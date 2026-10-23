//============================================================================
//
//  Pippin - the machine around the CPU
//  The save flash: an AMD Am29F010 (128 KB, 1 Mbit) at 40000000
//
//  As MAME's pippin.cpp (144-166) wires it: the flash's A0 is the CPU's A2,
//  so each byte is a 32-bit word's top byte lane (bits 31-24; the other
//  lanes read 0), 40000000-4007FFFF; and its data lines are reversed, bit 0
//  to bit 7. Everything below is in the flash's own terms: address
//  (offset >> 2) and the byte bit-reversed.
//
//  The Am29F010's commands (AMD's data sheet, in scratch/pdfs/chips), each
//  after the unlock cycles AA at 5555 and 55 at 2AAA (A14-A0 decoded):
//    A0 at 5555, then a byte to an address: program (bits only go from 1 to
//                0: the new byte is the old one AND the data)
//    80 at 5555, AA, 55, then 10 at 5555: erase the chip (every byte FF)
//                                   or 30 at an address: erase its 16 KB sector
//    90 at 5555: autoselect: address 0 reads 01 (AMD), 1 reads 20 (Am29F010),
//                until reset
//    F0 anywhere, any time (but as a program's data): back to reading the array
//  Programming finishes at once (a status read then shows the data itself,
//  which ends any DQ7 or DQ6 polling at its first read). An erase sweeps its
//  bytes, one a clock (16 KB or 128 KB); meanwhile a read answers the
//  embedded algorithm's status, as the data sheet's: DQ7 0 (the complement of
//  the erased byte's), DQ6 toggling at each read, DQ3 1 (the erase has begun),
//  the rest 0; writes are ignored. (Until 2026-10-22 a read answered FF during
//  the sweep: Mac OS's driver took the erase as done at its first poll, and its
//  program, arriving while the sweep held the RAM, was lost: no save at Shut
//  Down.) A write out of sequence goes back to reading the array.
//
//  The second port loads and saves the image (Pippin_nvsave's kind): a byte a
//  cycle by flash address; changed marks the CPU's changes.
//
//  The instant save (2026-10-23, the OSD's "Flash! saves"): Mac OS's driver keeps
//  the Flash! volume in the top 128 KB of the VRAM (F00E0000-F00FFFFF; the ROM
//  loads it from here at startup, FFCCE4A0, when "NuMc" is at 130C) and writes
//  it back here only at Shut Down or Restart (a sector erase and a program per
//  byte; measured on the board 2026-10-23: nothing in five minutes after a
//  change, the image written 4 s after Restart). A MiSTer is turned off or
//  given another disc or core without either, so with mir_on each VRAM store
//  into those 128 KB (mir_ld, presented by the machine as the store is
//  answered) is also written here, byte for byte at the same offset (the VRAM
//  holds the volume as the CPU reads the flash: VRAM byte n is flash byte n,
//  checked on the board), and changed marks it, so the image is saved a second
//  later. Armed only once the driver has read 130C in the array (the VRAM is
//  the ROM's scratch before that: dingusppc's taos.h), until the next reset;
//  mir_busy holds the next store into the volume while a store's bytes go in,
//  one a clock, in the clocks the CPU's port leaves free. The write-back at
//  Shut Down still works as before (it programs what is already here).
//
//============================================================================

module Pippin_flash
(
	input  logic         clk,
	input  logic         reset,

	// the CPU's side: a word access in 40000000-4007FFFF, one cycle; the answer the next
	input  logic         sel,
	input  logic         we,
	input  logic [18:2]  addr,
	input  logic [3:0]   be,
	input  logic [31:0]  wdata,
	output logic [31:0]  rdata,

	// the image, from outside: written (ld_we) or read (ld_re, its byte in ld_q a cycle later)
	input  logic         ld_we,
	input  logic         ld_re,
	input  logic [16:0]  ld_addr,
	input  logic [7:0]   ld_data,
	output logic [7:0]   ld_q,
	output logic         changed,         // a byte was programmed or erased by the CPU, or mirrored (one clock)

	// the instant save: a VRAM store into the volume's 128 KB, in the VRAM's byte order (a word,
	// be[3] the lowest address, or a whole line, word 0 in bits 255-224), one clock
	input  logic         mir_on,
	input  logic         mir_ld,
	input  logic         mir_line,
	input  logic [16:2]  mir_addr,
	input  logic [3:0]   mir_be,
	input  logic [255:0] mir_wdata,
	output logic         mir_busy
);

localparam logic [7:0] MFR_ID = 8'h01;   // AMD
localparam logic [7:0] DEV_ID = 8'h20;   // Am29F010

function automatic logic [7:0] rev8(input logic [7:0] x);
	for (int i = 0; i < 8; i++) rev8[i] = x[7 - i];
endfunction

// the bytes kept inverted, so that the block RAM's power-up zeros are an erased part (FF)
// without an initialisation file
// (two ports, the CPU's and the image's: true dual-port block RAM; neither port reads a byte in
// the clock the other writes it, so read-during-write is left to the RAM)
(* ramstyle = "no_rw_check, M10K" *) logic [7:0] mem [0:131071];

wire [16:0] fa   = addr[18:2];
wire [14:0] u    = fa[14:0];                 // the unlock decode: A14-A0
wire [7:0]  d    = rev8(wdata[31:24]);
wire        wr   = sel & we & be[3];

typedef enum logic [3:0] {
	F_READ, F_U1, F_U2, F_PROG, F_E0, F_E1, F_E2, F_ID
} fst_t;
fst_t st;

// erasing: a sweep over the bytes, one a cycle (16 KB or 128 KB); reads answer FF meanwhile
logic        er_on;
logic [16:0] er_a, er_end;

// the one memory port the CPU and the sweep share; the outside port is the other
logic        m_we;
logic [16:0] m_a;
logic [7:0]  m_d, m_q, m_q_n, ld_q_n;
logic        prog_q;                          // a program: the old byte read last cycle, written now
logic [16:0] prog_a;
logic [7:0]  prog_d;

// the instant save: the store in hand as a line (byte j of the line in bits 255-8j..248-8j), its
// bytes to go (mb_mask) from mb_idx on, mb_left of them
logic         armed;
logic [255:0] mb_data;
logic [31:0]  mb_mask;
logic [16:5]  mb_line;
logic [4:0]   mb_idx;
logic [5:0]   mb_left;
assign mir_busy = mb_left != 6'd0;
wire          mb_free = mir_busy && !sel && !er_on && !prog_q;   // the port's clock to take
wire  [7:0]   mb_byte = mb_data[8'(255 - 8 * mb_idx) -: 8];
wire          mb_we   = mb_free && mb_mask[mb_idx];

always_comb begin
	m_we = 1'b0;
	m_a  = fa;
	m_d  = 8'hFF;
	if (er_on)       begin m_we = 1'b1; m_a = er_a; end
	else if (prog_q) begin m_we = 1'b1; m_a = prog_a; m_d = m_q & prog_d; end
	else if (mb_we)  begin m_we = 1'b1; m_a = {mb_line, mb_idx}; m_d = rev8(mb_byte); end
	m_d = ~m_d;
end

always_ff @(posedge clk) begin
	if (m_we) mem[m_a] <= m_d;
	m_q_n <= mem[m_a];
end
assign m_q = ~m_q_n;
always_ff @(posedge clk) begin
	if (ld_we) mem[ld_addr] <= ~ld_data;
	ld_q_n <= mem[ld_addr];
end
assign ld_q = ~ld_q_n;

logic       rd_id, rd_er;
logic [7:0] id_q;
logic       er_tog;                     // DQ6: toggles at each read during an erase

always_ff @(posedge clk) begin
	changed <= 1'b0;
	prog_q  <= 1'b0;
	if (er_on) begin
		er_a <= er_a + 17'd1;
		if (er_a == er_end) er_on <= 1'b0;
		changed <= 1'b1;
	end
	if (prog_q) changed <= 1'b1;
	if (mb_we)  changed <= 1'b1;

	// the instant save: armed by the driver's look at the signature, a store taken whole, its
	// bytes written as the port is free
	if (sel & ~we && st == F_READ && !er_on && fa == 17'h0130C) armed <= 1'b1;
	if (mb_free) begin
		mb_idx  <= mb_idx + 5'd1;
		mb_left <= mb_left - 6'd1;
	end
	if (mir_ld && mir_on && armed && !mir_busy) begin
		mb_line <= mir_addr[16:5];
		if (mir_line) begin
			mb_data <= mir_wdata;
			mb_mask <= '1;
			mb_idx  <= 5'd0;
			mb_left <= 6'd32;
		end
		else begin
			mb_data <= {mir_wdata[31:0], 224'd0} >> (32 * mir_addr[4:2]);
			mb_mask <= 32'({mir_be[0], mir_be[1], mir_be[2], mir_be[3]}) << (4 * mir_addr[4:2]);
			mb_idx  <= {mir_addr[4:2], 2'b00};
			mb_left <= 6'd4;
		end
	end

	if (sel & ~we) begin
		rd_id <= st == F_ID;
		rd_er <= er_on;
		if (er_on) er_tog <= ~er_tog;
		id_q  <= (fa[0] == 1'b0) ? MFR_ID : DEV_ID;
	end

	if (wr && !er_on) begin
		// F0 resets, except as a program's data byte (any byte is data there)
		if (d == 8'hF0 && st != F_PROG) st <= F_READ;
		else case (st)
			F_READ, F_ID: st <= (u == 15'h5555 && d == 8'hAA) ? F_U1 : st;
			F_U1:   st <= (u == 15'h2AAA && d == 8'h55) ? F_U2 : F_READ;
			F_U2:   if (u == 15'h5555 && d == 8'hA0) st <= F_PROG;
			        else if (u == 15'h5555 && d == 8'h80) st <= F_E0;
			        else if (u == 15'h5555 && d == 8'h90) st <= F_ID;
			        else st <= F_READ;
			F_PROG: begin                        // the old byte comes out this cycle: AND it in the next
				prog_q <= 1'b1;
				prog_a <= fa;
				prog_d <= d;
				st     <= F_READ;
			end
			F_E0:   st <= (u == 15'h5555 && d == 8'hAA) ? F_E1 : F_READ;
			F_E1:   st <= (u == 15'h2AAA && d == 8'h55) ? F_E2 : F_READ;
			F_E2: begin
				if (u == 15'h5555 && d == 8'h10) begin           // the chip
					er_on <= 1'b1; er_a <= 17'd0; er_end <= 17'h1FFFF;
				end
				else if (d == 8'h30) begin                       // the 16 KB sector
					er_on <= 1'b1; er_a <= {fa[16:14], 14'd0}; er_end <= {fa[16:14], 14'h3FFF};
				end
				st <= F_READ;
			end
			default: st <= F_READ;
		endcase
	end

	if (reset) begin
		st     <= F_READ;
		er_on  <= 1'b0;
		prog_q <= 1'b0;
		rd_id  <= 1'b0;
		rd_er  <= 1'b0;
		er_tog <= 1'b0;
		armed  <= 1'b0;
		mb_left <= 6'd0;
	end
end

wire [7:0] byte_q = rd_id ? id_q : rd_er ? {1'b0, er_tog, 2'b00, 1'b1, 3'b000} : m_q;
assign rdata = {rev8(byte_q), 24'h0};

endmodule
