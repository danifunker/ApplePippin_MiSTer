//============================================================================
//
//  Pippin - the machine around the CPU
//  Taos (343S0153), the Pippin's video controller: its registers at
//  F0800000 and its colour table at F1000000
//
//  Follows dingusppc's devices/video/taos.cpp and taos.h (the registers,
//  read 85-107, write 109-170; the colour table, 82-86, 112-116) and MAME's
//  apple/taos.cpp. Every register keeps its value in the word's top bits, as
//  the CPU writes it; the timing generator's (HEQ 2C ... VHLINE 64) are
//  stored for the scan-out. A read answers, as dingusppc's does:
//    20 CRT_CTRL      as written
//    68 GPIO_IN       the monitor ID in bits 31-29 (mon_id: 5 NTSC, 6 VGA,
//                     3 PAL; the switch on the console's back, active low),
//                     bit 27 the console's eject button (0 while pressed:
//                     the ROM's VBL task polls it; dingusppc's "CD tray"
//                     reads 1 always), bit 25 the vertical sync,
//                     without the pins GPIO_CONFIG makes outputs (dingusppc
//                     masks the low byte instead: the same here, the ROM's
//                     configurations touching none of those pins)
//    7C INT_ENABLES   as written
//    8C TAOS_VERSION  A5000000
//  and 0 everywhere else. The ROM writes INT_ENABLES only with 0: Taos raises
//  no interrupt here (the Pippin's VBL comes through the VIA, as on a Power
//  Mac; docs/pippin_plan.md).
//
//  The colour table: 256 entries, R, G, B in bits 31-8 of each word (a read
//  gives them back so, bits 7-0 zero). The scan-out looks up a component per
//  index (8-bit pixels: one index for all three; 16-bit xRGB555 pixels: each
//  five-bit component through the table, as dingusppc's
//  convert_frame_15bpp_indexed does), in its own clock.
//
//  An access is presented for one cycle (sel or clut_sel); the read data is
//  valid in the next cycle.
//
//============================================================================

module Pippin_taos
(
	input  logic         clk,
	input  logic         reset,

	input  logic         sel,             // the registers (F0800000-F08007FF)
	input  logic         clut_sel,        // the colour table (F1000000-F10003FF)
	input  logic         we,
	input  logic [10:2]  addr,
	input  logic [3:0]   be,
	input  logic [31:0]  wdata,
	output logic [31:0]  rdata,

	input  logic [2:0]   mon_id,          // 5 NTSC, 6 VGA, 3 PAL
	input  logic         eject_btn,       // the console's eject button, pressed (GPIO 27, low while pressed)
	input  logic         vsync,           // the vertical sync input (GPIO 6)

	// to the scan-out (in this clock; standing still while they are used)
	output logic [31:0]  fb_base,         // FB_BASE as written (bits 31-12: the byte offset in VRAM)
	output logic [31:0]  row_words,       // ROW_WORDS as written (bits 31-20: the pitch in bytes)
	output logic         color16,         // COLOR_MODE bit 31: 16-bit xRGB555, else 8-bit indexed
	output logic [1:0]   video_mode,      // VIDEO_MODE bits 31-30 (0 progressive, 1-3 interlaced)
	output logic [31:0]  crt_ctrl,        // bit 24: video out enabled
	output logic [15*32-1:0] swatch,      // HEQ (2C) .. VHLINE (64), the first in bits 31-0
	output logic [23:0]  window,          // {HSTART, VEFS}: where the frame buffer's picture starts in the timing

	// the colour table, read by the scan-out in its clock
	input  logic         clk_v,
	input  logic [7:0]   v_index_r,
	input  logic [7:0]   v_index_g,
	input  logic [7:0]   v_index_b,
	output logic [23:0]  v_rgb
);

import Pippin_pkg::*;

localparam logic [31:0] TAOS_VERSION = 32'hA500_0000;

logic [31:0] gpio_cfg, gpio_out, gpio_int_ctrl, int_enables, crt_test, vconv_end;
// the picture's window in the timing (HSTART and VEFS go to the scan-out; readable by the machine bench)
logic [31:0] vefs /*verilator public_flat_rd*/, vofs /*verilator public_flat_rd*/,
             hstart /*verilator public_flat_rd*/, heb /*verilator public_flat_rd*/;
logic [31:0] sw [15];

always_comb for (int i = 0; i < 15; i++) swatch[32 * i +: 32] = sw[i];
assign window = {hstart[31:20], vefs[31:20]};

wire [8:0]  rn     = addr[10:2];          // register number: offset >> 2
wire [3:0]  sw_n   = 4'(rn - 9'h0B);      // a timing register's index (HEQ 0 ... VHLINE 14)
wire [31:0] gpio_in = ({mon_id, 1'b0, ~eject_btn, 1'b0, vsync, 25'd0}) & ~{gpio_cfg[31:24], 24'd0};

// ---- the colour table ------------------------------------------------------------------
logic [23:0] clut_c [0:255];
logic [23:0] clut_q;
logic [7:0]  clut_vr [0:255];
logic [7:0]  clut_vg [0:255];
logic [7:0]  clut_vb [0:255];
wire         clut_we = clut_sel & we & (be == 4'hF);
wire  [7:0]  ci      = addr[9:2];

always_ff @(posedge clk) begin
	if (clut_we) clut_c[ci] <= wdata[31:8];
	clut_q <= clut_c[ci];
end
always_ff @(posedge clk) if (clut_we) clut_vr[ci] <= wdata[31:24];
always_ff @(posedge clk) if (clut_we) clut_vg[ci] <= wdata[23:16];
always_ff @(posedge clk) if (clut_we) clut_vb[ci] <= wdata[15:8];
always_ff @(posedge clk_v) v_rgb[23:16] <= clut_vr[v_index_r];
always_ff @(posedge clk_v) v_rgb[15:8]  <= clut_vg[v_index_g];
always_ff @(posedge clk_v) v_rgb[7:0]   <= clut_vb[v_index_b];

// ---- the registers -----------------------------------------------------------------------
logic        rd_clut;
logic [31:0] rq;

always_ff @(posedge clk) begin
	rd_clut <= clut_sel;
	if (sel) begin
		case (rn)
			9'h08:   rq <= crt_ctrl;
			9'h1A:   rq <= gpio_in;
			9'h1F:   rq <= int_enables;
			9'h23:   rq <= TAOS_VERSION;
			default: rq <= 32'h0;
		endcase
	end
	if (sel & we) begin
		case (rn)
			9'h00: fb_base       <= merge_be(fb_base, wdata, be);
			9'h01: row_words     <= merge_be(row_words, wdata, be);
			9'h02: color16       <= be[3] ? wdata[31] : color16;
			9'h03: video_mode    <= be[3] ? wdata[31:30] : video_mode;
			9'h04: vefs          <= merge_be(vefs, wdata, be);
			9'h05: vofs          <= merge_be(vofs, wdata, be);
			9'h06: hstart        <= merge_be(hstart, wdata, be);
			9'h07: vconv_end     <= merge_be(vconv_end, wdata, be);
			9'h08: crt_ctrl      <= merge_be(crt_ctrl, wdata, be);
			9'h09: crt_test      <= merge_be(crt_test, wdata, be);
			9'h1B: gpio_cfg      <= merge_be(gpio_cfg, wdata, be);
			9'h1C: gpio_out      <= merge_be(gpio_out, wdata, be);
			9'h1D: gpio_int_ctrl <= merge_be(gpio_int_ctrl, wdata, be);
			9'h1F: int_enables   <= merge_be(int_enables, wdata, be);
			9'h25: heb           <= merge_be(heb, wdata, be);
			default: if (rn >= 9'h0B && rn <= 9'h19) sw[sw_n] <= merge_be(sw[sw_n], wdata, be);
		endcase
	end
	if (reset) begin
		fb_base       <= 32'h0;
		row_words     <= 32'h0;
		color16       <= 1'b0;
		video_mode    <= 2'd0;
		vefs          <= 32'h0;
		vofs          <= 32'h0;
		hstart        <= 32'h0;
		vconv_end     <= 32'h0;
		crt_ctrl      <= 32'h0;
		crt_test      <= 32'h0;
		gpio_cfg      <= 32'h0;
		gpio_out      <= 32'h0;
		gpio_int_ctrl <= 32'h0;
		int_enables   <= 32'h0;
		heb           <= 32'h0;
		for (int i = 0; i < 15; i++) sw[i] <= 32'h0;
	end
end

assign rdata = rd_clut ? {clut_q, 8'h00} : rq;

endmodule
