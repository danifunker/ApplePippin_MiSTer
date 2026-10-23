//============================================================================
//
//  Pippin - the machine around the CPU
//  The save image on the SD card: the save flash (Pippin_flash, 128 KB) and
//  Grand Central's 8 KB NVRAM (Mac OS's XPRAM at 1300-13FF: its settings),
//  in one image on hps_io's block slot 2
//
//  The Quadra 800 core's scheme for its PRAM (MacQuadra800.sv, "PRAM
//  persistence"), for two regions one after the other in the image: A, the
//  flash (2 ** ABITS bytes: blocks 0-255), then B, the NVRAM (2 ** BBITS
//  bytes: blocks 256-271; BBITS 0: none):
//    load   when an image is mounted: A's blocks if it holds A, and B's too
//           if it holds both (an image of A alone, the 128 KB of the
//           releases before 2026-10-22, keeps working: B is then not kept);
//           each block read and its 512 bytes written into the memory; the
//           machine is held in reset meanwhile (hold), so an image mounted
//           while it runs restarts it on what it holds
//    save   as storage: once a region has been written by the CPU and then
//           left alone for SETTLE_MS (1 s), or when the OSD opens, the blocks
//           of each region written since the last load or save are read out
//           and written to the image (not if it is read-only): a settings
//           change writes the NVRAM's 16 blocks, a flash write-back the
//           flash's 256
//  With no image mounted nothing happens: the memories start as they do
//  without this module (the flash erased, the NVRAM zeros).
//
//  hps_io's side (sd_*) is the block interface the disks use: rd or wr held
//  until sd_ack rises, the block moved while sd_ack is high (sd_buff_wr with
//  the bytes for a read; sd_buff_din one clock after sd_buff_addr for a
//  write), done when sd_ack falls. The memories' side is a byte channel to
//  the CPU's clock (BandaiPippin.sv): b_req held with b_we, b_addr, b_wdata
//  until b_done, the byte read in b_rdata then; b_addr[ABITS] picks B.
//  dirty_tog_a and dirty_tog_b toggle (in any clock) at each write the CPU
//  makes to each.
//
//============================================================================

module Pippin_nvsave
#(
	parameter int unsigned CLK_HZ    = 100_000_000,
	parameter int unsigned ABITS     = 17,            // region A: 2 ** ABITS bytes (the flash)
	parameter int unsigned BBITS     = 13,            // region B: 2 ** BBITS bytes (the NVRAM); 0 none
	parameter int unsigned SETTLE_MS = 1000           // a region left alone this long is saved
)
(
	input  logic        clk,
	input  logic        reset,

	// hps_io's block slot for the image
	input  logic        img_mounted,
	input  logic [63:0] img_size,
	input  logic        img_readonly,
	output logic [31:0] sd_lba,
	output logic        sd_rd,
	output logic        sd_wr,
	input  logic        sd_ack,
	input  logic [13:0] sd_buff_addr,
	input  logic [7:0]  sd_buff_dout,
	input  logic        sd_buff_wr,
	output logic [7:0]  sd_buff_din,

	input  logic        osd_open,
	input  logic        dirty_tog_a,
	input  logic        dirty_tog_b,
	output logic        hold,              // keep the machine in reset: a load under way

	// the byte channel to the memories
	output logic        b_req,
	output logic        b_we,
	output logic [ABITS:0] b_addr,
	output logic [7:0]  b_wdata,
	input  logic        b_done,
	input  logic [7:0]  b_rdata
);

localparam int unsigned SETTLE = CLK_HZ / 1000 * SETTLE_MS;
localparam int unsigned NA     = 1 << (ABITS - 9);                   // A's blocks
localparam int unsigned NB     = (BBITS >= 9) ? (1 << (BBITS - 9)) : 0;
localparam logic [63:0] SIZE_A = 64'd1 << ABITS;
localparam logic [63:0] SIZE_B = (BBITS >= 9) ? (64'd1 << BBITS) : 64'd0;
localparam int unsigned BW     = $clog2(NA + NB + 1);                 // bits of a block number
localparam logic [BW-1:0] A_LAST = BW'(NA - 1);
localparam logic [BW-1:0] B_FIRST = BW'(NA), B_LAST = BW'(NA + NB - 1);

typedef enum logic [2:0] {S_IDLE, S_LD_RD, S_LD_WAIT, S_LD_PUT, S_SV_GET, S_SV_WR, S_SV_WAIT} st_t;
st_t         s;
logic        ok, ok_b, ro;            // an image holding A; and B; read-only
logic [BW-1:0] blk;                   // the block in hand
logic [BW-1:0] last;                  // the last block of this load or save
logic [9:0]  idx;                     // the byte in hand (10 bits: 512 ends the block)
logic        acked;                   // hps_io has taken the block request
logic        dirty_a, dirty_b;
logic        sv_b_after;              // a save of A, then B's blocks too
logic [31:0] settle;
logic [2:0]  da_s, db_s;
logic        osd_q;

// a block's bytes in the memories' addressing
wire         in_b    = (NB != 0) && blk >= B_FIRST;
wire [ABITS:0] blk_base = in_b ? {1'b1, (ABITS)'(32'(blk - B_FIRST) << 9)}
                               : {1'b0, (ABITS)'(32'(blk) << 9)};

// the block buffer: one write port, one read port
logic [7:0]  buf_r [0:511];
logic [7:0]  buf_q;
logic [8:0]  buf_qa;                  // the address buf_q was read from
wire         buf_we = (s == S_LD_WAIT && sd_ack && sd_buff_wr) || (s == S_SV_GET && b_done);
wire  [8:0]  buf_wa = (s == S_SV_GET) ? idx[8:0] : sd_buff_addr[8:0];
wire  [7:0]  buf_wd = (s == S_SV_GET) ? b_rdata : sd_buff_dout;
wire  [8:0]  buf_ra = (s == S_LD_PUT) ? idx[8:0] : sd_buff_addr[8:0];
always_ff @(posedge clk) begin
	if (buf_we) buf_r[buf_wa] <= buf_wd;
	buf_q  <= buf_r[buf_ra];
	buf_qa <= buf_ra;
end
assign sd_buff_din = buf_q;
assign sd_lba      = 32'(blk);
assign hold        = s == S_LD_RD || s == S_LD_WAIT || s == S_LD_PUT;

wire da_ev = da_s[2] != da_s[1];
wire db_ev = db_s[2] != db_s[1];
wire save_now = !da_ev && !db_ev && (settle == 32'd0 || (osd_open && !osd_q));

always_ff @(posedge clk) begin
	da_s  <= {da_s[1:0], dirty_tog_a};
	db_s  <= {db_s[1:0], dirty_tog_b};
	osd_q <= osd_open;

	if (da_ev) dirty_a <= 1'b1;
	if (db_ev) dirty_b <= 1'b1;
	if (da_ev || db_ev) settle <= SETTLE;
	else if (settle != 32'd0) settle <= settle - 32'd1;

	case (s)
		S_IDLE: begin
			if (img_mounted) begin
				ok   <= img_size >= SIZE_A;
				ok_b <= NB != 0 && img_size >= SIZE_A + SIZE_B;
				ro   <= img_readonly;
				if (img_size >= SIZE_A) begin
					blk  <= '0;
					last <= (NB != 0 && img_size >= SIZE_A + SIZE_B) ? B_LAST : A_LAST;
					s    <= S_LD_RD;
				end
			end
			else if (ok && !ro && (dirty_a || (dirty_b && ok_b)) && save_now) begin
				// A's blocks, then B's if it was written too; or B's alone
				blk        <= dirty_a ? '0 : B_FIRST;
				last       <= dirty_a ? A_LAST : B_LAST;
				sv_b_after <= dirty_a && dirty_b && ok_b;
				dirty_a    <= 1'b0;                 // writes from now on make them dirty again
				dirty_b    <= 1'b0;
				idx        <= 10'd0;
				s          <= S_SV_GET;
			end
			else if (dirty_b && !ok_b && save_now) dirty_b <= 1'b0;   // an image without B: nothing to keep
		end

		// ---- load: a block from the image, then its bytes into the memory ----
		S_LD_RD: begin
			sd_rd <= 1'b1;
			acked <= 1'b0;
			s     <= S_LD_WAIT;
		end
		S_LD_WAIT: begin
			if (sd_ack) begin
				sd_rd <= 1'b0;
				acked <= 1'b1;
			end
			else if (acked) begin                // the block is in the buffer
				idx <= 10'd0;
				s   <= S_LD_PUT;
			end
		end
		S_LD_PUT: begin                          // buf_q is the byte at idx a clock after
			if (!b_req) begin
				if (idx == 10'd512) begin
					blk <= blk + 1'b1;
					if (blk == last) begin
						dirty_a <= 1'b0;
						dirty_b <= 1'b0;
						s       <= S_IDLE;
					end
					else s <= S_LD_RD;
				end
				else if (!b_done && buf_qa == idx[8:0]) begin
					b_req   <= 1'b1;
					b_we    <= 1'b1;
					b_addr  <= blk_base | (ABITS+1)'(idx[8:0]);
					b_wdata <= buf_q;
				end
			end
			else if (b_done) begin
				b_req <= 1'b0;
				idx   <= idx + 10'd1;
			end
		end

		// ---- save: a block's bytes out of the memory, then the block to the image ----
		S_SV_GET: begin
			if (!b_req) begin
				if (idx == 10'd512) begin
					sd_wr <= 1'b1;
					acked <= 1'b0;
					s     <= S_SV_WR;
				end
				else if (!b_done) begin
					b_req  <= 1'b1;
					b_we   <= 1'b0;
					b_addr <= blk_base | (ABITS+1)'(idx[8:0]);
				end
			end
			else if (b_done) begin               // buf_we takes the byte in this clock
				b_req <= 1'b0;
				idx   <= idx + 10'd1;
			end
		end
		S_SV_WR: begin
			if (sd_ack) begin
				sd_wr <= 1'b0;
				acked <= 1'b1;
			end
			else if (acked) s <= S_SV_WAIT;
		end
		S_SV_WAIT: begin
			idx <= 10'd0;
			if (blk == last && sv_b_after) begin  // A done: B's blocks next
				sv_b_after <= 1'b0;
				blk  <= B_FIRST;
				last <= B_LAST;
				s    <= S_SV_GET;
			end
			else begin
				blk <= blk + 1'b1;
				s   <= (blk == last) ? S_IDLE : S_SV_GET;
			end
		end
		default: s <= S_IDLE;
	endcase

	if (reset) begin
		s          <= S_IDLE;
		ok         <= 1'b0;
		ok_b       <= 1'b0;
		ro         <= 1'b1;
		blk        <= '0;
		last       <= '0;
		idx        <= 10'd0;
		acked      <= 1'b0;
		dirty_a    <= 1'b0;
		dirty_b    <= 1'b0;
		sv_b_after <= 1'b0;
		settle     <= 32'd0;
		sd_rd      <= 1'b0;
		sd_wr      <= 1'b0;
		b_req      <= 1'b0;
		b_we       <= 1'b0;
	end
end

endmodule
