//============================================================================
//
//  Pippin - the machine around the CPU
//  Taos's picture side, in the video clock (the memory clock): the VRAM in
//  DDR3, the dot clock, the timing generator, the scan-out
//
//  From Pippin_video (MacPPC7300's Control picture side): the same VRAM
//  port and DDR3 arbitration (the scan-out first; the CPU's accesses through
//  their crossing, a word or a 32-byte line), the same line buffers. What is
//  Taos's (dingusppc's taos.cpp enable_display and converters, MAME's
//  taos.cpp rebuild_params):
//
//    - the timing generator: Taos's DAFB-style registers (HEQ 2C ... VHLINE
//      64, each a 12-bit count in bits 31-20), counted as Pippin_swatch
//      counts Control's, horizontally in dots, vertically in half-lines. An
//      odd half-line total (NTSC 525, PAL 625) is interlaced: the count keeps
//      the half-line over the field's end, so the fields alternate, and a
//      field shows every other line of the frame buffer (its parity the
//      field's). The ROM's NTSC timing: 780 dots a line, 640 active, 240
//      lines a field, 15.7 kHz at Athens's 12.27 MHz; VGA's is 640 x 480
//      progressive at 31 kHz;
//    - the frame buffer: line y at FB_BASE >> 20 + y x (ROW_WORDS >> 20)
//      bytes (dingusppc: fb_ptr = vram + (fb_base >> 20), fb_pitch =
//      row_words >> 20); COLOR_MODE bit 31: 16-bit x-R5-G5-B5, else 8-bit;
//    - colour: an 8-bit pixel through Taos's colour table; a 16-bit pixel's
//      three components, each through the table at its five-bit value
//      (dingusppc's convert_frame_15bpp_indexed);
//    - the dot clock: Athens's (Pippin_athens) from its 20 MHz crystal
//      (dingusppc's AthensClocks(0x29, 20000000), MAME's 20_MHz_XTAL):
//      20 MHz x N2 / (D2 x 2^(3 - P2_MUX2[1:0])), or the crystal / 2^(...)
//      with P2_MUX2[5:4] = 2, as a clock enable of the video clock.
//
//  vbl is high during the vertical blanking (Taos's GPIO 6, active low: MAME
//  reads it as "0 in vblank"); field is the field being shown (0 the one
//  starting a half-line earlier); interlaced follows the timing.
//
//============================================================================

module Pippin_taosvideo
#(
	parameter int unsigned CLKV_HZ  = 100_000_000,
	parameter logic [28:0] DDR_BASE = 29'h0600_0000,    // byte 3000_0000, in 64-bit words
	// 1: the dot clock is always the console's standard line rate times Taos's line (below);
	// 0: that until Mac OS programs Athens (athens_set), then half Athens's output (not yet
	// right: the driver writes only P2_MUX2, below)
	parameter bit          STD_DOT  = 1'b1,
	// 1: the VRAM (its 1 MB of DDR3) is cleared once when the FPGA is configured, as a power-up
	// loses a real Pippin's VRAM; a reset keeps it, as the Pippin's own reset does (below)
	parameter bit          VRAM_CLEAR = 1'b1
)
(
	input  logic         clk,             // the video clock: the memory clock
	input  logic         reset,

	// the CPU's VRAM accesses, from their clock crossing (the CPU port's protocol)
	input  logic         c_req,
	input  logic         c_we,
	input  logic         c_line,
	input  logic [21:2]  c_addr,          // VRAM byte address
	input  logic [31:0]  c_be,            // a word's four (be[3] the lowest address); a line write's mask (bit j: the line's byte in bits 8j+7..8j)
	input  logic [255:0] c_wdata,
	output logic         c_ack,
	output logic [255:0] c_rdata,

	// DDR3, the framework's DDRAM port
	input  logic         ddr_busy,
	output logic [7:0]   ddr_burstcnt,
	output logic [28:0]  ddr_addr,
	input  logic [63:0]  ddr_dout,
	input  logic         ddr_dout_ready,
	output logic         ddr_rd,
	output logic [63:0]  ddr_din,
	output logic [7:0]   ddr_be,
	output logic         ddr_we,

	// Taos's registers, from the CPU's clock (standing still while used)
	input  logic         timing_on,       // CRT_CTRL bit 24
	input  logic [479:0] swatch,          // HEQ (bits 31-0) .. VHLINE
	input  logic [31:0]  fb_base,
	input  logic [31:0]  row_words,
	input  logic         color16,
	input  logic [7:0]   athens_d2,
	input  logic [7:0]   athens_n2,
	input  logic [7:0]   athens_p2,
	input  logic         athens_set,      // Athens has been programmed (quasi-static, the CPU's clock)
	input  logic [2:0]   mon_id,          // the console's video switch: 5 NTSC, 3 PAL, 6 VGA (STD_DOT)
	input  logic         progressive,     // an interlaced timing shown progressive: every line each field (quasi-static)
	output logic         vbl,
	output logic [23:0]  clut_index,      // Taos's colour table (R, G, B indices), read a clock later
	input  logic [23:0]  clut_rgb,

	// the picture
	output logic         ce_pix,
	output logic [7:0]   r,
	output logic [7:0]   g,
	output logic [7:0]   b,
	output logic         hs,
	output logic         vs,
	output logic         hblank,
	output logic         vblank,
	output logic         field,
	output logic         interlaced
);

// ---- Taos's timing registers: the counts in bits 31-20 ----------------------------------------
function automatic logic [11:0] tr(input logic [479:0] sw, input int n);   // n: offset >> 2 less 0x0B
	tr = sw[32 * n + 20 +: 12];
endfunction
wire [11:0] T_HBWAY = tr(swatch, 1);
wire [11:0] T_HAL   = tr(swatch, 2);
wire [11:0] T_HFP   = tr(swatch, 4);
wire [11:0] T_HPIX  = tr(swatch, 5);
wire [11:0] T_HSP   = tr(swatch, 6);
wire [11:0] T_VBPEQ = tr(swatch, 8);
wire [11:0] T_VAL   = tr(swatch, 10);
wire [11:0] T_VFP   = tr(swatch, 11);
wire [11:0] T_VSYNC = tr(swatch, 13);
wire [11:0] T_VHL   = tr(swatch, 14);

wire [11:0] fbb  = fb_base[31:20];
wire [11:0] pitch = row_words[31:20];

// ---- the dot clock ---------------------------------------------------------------------------
// STD_DOT (2026-10-19): the ROM leaves Athens at 20 MHz x 46 / (16 x 4) = 14.375 MHz, which on
// Taos's 780-clock line (HPIX 778) made 18.43 kHz lines and 70 Hz fields on the board.
// dingusppc's Pippin (no save flash: another branch of the ROM) has Mac OS's driver set
// 24.545 MHz (27 / 11 / 2), Taos counting a dot every second clock; that reprogramming never
// reaches our Athens, why not yet known. Meanwhile the dot clock is the standard's line rate
// times Taos's own line length (HPIX + 2): NTSC 4.5 MHz / 286 = 15,734.27 Hz (12.27 MHz on
// 780), PAL 15,625 Hz, VGA 25.175 MHz / 800 = 31,468.75 Hz.
//
// Since 2026-10-22 the Athens is the one at I2C 28 (Pippin_machine), which Mac OS's driver
// programs: NTSC 20 MHz x 27 / (11 x 2) = 24.545 MHz. Taos's counts are dingusppc's (a frame
// is the clock / (horizontal total x vertical total in half-lines)), and ours step two half-lines
// a line, so our dot is half Athens's output: 12.27 MHz, 15,734 Hz on 780. Until the driver has
// written it (the boot logo; that chip's power-up output is not known) the standard rate as above.
// The bench (run28) shows the driver writing only P2_MUX2 = 02 to it (PLL, post-divider 2) and
// 07 = 82 to the one at 29: D2 and N2 stay at power-up, which nobody models (dingusppc 2 and 2:
// 5 MHz here; MAME 0). Power-up values of D2 0B, N2 1B (what the E2 path writes) would make the
// NTSC clock exactly (20 x 27 / 11 / 2 = 24.545 MHz), unproven; so STD_DOT stays 1 for now.
localparam longint unsigned XTAL = 20_000_000;
logic [1:0]  set_s;
always_ff @(posedge clk) set_s <= {set_s[0], athens_set};
// Progressive (2026-10-22, the OSD's Interlace option): an interlaced timing (NTSC, PAL) is
// shown as a progressive picture: each field period scans every line of the frame buffer,
// one a half-line of the timing, at twice the dot rate (480 lines at 31 kHz for NTSC, the
// field rate and the vertical blank Mac OS sees unchanged), so the fields' flicker goes
logic [1:0]  prog_s;
always_ff @(posedge clk) prog_s <= {prog_s[0], progressive};
wire         prog_dot = prog_s[1] & T_VHL[0];
logic [39:0] numer, denom, acc;
logic        dot_off, ce_dot;
wire  [40:0] acc_n = {1'b0, acc} + {1'b0, numer};
wire  [7:0]  d_eff = (athens_p2[5:4] == 2'd2) ? 8'd1 : athens_d2;
wire  [12:0] htot  = {1'b0, T_HPIX} + 13'd2;
always_ff @(posedge clk) begin
	if (STD_DOT || !set_s[1]) begin
		numer   <= ((mon_id == 3'd5) ? 40'(4_500_000)  * 40'(htot) :
		            (mon_id == 3'd3) ? 40'(15_625)     * 40'(htot) :
		                               40'(25_175_000) * 40'(htot)) << prog_dot;
		denom   <= (mon_id == 3'd5) ? 40'(286) * 40'(CLKV_HZ) :
		           (mon_id == 3'd3) ? 40'(CLKV_HZ) :
		                              40'(800) * 40'(CLKV_HZ);
		dot_off <= 1'b0;
	end
	else begin
		numer   <= ((athens_p2[5:4] == 2'd2) ? 40'(XTAL) : 40'(athens_n2) * 40'(XTAL)) << prog_dot;
		denom   <= (40'(d_eff) * 40'(CLKV_HZ)) << (3'd4 - {1'b0, athens_p2[1:0]});   // (x 2: half the output)
		dot_off <= athens_p2[7] | athens_p2[4] | (athens_p2[5:4] == 2'd0 && (athens_d2 == 8'd0 || athens_n2 == 8'd0));
	end
	ce_dot  <= 1'b0;
	if (dot_off) acc <= 40'd0;
	else if (numer >= denom) begin acc <= 40'd0; ce_dot <= 1'b1; end
	else if (acc_n >= {1'b0, denom}) begin acc <= 40'(acc_n - {1'b0, denom}); ce_dot <= 1'b1; end
	else acc <= acc_n[39:0];
	if (reset) begin acc <= 40'd0; ce_dot <= 1'b0; end
end

// ---- the timing generator ------------------------------------------------------------------------
// While Taos's timing is off (from power-up to the ROM's picture) the counters run a fixed
// 640 x 480 at 60 Hz with negative syncs at a 25 MHz dot clock, black, so that the framework
// always has a picture (Pippin_swatch's fallback).
logic [1:0]  on_s;
wire         use_fb = ~on_s[1];
logic        fb_q;
logic [1:0]  fb_div;
wire         ce_fb  = fb_div == 2'd0;
wire         ce_eff = use_fb ? ce_fb : ce_dot;

wire [11:0] VBPEQ = use_fb ? 12'd0    : T_VBPEQ;
wire [11:0] VFP   = use_fb ? 12'd1030 : T_VFP;
wire [11:0] VAL   = use_fb ? 12'd70   : T_VAL;
wire [11:0] VSYNC = use_fb ? 12'd1046 : T_VSYNC;
wire [11:0] VHL   = use_fb ? 12'd1050 : T_VHL;
wire [11:0] HPIX  = use_fb ? 12'd798  : T_HPIX;
wire [11:0] HFP   = use_fb ? 12'd784  : T_HFP;
wire [11:0] HAL   = use_fb ? 12'd144  : T_HAL;
wire [11:0] HBWAY = use_fb ? 12'd0    : T_HBWAY;
wire [11:0] HSP   = use_fb ? 12'd704  : T_HSP;
wire        ilace = VHL[0];
wire        pmode = ilace & prog_s[1] & ~use_fb;  // the interlaced timing shown progressive

logic [11:0] h, v;
logic [11:0] xa;
logic        s_ce, s_hs, s_vs, s_hb, s_vb, fetch, s_fld;
logic [11:0] s_x;
logic [10:0] s_y, fetch_y;                // the line within the field
logic        fetch_fld;

wire [12:0] v2      = {1'b0, v} + (pmode ? 13'd1 : 13'd2);
wire [11:0] v_next  = (v2 >= {1'b0, VHL}) ? 12'(v2 - {1'b0, VHL}) : v2[11:0];
wire        last_h  = h >= HPIX + 12'd1;
wire        v2_act  = (v_next >= VAL) && (v_next < VFP);
wire [11:0] v_rel   = v - VAL;
wire [11:0] vn_rel  = v_next - VAL;

always_ff @(posedge clk) begin
	on_s   <= {on_s[0], timing_on};
	fb_q   <= use_fb;
	fb_div <= fb_div + 2'd1;
	s_ce   <= 1'b0;
	fetch  <= 1'b0;

	if (fb_q != use_fb) begin                // the timing changes hands: the counters start over
		h     <= 12'd0;
		v     <= 12'd0;
		xa    <= 12'd0;
		s_hs  <= 1'b1;
		s_vs  <= 1'b1;
		s_hb  <= 1'b1;
		s_vb  <= 1'b1;
	end
	else if (ce_eff) begin
		s_ce  <= 1'b1;
		s_hb  <= ~((h >= HAL) && (h < HFP));
		s_vb  <= ~((v >= VAL) && (v < VFP));
		s_hs  <= ~((h >= HSP) || (h < HBWAY));    // negative syncs
		s_vs  <= ~((v >= VSYNC) || (v < VBPEQ));
		s_x   <= xa;
		s_y   <= pmode ? 11'(v_rel) : 11'(v_rel >> 1);
		s_fld <= ilace & ~pmode & v_rel[0];
		if ((h >= HAL) && (h < HFP)) xa <= xa + 12'd1;
		if (!last_h) h <= h + 12'd1;
		else begin
			h  <= 12'd0;
			xa <= 12'd0;
			v  <= v_next;
		end
		// a line starts: fetch the line after it if that one is active
		if (h == 12'd0) begin
			fetch     <= v2_act && !use_fb;
			fetch_y   <= pmode ? 11'(vn_rel) : 11'(vn_rel >> 1);
			fetch_fld <= ilace & ~pmode & vn_rel[0];
		end
	end
end
assign vbl = s_vb;

initial begin
	on_s   = 2'b00;
	fb_q   = 1'b1;
	fb_div = 2'd0;
end

// ---- the line fetch ----------------------------------------------------------------------------
wire [11:0] width  = HFP - HAL;
wire [14:0] lpix   = color16 ? {2'd0, width, 1'b0} : {3'd0, width};
wire [14:0] lbytes = lpix + 15'd7;
wire [11:0] lwords = 12'(lbytes >> 3);

typedef enum logic [2:0] {D_IDLE, D_FREAD, D_FWAIT, D_CREAD, D_CWAIT, D_CWRITE, D_CLEAR} ds_t;
ds_t         ds;
// VRAM_CLEAR (2026-10-22): the DDR3 keeps the VRAM over a core reload, and Mac OS's Flash! driver
// keeps its volume in VRAM (F00E0000-F00FFFFF, loaded from the save flash at boot only when the
// flash holds a volume, written back at Shut Down): without the clear, a volume never saved
// survived a reload, as if saved. 1 MB of zeros in bursts of 128 words, before anything else
// gets the port (the CPU is held meanwhile for the ROM's download).
logic        clr_on = VRAM_CLEAR;
logic [16:0] clr_a  = 17'd0;               // the next 64-bit word
logic [6:0]  clr_beat;
logic        f_pend;                   // a line is being fetched
logic        f_calc;                   // its address is being made
logic [21:0] f_line;                   // the frame buffer line's first byte
logic [21:0] f_addr;                   // the next byte to ask for
logic [11:0] f_left;                   // words still to ask for
logic [11:0] f_put;                    // where the next word goes
logic        f_bank;
logic [7:0]  f_burst;                  // the burst asked for
logic [7:0]  f_due;                    // its words still to come
logic        f_issue;
logic        f_last;                   // the last DDR3 access was a scan-out burst
wire         f_word = (ds == D_FWAIT) && ddr_dout_ready;
wire  [7:0]  f_next = (f_left > 12'd32) ? 8'd32 : 8'(f_left);
// the frame buffer's line: a field shows every other one
wire  [10:0] fb_y   = (ilace & ~pmode) ? {fetch_y[9:0], fetch_fld} : fetch_y;

always_ff @(posedge clk) begin
	f_calc <= 1'b0;
	if (fetch) begin
		f_line <= {10'd0, fbb} + 22'(fb_y * pitch);
		f_bank <= fetch_y[0];
		f_calc <= 1'b1;
	end
	if (f_calc) begin
		f_addr <= f_line;
		f_left <= lwords;
		f_put  <= 12'd0;
		f_pend <= 1'b1;
	end
	else if (f_issue) begin
		f_addr <= f_addr + {11'd0, f_burst, 3'b000};
		f_left <= f_left - {4'd0, f_burst};
		if (f_left == {4'd0, f_burst}) f_pend <= 1'b0;
	end
	if (f_word) f_put <= f_put + 12'd1;
	if (reset) f_pend <= 1'b0;
end

// ---- the line buffers: two lines of up to 1024 words ---------------------------------------------
logic [63:0]  lbuf [0:2047];
logic [63:0]  lb_q;
logic [10:0]  lb_ra;
always_ff @(posedge clk) begin
	if (f_word) lbuf[{f_bank, f_put[9:0]}] <= ddr_dout;
	lb_q <= lbuf[lb_ra];
end

// ---- DDR3: the scan-out and the CPU in turn (Pippin_video's) -----------------------------------------
logic [2:0]  c_beat;
logic [63:0] c_got0, c_got1, c_got2, c_got3;
wire  [2:0]  c_n = c_line ? 3'd4 : 3'd1;

wire [31:0] c_w0     = c_wdata[31:0];
wire [63:0] c_word64 = c_addr[2] ? {c_w0[7:0], c_w0[15:8], c_w0[23:16], c_w0[31:24], 32'h0}
                                 : {32'h0, c_w0[7:0], c_w0[15:8], c_w0[23:16], c_w0[31:24]};
wire [7:0]  c_be8    = c_addr[2] ? {c_be[0], c_be[1], c_be[2], c_be[3], 4'h0} : {4'h0, c_be[0], c_be[1], c_be[2], c_be[3]};
function automatic logic [63:0] line_beat(input logic [255:0] w, input logic [1:0] k);
	logic [31:0] w0, w1;
	w0 = w[255 - 64 * k -: 32];
	w1 = w[223 - 64 * k -: 32];
	line_beat = {w1[7:0], w1[15:8], w1[23:16], w1[31:24], w0[7:0], w0[15:8], w0[23:16], w0[31:24]};
endfunction
function automatic logic [7:0] beat_be(input logic [31:0] m, input logic [1:0] k);
	logic [3:0] m0, m1;
	m0 = m[31 - 8 * k -: 4];
	m1 = m[27 - 8 * k -: 4];
	beat_be = {m1[0], m1[1], m1[2], m1[3], m0[0], m0[1], m0[2], m0[3]};
endfunction
function automatic logic [31:0] lane_word(input logic [63:0] q, input logic hi);
	lane_word = hi ? {q[39:32], q[47:40], q[55:48], q[63:56]} : {q[7:0], q[15:8], q[23:16], q[31:24]};
endfunction

always_ff @(posedge clk) begin
	f_issue <= 1'b0;
	c_ack   <= 1'b0;
	case (ds)
		D_IDLE: begin
			ddr_rd <= 1'b0;
			ddr_we <= 1'b0;
			if (clr_on) begin
				ddr_addr     <= DDR_BASE + {12'd0, clr_a};
				ddr_burstcnt <= 8'd128;
				ddr_din      <= 64'd0;
				ddr_be       <= 8'hFF;
				ddr_we       <= 1'b1;
				clr_beat     <= 7'd0;
				ds           <= D_CLEAR;
			end
			else if (f_pend && !f_issue && !f_calc && !(c_req && !c_ack && f_last)) begin
				f_last       <= 1'b1;
				f_burst      <= f_next;
				ddr_addr     <= DDR_BASE + {10'd0, f_addr[21:3]};
				ddr_burstcnt <= f_next;
				ddr_rd       <= 1'b1;
				ds           <= D_FREAD;
			end
			else if (c_req && !c_ack) begin
				f_last       <= 1'b0;
				ddr_addr     <= DDR_BASE + {10'd0, c_addr[21:5], c_line ? 2'b00 : c_addr[4:3]};
				ddr_burstcnt <= {5'd0, c_n};
				c_beat       <= 3'd0;
				if (c_we) begin
					ddr_we  <= 1'b1;
					ddr_din <= c_line ? line_beat(c_wdata, 2'd0) : c_word64;
					ddr_be  <= c_line ? beat_be(c_be, 2'd0) : c_be8;
					ds      <= D_CWRITE;
				end
				else begin
					ddr_rd <= 1'b1;
					ds     <= D_CREAD;
				end
			end
		end
		D_FREAD: if (!ddr_busy) begin
			ddr_rd  <= 1'b0;
			f_issue <= 1'b1;
			f_due   <= f_burst;
			ds      <= D_FWAIT;
		end
		D_FWAIT: if (ddr_dout_ready) begin
			f_due <= f_due - 8'd1;
			if (f_due == 8'd1) ds <= D_IDLE;
		end
		D_CREAD: if (!ddr_busy) begin
			ddr_rd <= 1'b0;
			ds     <= D_CWAIT;
		end
		D_CWAIT: if (ddr_dout_ready) begin
			case (c_beat[1:0])
				2'd0:    c_got0 <= ddr_dout;
				2'd1:    c_got1 <= ddr_dout;
				2'd2:    c_got2 <= ddr_dout;
				default: c_got3 <= ddr_dout;
			endcase
			c_beat <= c_beat + 3'd1;
			if (c_beat + 3'd1 == c_n) begin
				c_ack <= 1'b1;
				ds    <= D_IDLE;
			end
		end
		D_CWRITE: if (!ddr_busy) begin
			if (c_beat + 3'd1 == c_n) begin
				ddr_we <= 1'b0;
				c_ack  <= 1'b1;
				ds     <= D_IDLE;
			end
			else begin
				c_beat  <= c_beat + 3'd1;
				ddr_din <= line_beat(c_wdata, 2'(c_beat + 3'd1));
				ddr_be  <= beat_be(c_be, 2'(c_beat + 3'd1));
			end
		end
		D_CLEAR: if (!ddr_busy) begin
			clr_beat <= clr_beat + 7'd1;
			if (clr_beat == 7'd127) begin
				ddr_we <= 1'b0;
				clr_a  <= clr_a + 17'd128;
				if (clr_a == 17'h1FF80) clr_on <= 1'b0;
				ds     <= D_IDLE;
			end
		end
		default: ds <= D_IDLE;
	endcase
	if (reset & ~clr_on) begin
		ds     <= D_IDLE;
		ddr_rd <= 1'b0;
		ddr_we <= 1'b0;
		f_last <= 1'b0;
	end
end

always_comb begin
	if (c_line)
		c_rdata = {lane_word(c_got0, 1'b0), lane_word(c_got0, 1'b1), lane_word(c_got1, 1'b0), lane_word(c_got1, 1'b1),
		           lane_word(c_got2, 1'b0), lane_word(c_got2, 1'b1), lane_word(c_got3, 1'b0), lane_word(c_got3, 1'b1)};
	else
		c_rdata = {224'h0, lane_word(c_got0, c_addr[2])};
end

// ---- the pixels ----------------------------------------------------------------------------------------
// stage 0, the counters' dot: its word in the line buffer
wire [14:0] p_byte = color16 ? {2'd0, s_x, 1'b0} : {3'd0, s_x};
assign lb_ra = {s_y[0], p_byte[12:3]};

// stage 1: the word comes out of the line buffer
logic        p1_ce, p1_de, p1_hs, p1_vs, p1_hb, p1_vb, p1_fld;
logic [2:0]  p1_lane;
logic [7:0]  pix8;
logic [15:0] pix16;
always_comb begin
	pix8  = lb_q[8 * p1_lane +: 8];
	pix16 = {lb_q[8 * p1_lane +: 8], lb_q[8 * 3'(p1_lane + 3'd1) +: 8]};
end
// stage 2: the index going to the colour table
logic        p2_ce, p2_de, p2_hs, p2_vs, p2_hb, p2_vb, p2_fld;
// stage 3: the colour table answers
logic        p3_ce, p3_de, p3_hs, p3_vs, p3_hb, p3_vb, p3_fld;

always_ff @(posedge clk) begin
	p1_ce   <= s_ce;
	p1_de   <= ~s_hb & ~s_vb;
	p1_hs   <= s_hs;
	p1_vs   <= s_vs;
	p1_hb   <= s_hb;
	p1_vb   <= s_vb;
	p1_fld  <= s_fld;
	p1_lane <= p_byte[2:0];

	p2_ce      <= p1_ce;
	p2_de      <= p1_de;
	p2_hs      <= p1_hs;
	p2_vs      <= p1_vs;
	p2_hb      <= p1_hb;
	p2_vb      <= p1_vb;
	p2_fld     <= p1_fld;
	clut_index <= color16 ? {3'd0, pix16[14:10], 3'd0, pix16[9:5], 3'd0, pix16[4:0]} : {3{pix8}};

	p3_ce  <= p2_ce;
	p3_de  <= p2_de;
	p3_hs  <= p2_hs;
	p3_vs  <= p2_vs;
	p3_hb  <= p2_hb;
	p3_vb  <= p2_vb;
	p3_fld <= p2_fld;

	{r, g, b}  <= (p3_de && !fb_q) ? clut_rgb : 24'h0;
	ce_pix     <= p3_ce;
	hs         <= p3_hs;
	vs         <= p3_vs;
	hblank     <= p3_hb;
	vblank     <= p3_vb;
	field      <= p3_fld;
	interlaced <= ilace & ~pmode;
end

endmodule
