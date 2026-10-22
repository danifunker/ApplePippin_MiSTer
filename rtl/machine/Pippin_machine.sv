//============================================================================
//
//  Pippin - the machine around the CPU
//  The Apple/Bandai Pippin (dingusppc's machinepippin.cpp, MAME's
//  apple/pippin.cpp): the address map, the device stubs, the time base
//
//  Sits on the CPU's side of the clock crossing, in the CPU's clock. It takes
//  the CPU's memory port, decodes the address, answers device accesses
//  itself and passes RAM and ROM accesses on, as SDRAM offsets, to
//  DSPPC603_memcdc. The protocol is the CPU's port's on both sides: one
//  request at a time, req held until ack, a 32-byte line or one word with
//  byte enables (the lowest address in bits 255-224 or 31-24).
//
//  The map (dingusppc's machinepippin.cpp and the devices it builds; MAME's
//  pippin.cpp:105-150 agrees):
//
//    00000000  RAM                    Aspen's four banks, one per 16 MB: 4 MB
//                                     and 1 MB on the board, two expansion
//                                     slots (ram_mb 5, 13 or 21: 8 MB in bank
//                                     2, then 3); each with Aspen's 4 KB
//                                     windows onto it, which the ROM's memory
//                                     sizing probes (aspen.cpp:154-205): at
//                                     + C01000 always, + C00000 below 16 MB,
//                                     + 400000 below 8 MB, each onto the
//                                     bank's DRAM row and column wrap
//                                     (1 MB: + 0; 4 MB: + 200; 8 MB: + 600).
//                                     SDRAM offset = the physical address, so
//                                     5 MB fits a 32 MB module, 13 and 21 MB
//                                     need 64 MB
//    40000000  save flash             Am29F010, 128 KB, a byte per word
//                                     (pippin.cpp:145, 158-166) -> Pippin_flash
//    F0000000  Taos's VRAM            1 MB: memory, through its own crossing
//                                     to the picture side (Pippin_video, the
//                                     VRAM in DDR3), big-endian
//    F0800000  Taos's registers       2 KB -> Pippin_taos
//    F1000000  Taos's colour table    1 KB -> Pippin_taos
//    F2000000  Aspen's PCI            16 MB: configuration space only
//                                     (bandit.cpp:336-350) -> Pippin_pcicfg
//    F3000000  Grand Central          128 KB, where the ROM sets its base
//                                     address register (CONFIG_ADDR 2810) ->
//                                     Pippin_gc
//    F8000000  Aspen's registers      2 KB, 32 registers repeated every 128
//                                     bytes (aspen.cpp:76-133) -> below
//    FFC00000  ROM                    4 MB (machinepippin.cpp:64); SDRAM offset
//                                     rom_at x 4 MB (the board's top 4 MB);
//                                     writes are ignored.
//                                     With boot_memtest, the 8 KB memory-test
//                                     program (Pippin_bootrom) mirrored over
//                                     it instead
//    F9000000  debug registers        not a Pippin device: 256 bytes where the
//                                     memory test reports (see below)
//
//  Anything else (RAM's holes included) reads as zeros and ignores writes. A device answers at
//  once, but for the VIA, which Grand Central paces to its 783,360 Hz clock:
//  an access waits for the clock's next edge and then half a cycle (MAME's
//  Grand Central, heathrow.cpp via_sync), 0.64-1.91 us. The 7600's ROM
//  counts on it: its Cuda timeouts are counts of VIA reads, and after each
//  byte it waits ten VIA reads for Cuda to take the byte's last bit. RAM
//  space beyond the installed memory reads 0, as measured on the 7300
//  (dingusppc reads all ones there).
//
//  Cuda (Pippin_cuda), the board's microcontroller, sits on the VIA's port
//  B and shift register, and holds the CPU in reset (cpu_reset) until its
//  firmware has powered the machine up, as on the 7600. Athens, the video's
//  clock generator, answers on Cuda's I2C lines (Pippin_athens).
//
//  Grand Central's DMA channels reach memory through one DMA port here
//  (rule 2): each access's line through the CPU's snoop port, then the
//  memory port, which the CPU and the DMA share (below). The internal SCSI
//  bus joins MESH (in Grand Central) and the disks (Pippin_scsidisk, IDs 0
//  and 1, the MiSTer's disk images through hps_io's block devices, whose
//  side runs in clk_v).
//
//  A line request to a device is eight word accesses to it, the lowest
//  address first, as a burst on the real bus would be: with data
//  translation off the 604 treats every address as cacheable, and the ROM
//  reads Hammerhead's CPU ID through the data cache (its fortieth
//  instruction, FFF03108, after enabling the cache at FFF03094).
//
//  Also made here: tb_tick for the CPU's time base and decrementer, at
//  TB_HZ on average from any CPU clock (the 604 counts every fourth bus
//  clock; the 7600's bus is 50 MHz), the VIA's 783,360 Hz clock, the
//  ESCC's RTxC at 3,686,400 Hz, the SCSI controllers' 25 MHz (MESH's
//  delays and selection timeout, Curio's chip clock), a microsecond tick
//  (the SWIM3) and twice 44,100 Hz (AWACS's frames, whose samples come
//  out as snd_left and snd_right); all by phase accumulation. ext_irq is Grand
//  Central's interrupt output. The ESCC's channel A, the modem port, comes
//  out as modem_txd and modem_rxd; Grand Central's NVRAM can be written
//  from outside through nv_ld_* (an image loaded while reset is held).
//
//============================================================================

module Pippin_machine
#(
	parameter int unsigned CPU_HZ   = 66_000_000,
	parameter int unsigned CPU_HZ_FAST = CPU_HZ,    // the clock with cpu_fast
	parameter int unsigned TB_HZ    = 16_500_000,     // the 603's time base: a quarter of its 66 MHz bus
	parameter int unsigned VIA_HZ   = 783_360,
	parameter int unsigned RTXC_HZ  = 3_686_400,     // the ESCC's RTxC clock
	parameter int unsigned SCSI_HZ  = 25_000_000,    // MESH's time base and Curio's clock (below CPU_HZ)
	parameter int unsigned CUDA_FAST_BOOT = 0,      // 1: the test bench's (Pippin_cuda FAST_BOOT)
	parameter int unsigned SOUND_IN_DMA = 1,        // 0: DMA channel 9 (sound in) its registers alone
	parameter int unsigned INT_REPORT = 1,          // Pippin_gc INT_REPORT: an access leaving a device's line high is an event (68k mode)
	parameter int unsigned TRACE_INT = 1,           // 1: the trace takes Grand Central's interrupt and the VIA's register writes
	parameter int unsigned TRACE_FL = 0,            // 1: the trace takes the save flash's CPU accesses and its image's load and save (kind 4)
	parameter int unsigned TRACE_RAM = 0,           // 1: the trace takes every uncached word access to the RAM lines below
	parameter logic [31:0] TRACE_RAM_A  = 32'h00081C60,   // TRACE_RAM: an address in the line (the board's TMTask, cap2-cap5)
	parameter logic [31:0] TRACE_RAM_A2 = 32'h00081AC0    // ... and a second line (the bench's TMTask, rep18)
)
(
	input  logic         clk,
	input  logic         cpu_fast,                  // clk is CPU_HZ_FAST, else CPU_HZ (changes only in reset)
	input  logic         reset,
	input  logic [7:0]   ram_mb,                    // installed RAM, at most 4 x rom_at
	input  logic [4:0]   rom_at,                    // the ROM's SDRAM offset in 4 MB (quasi-static)
	input  logic         boot_memtest,              // run the memory test in place of the ROM

	// the CPU's memory port
	input  logic         c_req,
	input  logic         c_we,
	input  logic         c_line,
	input  logic [31:2]  c_addr,
	input  logic [3:0]   c_be,
	input  logic [255:0] c_wdata,
	output logic         c_ack,
	output logic [255:0] c_rdata,

	// RAM and ROM, by SDRAM offset, to DSPPC603_memcdc
	output logic         m_req,
	output logic         m_we,
	output logic         m_line,
	output logic [31:2]  m_addr,
	output logic [3:0]   m_be,
	output logic [255:0] m_wdata,
	input  logic         m_ack,
	input  logic [255:0] m_rdata,

	output logic         ext_irq,
	output logic [127:0] int_dbg,         // Grand Central's interrupt state, for the trace (kind 16)
	output logic         tb_tick,
	output logic         cpu_reset,                 // Cuda holds the CPU in reset
	output logic         power_wake,                // off, and the power key pressed: reset the machine

	// the CPU's snoop port: a DMA access's line, presented before it goes to memory
	output logic         snoop_req,
	output logic         snoop_we,
	output logic [31:5]  snoop_addr,
	input  logic         snoop_ack,

	// the SCSI targets' images: hps_io's block devices (0, 1 the disks, 3 the
	// Toolbox, 4 the CD-ROM, 5 the CD changer; 2 not driven here), in clk_v
	input  logic [5:0]   img_mounted,
	input  logic [63:0]  img_size,
	input  logic         img_readonly,
	output logic [31:0]  sd_lba,
	output logic [5:0]   sd_rd,
	output logic [5:0]   sd_wr,
	output logic [5:0]   sd_blk_cnt,
	input  logic [5:0]   sd_ack,
	input  logic [13:0]  sd_buff_addr,
	input  logic [7:0]   sd_buff_dout,
	output logic [7:0]   sd_buff_din,
	input  logic         sd_buff_wr,
	output logic         disk_busy,
	output logic signed [15:0] cd_left,  // the CD's audio, in this clock
	output logic signed [15:0] cd_right,
	// the floppy disk's image: hps_io's slot 6 (the other signals shared), in clk_v
	input  logic         fd_mounted,
	output logic [31:0]  fd_lba,
	output logic         fd_rd,
	output logic [5:0]   fd_blk_cnt,
	input  logic         fd_ack,

	// a DMA write to RAM, for the test bench (its reference has no DMA): one
	// clock, as it goes into memory
	output logic         dma_wr,
	output logic         dma_wr_line,
	output logic [31:2]  dma_wr_addr,
	output logic [3:0]   dma_wr_be,
	output logic [255:0] dma_wr_data,

	// the modem port (the ESCC's channel A), 1 when idle; its CTS and RTS
	output logic         modem_txd,
	input  logic         modem_rxd,
	input  logic         modem_cts,
	output logic         modem_rts,
	output logic         modem_midi,                // the modem port at MIDI's rate (the MT32-pi takes it then)

	// the network bridge (Pippin_enet): MACE's side
	input  logic         net_link,
	output logic         net_tx_we,
	output logic [7:0]   net_tx_wa,
	output logic [63:0]  net_tx_wd,
	output logic         net_tx_go,
	output logic [10:0]  net_tx_len,
	input  logic         net_tx_done,
	output logic [7:0]   net_rx_ra,
	input  logic [63:0]  net_rx_q,
	input  logic         net_rx_avail,
	input  logic [10:0]  net_rx_len,
	output logic         net_rx_done,
	input  logic [47:0]  net_mac,
	input  logic         net_mac_ok,

	// the sound AWACS plays (signed, changing at its frame rate)
	output logic [15:0]  snd_left,
	output logic [15:0]  snd_right,
	output logic         snd_frame,     // one clock a frame (the samples change the clock after)

	// Grand Central's NVRAM written from outside, a byte a cycle, while
	// the machine is held in reset
	input  logic         nv_ld_we,
	input  logic         nv_ld_re,                  // ... or read from outside (Pippin_gc)
	input  logic [12:0]  nv_ld_addr,
	input  logic [7:0]   nv_ld_data,
	output logic         nv_ld_rack,
	output logic [7:0]   nv_ld_q,
	output logic         nv_wr_cpu,                 // the CPU wrote the NVRAM

	// the save flash's image, loaded and saved from outside (Pippin_flash)
	input  logic         fl_ld_we,
	input  logic         fl_ld_re,
	input  logic [16:0]  fl_ld_addr,
	input  logic [7:0]   fl_ld_data,
	output logic [7:0]   fl_ld_q,
	output logic         fl_changed,

	// the console's video switch (Taos's GPIO: 5 NTSC, 6 VGA, 3 PAL) and the CD tray
	input  logic [2:0]   mon_id,
	input  logic         tray_closed,

	// the keyboard, the mouse and the game controller, as hps_io gives them (Pippin_adb)
	input  logic [10:0]  ps2_key,
	input  logic [24:0]  ps2_mouse,
	input  logic [51:0]  joy,

	// the date and time for Cuda's clock: seconds since 1904, steady in this clock
	input  logic         clock_ok,
	input  logic [31:0]  clock_secs,

	// the VRAM, by VRAM byte address, to its clock crossing (the CPU port's
	// protocol, VRAM's byte order)
	output logic         v_req,
	output logic         v_we,
	output logic         v_line,
	output logic [21:2]  v_addr,
	output logic [3:0]   v_be,
	output logic [255:0] v_wdata,
	input  logic         v_ack,
	input  logic [255:0] v_rdata,

	// Taos's registers, to the picture side (Pippin_taosvideo), standing
	// still while they are used; its vertical blanking back (asynchronous)
	output logic         taos_on,
	output logic [479:0] taos_swatch,
	output logic [31:0]  taos_fbb,
	output logic [31:0]  taos_roww,
	output logic         taos_c16,
	output logic [7:0]   athens_d2,
	output logic [7:0]   athens_n2,
	output logic [7:0]   athens_p2,
	output logic         athens_set,                // the dot clock's Athens (28) has been programmed
	input  logic         vbl,
	input  logic         clk_v,
	input  logic [23:0]  clut_index,
	output logic [23:0]  clut_rgb,

	// the debug registers, for the debug readout
	output logic [31:0]  dbg_status,
	output logic [31:0]  dbg_passes,
	output logic [31:0]  dbg_errors,
	output logic [31:0]  dbg_first,

	// the records for Pippin_trace; tr_mesh adds MESH's and channel A's accesses
	input  logic         tr_mesh,
	output logic         tr_ev,
	output logic [255:0] tr_rec
);

import Pippin_pkg::*;

// ---- RAM: Aspen's banks ------------------------------------------------------------------
// The bank sizes in MB from the installed RAM: 4 + 1 on the board, 8 in each expansion slot
function automatic logic [4:0] bank_mb(input logic [1:0] n, input logic [7:0] mb);
	case (n)
		2'd0:    bank_mb = (mb >= 8'd4) ? 5'd4 : 5'(mb);
		2'd1:    bank_mb = (mb >= 8'd5) ? 5'd1 : 5'd0;
		2'd2:    bank_mb = (mb >= 8'd13) ? 5'd8 : 5'd0;
		default: bank_mb = (mb >= 8'd21) ? 5'd8 : 5'd0;
	endcase
endfunction
// {hit, SDRAM byte offset} of a physical address
function automatic logic [27:0] ram_map(input logic [31:0] x, input logic [7:0] mb);
	logic [4:0]  sz;
	logic        direct, w400, wc00, wc01;
	logic [11:0] wrap;
	sz     = bank_mb(x[25:24], mb);
	direct = (sz != 5'd0) && ({4'd0, x[23:20]} < {3'd0, sz});
	w400   = (sz != 5'd0) && (sz < 5'd8)  && (x[23:12] == 12'h400);
	wc00   = (sz != 5'd0) && (sz < 5'd16) && (x[23:12] == 12'hC00);
	wc01   = (sz != 5'd0) && (x[23:12] == 12'hC01);
	wrap   = (sz == 5'd1) ? 12'h000 : (sz == 5'd4) ? 12'h200 : 12'h600;
	ram_map[27]   = (x[31:26] == 6'd0) && (direct | w400 | wc00 | wc01);
	ram_map[26:0] = direct ? {1'b0, x[25:0]} : {1'b0, x[25:24], 12'h000, 12'(wrap + {1'b0, x[11:0]})};
endfunction

// ---- decode -----------------------------------------------------------------------------
wire [31:0] a       = {c_addr, 2'b00};
wire [27:0] a_map   = ram_map(a, ram_mb);
wire        is_ram  = a_map[27];
wire        is_rom  = a[31:22] == 10'h3FF;
wire        to_mem  = is_ram | (is_rom & ~c_we & ~boot_memtest);

// ---- the request, registered, for the devices and the VRAM --------------------------------
// The devices' and the VRAM's requests are decided from a registered copy of
// the CPU's port: its address and store data come straight off its caches'
// RAMs and through the RAM map, and deciding their take and the enables of
// their 300-odd registers from that was the slowest family at 100 MHz
// (2026-10-13). The memory path keeps the live decode. The copy stands for
// the request still up (q_valid: not answered in the cycle it was taken),
// so a request made right after an answer waits a cycle for its copy.
logic         q_valid, q_we, q_line, q_to_mem;
logic [31:2]  q_addr;
logic [3:0]   q_be;
logic [255:0] q_wdata;
always_ff @(posedge clk) begin
	q_valid  <= c_req & ~c_ack & ~reset;
	q_we     <= c_we;
	q_line   <= c_line;
	q_addr   <= c_addr;
	q_be     <= c_be;
	q_wdata  <= c_wdata;
	q_to_mem <= to_mem;                            // the live decode's answer for the same request (a RAM map instance less)
end
wire [31:0] qa        = {q_addr, 2'b00};
wire        q_is_rom  = qa[31:22] == 10'h3FF;
wire        q_is_boot = q_is_rom & ~q_we & boot_memtest;
wire        q_is_dbg  = qa[31:8] == 24'hF90000;
wire        q_is_vram = qa[31:20] == 12'hF00;                 // Taos's VRAM, F0000000-F00FFFFF
wire        q_is_taos = qa[31:11] == 21'h1E1000;              // F0800000-F08007FF
wire        q_is_clut = qa[31:10] == 22'h3C4000;              // F1000000-F10003FF
wire        q_is_pci  = qa[31:24] == 8'hF2;
wire        q_is_gc   = qa[31:17] == 15'h7980;                // F3000000-F301FFFF
wire        q_is_asp  = qa[31:11] == 21'h1F0000;              // F8000000-F80007FF
wire        q_is_via  = q_is_gc && qa[16:13] == 4'b1011;      // F3016000-F3017FFF
wire        q_is_fl   = qa[31:19] == 13'h0800;                // 40000000-4007FFFF
wire        q_req     = q_valid & c_req;

// ---- RAM and ROM: the CPU's accesses and the DMA channels', one port ------------------------
// The crossing captures a request and holds it, and ignores it in the cycle
// of its own acknowledge, exactly as the CPU's port behaves. Two masters
// share it (rule 2): the CPU's accesses go straight through when the port
// is free; a DMA access (Grand Central's DMA port, dm_*) first presents its
// line to the CPU's snoop port (the caches write it back if it is dirty,
// and drop it if the DMA writes), then takes the port as soon as it is
// free, before any new CPU access. The CPU's accesses go on during the
// snoop (the write-back is one of them, and a cache may have to finish a
// fill before it can answer), so a cache could fetch the line again after
// its part of the snoop and before the DMA writes it: a DMA write is
// therefore followed by a second snoop of the line, which drops any such
// copy. (A store into that copy in those few clocks would be written back
// over the DMA's bytes: Pippin_stubs.md.) A DMA access outside RAM and the
// ROM reads 0 and writes nothing, at once.
logic         gdm_req, gdm_we, gdm_line, gdm_ack;
logic [31:2]  gdm_addr;
logic [3:0]   gdm_be;
logic [255:0] gdm_wdata, gdm_rdata;
wire  [31:0]  da      = {gdm_addr, 2'b00};
wire  [27:0]  da_map  = ram_map(da, ram_mb);
wire          d_ram   = da_map[27];
wire          d_rom   = da[31:22] == 10'h3FF;
wire          d_mem   = d_ram | (d_rom & ~gdm_we);

typedef enum logic [2:0] {DQ_IDLE, DQ_SNOOP, DQ_MEM, DQ_SNOOP2, DQ_DONE} dq_t;
dq_t          dq;
logic         own_cpu, own_dma;                    // whose request the crossing holds
logic         snoop_gap;                           // a clock between the two snoops (the request drops)
wire          port_free = ~own_cpu & ~own_dma;
wire          grant_dma = port_free & (dq == DQ_MEM);
wire          grant_cpu = port_free & ~grant_dma & (dq != DQ_MEM) & c_req & to_mem;
wire          pres_dma  = own_dma | grant_dma;
wire          snoop_skip = reset | cpu_reset;     // a CPU held in reset has nothing to give back
// the board's devices (the bridges, Grand Central and all behind it, the
// Control video, the disks' bus side) are reset with the CPU, as a
// restart (Cuda's PC3) resets a 7600's whole board; Cuda, the ADB devices,
// Athens and the NVRAM's contents keep theirs
wire          board_reset = reset | cpu_reset;

assign snoop_req  = (dq == DQ_SNOOP || (dq == DQ_SNOOP2 && !snoop_gap)) && !snoop_skip;
assign snoop_we   = gdm_we;
assign snoop_addr = gdm_addr[31:5];

assign m_req   = pres_dma | ((own_cpu | grant_cpu) & c_req & to_mem);
assign m_we    = pres_dma ? gdm_we   : c_we;
assign m_line  = pres_dma ? gdm_line : c_line;
assign m_addr  = pres_dma ? (d_rom ? {5'd0, rom_at, da[21:2]} : {5'd0, da_map[26:2]})
                          : (is_rom ? {5'd0, rom_at, a[21:2]} : {5'd0, a_map[26:2]});
assign m_be    = pres_dma ? gdm_be   : c_be;
assign m_wdata = pres_dma ? gdm_wdata : c_wdata;
wire   cpu_m_ack = m_ack & own_cpu;

assign dma_wr      = m_ack & own_dma & gdm_we & d_ram;
assign dma_wr_line = gdm_line;
assign dma_wr_addr = gdm_addr;
assign dma_wr_be   = gdm_be;
assign dma_wr_data = gdm_wdata;

always_ff @(posedge clk) begin
	gdm_ack <= 1'b0;
	if (m_ack) begin
		own_cpu <= 1'b0;
		own_dma <= 1'b0;
	end
	else begin
		if (grant_cpu) own_cpu <= 1'b1;
		if (grant_dma) own_dma <= 1'b1;
	end
	snoop_gap <= 1'b0;
	case (dq)
		DQ_IDLE: if (gdm_req && !gdm_ack) begin
			if (!d_mem) begin                          // nothing there: 0, at once
				gdm_rdata <= 256'h0;
				gdm_ack   <= 1'b1;
				dq        <= DQ_DONE;
			end
			else dq <= DQ_SNOOP;
		end
		DQ_SNOOP: if (snoop_ack || snoop_skip) dq <= DQ_MEM;
		DQ_MEM: if (m_ack && own_dma) begin
			gdm_rdata <= m_rdata;
			if (gdm_we) begin                          // a write: the line snooped again
				snoop_gap <= 1'b1;
				dq        <= DQ_SNOOP2;
			end
			else begin
				gdm_ack <= 1'b1;
				dq      <= DQ_DONE;
			end
		end
		DQ_SNOOP2: if (!snoop_gap && (snoop_ack || snoop_skip)) begin
			gdm_ack <= 1'b1;
			dq      <= DQ_DONE;
		end
		default: dq <= DQ_IDLE;                        // the acknowledge's cycle
	endcase
	if (reset) begin
		dq        <= DQ_IDLE;
		own_cpu   <= 1'b0;
		own_dma   <= 1'b0;
		snoop_gap <= 1'b0;
		gdm_ack   <= 1'b0;
	end
end

// The VRAM is memory, not a device: it goes to the picture side through a
// crossing of its own, as RAM goes to the SDRAM. Taos's 1 MB, big-endian, as
// it is (dingusppc's taos.h:39-41; the ROM uses it as scratch before video).

assign v_req   = q_req & q_is_vram;
assign v_we    = q_we;
assign v_line  = q_line;
assign v_addr  = {2'b00, qa[19:2]};
assign v_be    = q_be;
assign v_wdata = q_wdata;

// Everything else is answered here: a word two cycles after it is seen, a line
// as eight words presented on consecutive cycles, answered after the last.
// The request goes to the devices from a register (p_*): the CPU's address and
// store data come straight off its caches' RAMs, and the decode and the
// devices' own muxes behind them set the clock before (build 28: -1.5 ns).
logic       dev_ack, dev_busy;
logic [3:0] dev_cnt;                               // cycles since the request was taken
logic [7:0] dev_sel_q;                             // which block answers: flash, Taos, its table, PCI, GC, Aspen, debug, boot
logic       p_sel, pq_sel;                         // a word is before the devices in this cycle; was in the last
logic [2:0] p_k, pq_k;                             // ... this one of the line
logic [31:2] p_a;
logic [3:0]  p_be;
logic [31:0] p_wd;
logic        p_we;
logic [7:0]  p_dev;
logic [31:0] line_buf [8];

// a word access to the VIA waits for the VIA's clock: its next edge, then half
// a cycle (a line goes at once, as to any device)
localparam int unsigned VIA_HALF = CPU_HZ / VIA_HZ / 2, VIA_HALF_FAST = CPU_HZ_FAST / VIA_HZ / 2;
logic [1:0] vw;                                    // 0 idle; 1 to the edge; 2 the half cycle
logic [7:0] vw_cnt;
wire  via_wait = q_is_via & ~q_line;
wire  via_go   = vw == 2'd2 && vw_cnt == 8'd0;
wire  dev_take = q_req & ~q_to_mem & ~q_is_vram & ~dev_busy & ~dev_ack & (~via_wait | via_go);
// the word presented to the devices in this cycle
wire        present = dev_take | (dev_busy & q_line & dev_cnt <= 4'd7);
wire  [2:0] pres_k  = dev_take ? 3'd0 : dev_cnt[2:0];
wire [31:2] dev_a   = q_line ? {q_addr[31:5], pres_k} : q_addr;
wire  [3:0] dev_be  = q_line ? 4'hF : q_be;
wire [31:0] dev_wd  = q_line ? q_wdata[255 - 32 * pres_k -: 32] : q_wdata[31:0];
always_ff @(posedge clk) begin
	p_sel <= present & ~reset;
	p_k   <= pres_k;
	p_a   <= dev_a;
	p_be  <= dev_be;
	p_wd  <= dev_wd;
	p_we  <= q_we;
	p_dev <= {q_is_fl, q_is_taos, q_is_clut, q_is_pci, q_is_gc, q_is_asp, q_is_dbg, q_is_boot};
end

// ---- the time base, the VIA's clock, the ESCC's and the SCSI controllers', the microsecond, ----
// ---- AWACS's twice 44,100 Hz ----
// Each rate R by phase accumulation: past the clock less R, the clock less R comes off,
// else R goes on; the clock less R registered (cpu_fast changes only in reset)
logic [31:0] tb_acc, via_acc, rtxc_acc, scsi_acc, us_acc, snd_acc;
logic        via_tick, rtxc_tick, scsi_tick, us_tick, snd_tick;
logic [31:0] tb_d, via_d, rtxc_d, scsi_d, us_d, snd_d;
always_ff @(posedge clk) begin
	snd_d  <= (cpu_fast ? CPU_HZ_FAST : CPU_HZ) - 32'd88_200;
	us_d   <= (cpu_fast ? CPU_HZ_FAST : CPU_HZ) - 32'd1_000_000;
	scsi_d <= (cpu_fast ? CPU_HZ_FAST : CPU_HZ) - SCSI_HZ;
	rtxc_d <= (cpu_fast ? CPU_HZ_FAST : CPU_HZ) - RTXC_HZ;
	tb_d   <= (cpu_fast ? CPU_HZ_FAST : CPU_HZ) - TB_HZ;
	via_d  <= (cpu_fast ? CPU_HZ_FAST : CPU_HZ) - VIA_HZ;
end
always_ff @(posedge clk) begin
	tb_tick   <= 1'b0;
	via_tick  <= 1'b0;
	rtxc_tick <= 1'b0;
	scsi_tick <= 1'b0;
	us_tick   <= 1'b0;
	snd_tick  <= 1'b0;
	if (snd_acc >= snd_d) begin
		snd_acc  <= snd_acc - snd_d;
		snd_tick <= 1'b1;
	end
	else snd_acc <= snd_acc + 32'd88_200;
	if (us_acc >= us_d) begin
		us_acc  <= us_acc - us_d;
		us_tick <= 1'b1;
	end
	else us_acc <= us_acc + 32'd1_000_000;
	if (scsi_acc >= scsi_d) begin
		scsi_acc  <= scsi_acc - scsi_d;
		scsi_tick <= 1'b1;
	end
	else scsi_acc <= scsi_acc + SCSI_HZ;
	if (rtxc_acc >= rtxc_d) begin
		rtxc_acc  <= rtxc_acc - rtxc_d;
		rtxc_tick <= 1'b1;
	end
	else rtxc_acc <= rtxc_acc + RTXC_HZ;
	if (tb_acc >= tb_d) begin
		tb_acc  <= tb_acc - tb_d;
		tb_tick <= 1'b1;
	end
	else tb_acc <= tb_acc + TB_HZ;
	if (via_acc >= via_d) begin
		via_acc  <= via_acc - via_d;
		via_tick <= 1'b1;
	end
	else via_acc <= via_acc + VIA_HZ;
	if (reset) begin
		tb_acc    <= 32'h0;
		via_acc   <= 32'h0;
		rtxc_acc  <= 32'h0;
		scsi_acc  <= 32'h0;
		us_acc    <= 32'h0;
		snd_acc   <= 32'h0;
		snd_tick  <= 1'b0;
		tb_tick   <= 1'b0;
		via_tick  <= 1'b0;
		rtxc_tick <= 1'b0;
		scsi_tick <= 1'b0;
		us_tick   <= 1'b0;
	end
end

always_ff @(posedge clk) begin
	case (vw)
		2'd0: if (q_req & ~q_to_mem & via_wait & ~dev_busy & ~dev_ack) vw <= 2'd1;
		2'd1: if (via_tick) begin vw <= 2'd2; vw_cnt <= cpu_fast ? 8'(VIA_HALF_FAST - 1) : 8'(VIA_HALF - 1); end
		default: begin
			if (vw_cnt != 8'd0) vw_cnt <= vw_cnt - 8'd1;
			else vw <= 2'd0;                        // via_go: the access is presented now
		end
	endcase
	if (reset) begin
		vw     <= 2'd0;
		vw_cnt <= 8'd0;
	end
end

// ---- the devices ------------------------------------------------------------------------
logic [31:0] pci_rdata, gc_rdata;
logic        gc_irq;
logic        cuda_nmi;                     // Cuda's NMI (PC2), Grand Central's source 14

logic [31:12] pci_unused_regs;            // (Chaos's outputs: Control's BARs)
logic [31:26] pci_unused_vram;
Pippin_pcicfg #(.BRIDGE(2)) aspen_pci (
	.clk, .reset(board_reset),
	.sel(p_sel & p_dev[4]), .we(p_we), .addr(p_a[23:2]), .be(p_be), .wdata(p_wd),
	.rdata(pci_rdata), .ctl_regs_base(pci_unused_regs), .ctl_vram_base(pci_unused_vram)
);

// ---- Taos: its registers and colour table -------------------------------------------------
logic [31:0] taos_rdata, taos_crt_ctrl;
logic [1:0]  taos_video_mode;
logic        taos_vsync;
logic [7:0]  dac_cr, dbl_buf_cr;          // (RaDACal's, in Grand Central: not the Pippin's)
logic [15:0] cursor_x;
logic [191:0] cursor_clut;
logic [2:0]  vbl_s;

Pippin_taos taos (
	.clk, .reset(board_reset),
	.sel(p_sel & p_dev[6]), .clut_sel(p_sel & p_dev[5]), .we(p_we), .addr(p_a[10:2]), .be(p_be), .wdata(p_wd),
	.rdata(taos_rdata), .mon_id, .tray_closed, .vsync(taos_vsync),
	.fb_base(taos_fbb), .row_words(taos_roww), .color16(taos_c16), .video_mode(taos_video_mode),
	.crt_ctrl(taos_crt_ctrl), .swatch(taos_swatch),
	.clk_v, .v_index_r(clut_index[23:16]), .v_index_g(clut_index[15:8]), .v_index_b(clut_index[7:0]),
	.v_rgb(clut_rgb)
);
// the vertical sync input (GPIO 6, active low: 0 in the blanking, as MAME has it), from the
// scan-out's clock
always_ff @(posedge clk) vbl_s <= {vbl_s[1:0], vbl};
assign taos_vsync = ~vbl_s[2];
assign taos_on    = taos_crt_ctrl[24];

logic cuda_treq, cuda_cb1, cuda_cb2_oe, cuda_cb2_out;
logic via_tip, via_byteack, via_cb2_oe, via_cb2_out;
wire  cb2_line = (cuda_cb2_oe ? cuda_cb2_out : 1'b1) & (via_cb2_oe ? via_cb2_out : 1'b1);

// the internal SCSI bus: MESH's lines and the disks', wired together (each side
// seeing the other's a clock later)
logic       mesh_rst, mesh_bsy, mesh_sel, mesh_atn, mesh_ack, mesh_req, mesh_msg, mesh_cd, mesh_io;
logic [7:0] mesh_db;
logic       t_bsy, t_req, t_msg, t_cd, t_io;
logic [7:0] t_db;
logic       scsi_rst, scsi_bsy, scsi_sel, scsi_atn, scsi_ack, scsi_req, scsi_msg, scsi_cd, scsi_io;
logic [7:0] scsi_db;
logic       b_rst, b_bsy, b_sel, b_atn, b_ack;
logic [7:0] b_db;
Pippin_scsibus scsibus (.clk, .mesh_rst, .mesh_bsy, .mesh_sel, .mesh_atn, .mesh_ack, .mesh_req, .mesh_msg,
	.mesh_cd, .mesh_io, .mesh_db, .t_bsy, .t_req, .t_msg, .t_cd, .t_io, .t_db,
	.scsi_rst, .scsi_bsy, .scsi_sel, .scsi_atn, .scsi_ack, .scsi_req, .scsi_msg, .scsi_cd, .scsi_io, .scsi_db,
	.b_rst, .b_bsy, .b_sel, .b_atn, .b_ack, .b_db);

logic         dfin;
logic [3:0]   dfin_ch;
logic [1:0]   dfin_type;
logic [127:0] dfin_info;
logic         itr_ev, itr8_ev;
logic [7:0]   itr8_st;
logic         fd_m_t, fd_m_ok, fd_m_dc42, fd_rq_t, fd_dn_t;
logic [1:0]   fd_m_fmt;
logic [11:0]  fd_rq_lba;
logic [9:0]   fd_ra;
logic [7:0]   fd_q;
logic [7:0]   itr_st;

Pippin_gc #(.SCSI_HZ(SCSI_HZ), .SOUND_IN_DMA(SOUND_IN_DMA), .INT_REPORT(INT_REPORT)) gc (
	.clk, .reset(board_reset), .via_tick, .rtxc_tick, .scsi_tick, .us_tick, .snd_tick,
	.sel(p_sel & p_dev[3]), .we(p_we), .addr(p_a[16:2]), .be(p_be), .wdata(p_wd),
	.rdata(gc_rdata), .irq(gc_irq), .int_dbg,
	.cuda_treq, .cuda_cb1, .cb2(cb2_line), .via_tip, .via_byteack, .via_cb2_oe, .via_cb2_out,
	.modem_txd, .modem_rxd, .modem_cts, .modem_rts, .modem_midi,
	.net_link, .net_tx_we, .net_tx_wa, .net_tx_wd, .net_tx_go, .net_tx_len, .net_tx_done,
	.net_rx_ra, .net_rx_q, .net_rx_avail, .net_rx_len, .net_rx_done, .net_mac, .net_mac_ok,
	.nv_ld_we, .nv_ld_re, .nv_ld_addr, .nv_ld_data, .nv_ld_rack, .nv_ld_q, .nv_wr_cpu,
	.ctl_irq(1'b0), .nmi(cuda_nmi),
	.mesh_rst, .mesh_bsy, .mesh_sel, .mesh_atn, .mesh_ack, .mesh_req, .mesh_msg, .mesh_cd, .mesh_io, .mesh_db,
	.scsi_rst, .scsi_bsy, .scsi_sel, .scsi_atn, .scsi_ack, .scsi_req, .scsi_msg, .scsi_cd, .scsi_io, .scsi_db,
	.dm_req(gdm_req), .dm_we(gdm_we), .dm_line(gdm_line), .dm_addr(gdm_addr), .dm_be(gdm_be),
	.dm_wdata(gdm_wdata), .dm_ack(gdm_ack), .dm_rdata(gdm_rdata),
	.snd_left, .snd_right, .snd_frame,
	.dac_cr, .dbl_buf_cr, .cursor_x, .cursor_clut, .clk_v, .clut_index,
	/* verilator lint_off PINCONNECTEMPTY */
	.clut_rgb(),
	/* verilator lint_on PINCONNECTEMPTY */
	.dfin, .dfin_ch, .dfin_type, .dfin_info, .itr_ev, .itr_st, .itr8_ev, .itr8_st,
	.fd_m_t, .fd_m_ok, .fd_m_fmt, .fd_m_dc42, .fd_rq_t, .fd_rq_lba, .fd_dn_t, .fd_ra, .fd_q
);

assign ext_irq = gc_irq;

// ---- the internal bus's targets: disks at IDs 0 and 1, the CD-ROM at 3 (hps_io's slots) ----------
logic         sd_tr_ev;
logic [255:0] sd_tr_rec;

Pippin_scsidisk #(.CLK_HZ(CPU_HZ), .CLK_HZ_FAST(CPU_HZ_FAST)) disks (
	.clk, .cpu_fast, .reset(board_reset),
	.t_bsy, .t_req, .t_msg, .t_cd, .t_io, .t_db,
	.b_rst, .b_bsy, .b_sel, .b_atn, .b_ack, .b_db,
	.clk_h(clk_v), .img_mounted, .img_size, .img_readonly,
	.sd_lba, .sd_rd, .sd_wr, .sd_blk_cnt, .sd_ack, .sd_buff_addr, .sd_buff_dout, .sd_buff_din, .sd_buff_wr,
	.busy(disk_busy), .cd_left, .cd_right, .tr_ev(sd_tr_ev), .tr_rec(sd_tr_rec)
);

// ---- the floppy disk's image (SWIM3's, in Grand Central) ---------------------------------------
Pippin_fdblk fdblk (
	.clk_m(clk_v), .reset_m(1'b0),
	.img_mounted(fd_mounted), .img_size, .img_readonly,
	.sd_lba(fd_lba), .sd_rd(fd_rd), .sd_blk_cnt(fd_blk_cnt), .sd_ack(fd_ack),
	.sd_buff_addr, .sd_buff_dout, .sd_buff_wr,
	.m_t(fd_m_t), .m_ok(fd_m_ok), .m_fmt(fd_m_fmt), .m_dc42(fd_m_dc42),
	/* verilator lint_off PINCONNECTEMPTY */
	.m_ro(),
	/* verilator lint_on PINCONNECTEMPTY */
	.clk, .rq_t(fd_rq_t), .rq_lba(fd_rq_lba), .dn_t(fd_dn_t), .ra(fd_ra), .q(fd_q)
);

// ---- Cuda ------------------------------------------------------------------------------------
// On its ADB line: the keyboard and the mouse (Pippin_adb), from the PS/2
// inputs. On its I2C lines: Athens, the video's clock generator (address 28).
logic        adb_low, adb_dev_low, cuda_tick, iic_scl_low, iic_sda_low, athens_sda_low, athens2_sda_low;
wire         iic_scl = ~iic_scl_low;
wire         iic_sda = ~(iic_sda_low | athens_sda_low | athens2_sda_low);

logic        adb_tr_ev;
logic [31:0] adb_tr_info;

logic power_off, power_key;
always_ff @(posedge clk) begin
	if (power_off & power_key) power_wake <= 1'b1;
	if (reset) power_wake <= 1'b0;
end

Pippin_adb adb (
	.clk, .reset, .tick(cuda_tick), .host_low(adb_low), .dev_low(adb_dev_low),
	.ps2_key, .ps2_mouse, .joy, .power_key, .tr_ev(adb_tr_ev), .tr_info(adb_tr_info)
);

// The Pippin has two Athens Primes (343S1191; the board's photos, MAME's pippin.cpp:16). Which one
// makes Taos's dot clock follows the save flash (2026-10-22): the ROM probes the flash at
// FFF0533C (AMD's autoselect through the reversed data lines) and leaves E1 at F00DFFFA when it
// answers, E2 when not; with E1 the early set-up (FFF04818) programs the one at 29 to 14.375 MHz
// and nothing else, and Mac OS's Taos driver (FFE54F9C) talks to the one at 28 (I2C byte 50),
// with E2 to 29 (52). dingusppc has no flash (E2) and one Athens at 29; MAME forces E1 and does
// not use the pixel clock. Our flash answers as the real one, so the driver talks to 28: it was
// missing, the driver's first write went unacknowledged and it gave up. Acknowledged, it writes
// that one's P2_MUX2 = 02 and nothing else (the bench, 2026-10-22); Pippin_taosvideo's STD_DOT.
logic [7:0] athens29_d2, athens29_n2, athens29_p2;
logic       athens29_set;
Pippin_athens #(.ADDR(7'h29)) athens (
	.clk, .reset, .scl(iic_scl), .sda(iic_sda), .sda_low(athens_sda_low),
	.d2(athens29_d2), .n2(athens29_n2), .p2_mux2(athens29_p2), .written(athens29_set)
);
Pippin_athens #(.ADDR(7'h28)) athens2 (
	.clk, .reset, .scl(iic_scl), .sda(iic_sda), .sda_low(athens2_sda_low),
	.d2(athens_d2), .n2(athens_n2), .p2_mux2(athens_p2), .written(athens_set)
);

logic        cu_cen, cu_rd, cu_wr, cu_tr_valid, cu_tr_int, cu_cpi, cu_fast;
logic [12:0] cu_addr, cu_tr_pc;
logic [7:0]  cu_wdata, cu_rdata, cu_tr_op, cu_tr_a, cu_tr_x, cu_tr_sp, cu_tr_cc;

Pippin_cuda #(.CLK_HZ(CPU_HZ), .CLK_HZ_FAST(CPU_HZ_FAST), .FAST_BOOT(CUDA_FAST_BOOT != 0)) cuda (
	.clk, .cpu_fast, .reset,
	.via_tip, .via_byteack, .treq(cuda_treq), .cb1(cuda_cb1),
	.cb2_oe(cuda_cb2_oe), .cb2_out(cuda_cb2_out), .cb2(cb2_line),
	.cpu_reset, .power_off, .nmi(cuda_nmi), .clock_ok, .clock_secs,
	.adb_low, .adb_line(~(adb_low | adb_dev_low)), .tick(cuda_tick),
	.iic_scl_low, .iic_sda_low, .iic_scl, .iic_sda,
	.dbg_cen(cu_cen), .dbg_addr(cu_addr), .dbg_rd(cu_rd), .dbg_wr(cu_wr),
	.dbg_wdata(cu_wdata), .dbg_rdata(cu_rdata),
	.tr_valid(cu_tr_valid), .tr_int(cu_tr_int), .tr_pc(cu_tr_pc), .tr_op(cu_tr_op),
	.tr_a(cu_tr_a), .tr_x(cu_tr_x), .tr_sp(cu_tr_sp), .tr_cc(cu_tr_cc),
	.dbg_cpi(cu_cpi), .dbg_fast(cu_fast)
);

// ---- Aspen's registers (aspen.cpp:76-133, aspen.h) -------------------------------------------
// 32 word registers, repeated every 128 bytes. SYSTEM_ID (10) 40010000 and
// CHIP_REV (14) 01000000 are read-only; MEM_CONFIG (18) takes the bank
// sizes (the ROM writes AA000000 and then 40800000; the map above is fixed by
// ram_mb, as dingusppc's is) and reads 0, as in dingusppc; GPIO_ENABLE (34)
// keeps its top byte; GPIO_IN (30) and GPIO_OUT (38) read 0. A narrow read
// takes its bytes from the word (dingusppc returns the whole word for any
// size, which the CPU then truncates: a byte read of SYSTEM_ID gives 00
// there, 40 here, the bus's big-endian answer).
localparam logic [31:0] ASPEN_SYSTEM_ID = 32'h4001_0000;
localparam logic [31:0] ASPEN_CHIP_REV  = 32'h0100_0000;

logic [7:0]  asp_gpio_en;
logic [31:0] asp_mem_config;
logic [31:0] asp_rdata;
wire  [4:0]  asp_reg = p_a[6:2];

always_ff @(posedge clk) begin
	if (p_sel & p_dev[2]) begin
		case (asp_reg)
			5'd4:    asp_rdata <= ASPEN_SYSTEM_ID;
			5'd5:    asp_rdata <= ASPEN_CHIP_REV;
			5'd13:   asp_rdata <= {asp_gpio_en, 24'h0};
			default: asp_rdata <= 32'h0;
		endcase
		if (p_we & p_be[3]) begin
			if (asp_reg == 5'd6)  asp_mem_config <= p_wd;
			if (asp_reg == 5'd13) asp_gpio_en    <= p_wd[31:24];
		end
	end
	if (reset) begin
		asp_gpio_en    <= 8'h0;
		asp_mem_config <= 32'h0;
	end
end

// ---- the save flash (Am29F010 at 40000000) ------------------------------------------------------
logic [31:0] fl_rdata;
Pippin_flash flash (
	.clk, .reset(board_reset),
	.sel(p_sel & p_dev[7]), .we(p_we), .addr(p_a[18:2]), .be(p_be), .wdata(p_wd), .rdata(fl_rdata),
	.ld_we(fl_ld_we), .ld_re(fl_ld_re), .ld_addr(fl_ld_addr), .ld_data(fl_ld_data), .ld_q(fl_ld_q),
	.changed(fl_changed)
);

// ---- the memory-test boot program, in place of the ROM when the OSD asks ------------------
logic [31:0] boot_rdata;
Pippin_bootrom bootrom (.clk, .addr(p_a[12:2]), .q(boot_rdata));

// ---- the debug registers (not a 7600 device) -------------------------------------------
// The memory test (verilator/progs.py, memtest) writes its progress here and
// the debug readout shows it:
//   00 status   04 passes completed   08 errors   0C first error address
//   10 the word read there   14 the word expected   20 installed RAM in bytes (read only)
logic [31:0] dbg_reg [6];
logic [31:0] dbg_rdata;
wire  [3:0]  dbg_n = p_a[7:2] < 6'd6 ? p_a[5:2] : 4'd15;
always_ff @(posedge clk) begin
	if (p_sel & p_dev[1]) begin
		dbg_rdata <= p_a[7:2] == 6'h08 ? {4'h0, ram_mb, 20'h0} : dbg_n < 4'd6 ? dbg_reg[dbg_n[2:0]] : 32'h0;
		if (p_we & dbg_n < 4'd6) dbg_reg[dbg_n[2:0]] <= merge_be(dbg_reg[dbg_n[2:0]], p_wd, p_be);
	end
	if (reset) for (int i = 0; i < 6; i++) dbg_reg[i] <= 32'h0;
end
assign dbg_status = dbg_reg[0];
assign dbg_passes = dbg_reg[1];
assign dbg_errors = dbg_reg[2];
assign dbg_first  = dbg_reg[3];

// ---- the answer ---------------------------------------------------------------------------
always_ff @(posedge clk) begin
	if (dev_take) begin
		dev_busy  <= 1'b1;
		dev_cnt   <= 4'd1;
		dev_sel_q <= {q_is_fl, q_is_taos, q_is_clut, q_is_pci, q_is_gc, q_is_asp, q_is_dbg, q_is_boot};
	end
	else if (dev_busy) dev_cnt <= dev_cnt + 4'd1;
	// the answer is in line_buf the cycle after the devices' (a word's in
	// line_buf[0]): the CPU takes it from a register, not through the
	// devices' read mux
	dev_ack  <= pq_sel & (~q_line | pq_k == 3'd7);
	if (dev_ack) dev_busy <= 1'b0;
	pq_sel   <= p_sel;
	pq_k     <= p_k;
	if (pq_sel) line_buf[pq_k] <= dev_rdata;
	if (reset) begin
		dev_busy  <= 1'b0;
		dev_ack   <= 1'b0;
		dev_cnt   <= 4'd0;
		dev_sel_q <= 8'b0;
		pq_sel    <= 1'b0;
	end
end

logic [31:0] dev_rdata;
always_comb begin
	dev_rdata = 32'h0;
	if (dev_sel_q[7]) dev_rdata = fl_rdata;
	if (dev_sel_q[6] | dev_sel_q[5]) dev_rdata = taos_rdata;
	if (dev_sel_q[4]) dev_rdata = pci_rdata;
	if (dev_sel_q[3]) dev_rdata = gc_rdata;
	if (dev_sel_q[2]) dev_rdata = asp_rdata;
	if (dev_sel_q[1]) dev_rdata = dbg_rdata;
	if (dev_sel_q[0]) dev_rdata = boot_rdata;
end

// ---- the trace: the targets' records, and (kind 4) the CPU's accesses to MESH and its DMA channel ----
logic        bt_pend, bt_we;
logic [31:0] bt_a, bt_wd, bt_us = 32'd0;
logic [3:0]  bt_be;
logic [15:0] bt_div = 16'd0;
// MACE (F3011000-F30111FF) and its DMA channels 2 and 3 (F3008200, 8300); AWACS (F3014000)
// and its channel 8 (F3008800); MESH (F3018000) and its channel A (F3008A00) with tr_mesh.
// Not the interrupt registers: the NanoKernel reads and rewrites them thousands of times a second
// With TRACE_INT: the writes to Grand Central's interrupt registers (mask, clear) and to
// the VIA (its IFR and IER are how Mac OS takes and acknowledges its interrupts), for the
// interrupts that stop on the board after the ROM's ADB set-up (2026-10-19); SWIM3 (F3015000)
// and its DMA channel 1 (F3008100), reads and writes, for the floppy driver's init that
// precedes the stall (2026-10-21); and every 256th read of the interrupt registers or the
// VIA (bt_rdn), to see what a polling loop reads without flooding the trace
logic [7:0]  bt_rdn = 8'd0;
wire         bt_rd_sample = q_is_gc && ~q_we && qa[16:8] == 9'h000;   // (the VIA's reads: every one, since 2026-10-21 14:00)
wire         bt_hit = (TRACE_INT != 0 && q_is_dbg && q_we) ||   // the memory test's progress (DBG)
                      (TRACE_FL != 0 && q_is_fl) ||               // the save flash (2026-10-22: does Mac OS program it?)
                      q_is_gc && (qa[16:9] == 8'h88 || qa[16:8] == 9'h082 || qa[16:8] == 9'h083 ||
                                qa[16:8] == 9'h140 || qa[16:8] == 9'h088 ||
                                (tr_mesh && (qa[16:8] == 9'h180 || qa[16:8] == 9'h08A)) ||
                                (TRACE_INT != 0 && q_we && (qa[16:8] == 9'h000 || q_is_via)) ||
                                (TRACE_INT != 0 && q_is_via) ||   // the VIA's reads too: T2 and IFR as the Time Manager sees them
                                (TRACE_INT != 0 && (qa[16:8] == 9'h150 || qa[16:8] == 9'h081)) ||
                                (TRACE_INT != 0 && (qa[16:8] == 9'h120 || qa[16:8] == 9'h130)) ||   // the ESCC
                                (TRACE_INT != 0 && bt_rd_sample && bt_rdn == 8'd0));
always_ff @(posedge clk) begin
	if (dev_take & ~q_line & bt_rd_sample) bt_rdn <= bt_rdn + 8'd1;
	if (bt_div == (cpu_fast ? 16'(CPU_HZ_FAST / 1_000_000 - 1) : 16'(CPU_HZ / 1_000_000 - 1))) begin
		bt_div <= 16'd0;
		bt_us  <= bt_us + 32'd1;
	end
	else bt_div <= bt_div + 16'd1;
	if (dev_take & (~q_line | (TRACE_FL != 0 && q_is_fl))) begin   // (the flash's line accesses too: their first word, be 0)
		bt_pend <= bt_hit;
		bt_a    <= qa;
		bt_we   <= q_we;
		bt_wd   <= c_wdata[31:0];
		bt_be   <= q_line ? 4'h0 : c_be;
	end
	else if (dev_ack) bt_pend <= 1'b0;
	if (reset) bt_pend <= 1'b0;
end
wire bt_ev = dev_ack & bt_pend;
// ... and every word access (not a line: uncached) the CPU makes to one RAM line, as the
// memory port serves it (2026-10-21 22:50: the floppy driver's TMTask is in a cache-
// inhibited page and two halves of a misaligned store never reach the SDRAM): the
// request as granted, the answer's data for a read, the SDRAM controller's diagnostic
// word (its rdata[63:32]) for a write, in bytes 16-19 of the record
localparam logic [31:5] TRACE_RAM_LINE  = TRACE_RAM_A[31:5];
localparam logic [31:5] TRACE_RAM_LINE2 = TRACE_RAM_A2[31:5];
logic        mw_pend, mw_we;
logic [31:0] mw_a, mw_wd;
logic [3:0]  mw_be;
always_ff @(posedge clk) begin
	if (TRACE_RAM != 0 && grant_cpu & ~c_line & ((a[31:5] == TRACE_RAM_LINE) | (a[31:5] == TRACE_RAM_LINE2))) begin
		mw_pend <= 1'b1;
		mw_a    <= a;
		mw_we   <= c_we;
		mw_wd   <= c_wdata[31:0];
		mw_be   <= c_be;
	end
	else if (cpu_m_ack) mw_pend <= 1'b0;
	if (reset) mw_pend <= 1'b0;
end
wire mw_ev = cpu_m_ack & mw_pend;
// kind 5: a command of DMA channel 2, 3 or 8 finished (8 fetched, 9 stopped); 6: the ADB
// keyboard; 10: MESH's interrupt (with tr_mesh); 11: channel 8's interrupt
wire   itr_tr = itr_ev & tr_mesh;
// TRACE_FL: the save flash's image port, as kind 4 records at 4F000000 + what: 1 a block of the
// image loaded into the flash (its first byte written, the address in the low bits), 2 a block
// read out for a save (its first byte), 3 the CPU programmed or erased the flash
// (3 only at the first of a run: an erase sweep changes a byte every clock and flooded the trace)
logic        fl_re_q, fl_ch_q;
always_ff @(posedge clk) begin fl_re_q <= fl_ld_re; fl_ch_q <= fl_changed; end
wire         fl_tev  = TRACE_FL != 0 &&
                       ((fl_ld_we && fl_ld_addr[8:0] == 9'd0) || (fl_ld_re && !fl_re_q && fl_ld_addr[8:0] == 9'd0) || (fl_changed && !fl_ch_q));
wire  [31:0] fl_ta   = {8'h4F, fl_changed ? 4'd3 : fl_ld_we ? 4'd1 : 4'd2, 3'd0, fl_ld_addr};
assign tr_ev  = sd_tr_ev | bt_ev | mw_ev | dfin | adb_tr_ev | itr_tr | itr8_ev | fl_tev;
assign tr_rec = sd_tr_ev ? sd_tr_rec :
                fl_tev & ~bt_ev & ~mw_ev ? {128'd0, 24'd0, fl_ld_data, fl_ta, bt_us, 19'd0, 1'b1, 4'hF, 8'd4} :
                bt_ev    ? {128'd0, bt_we ? bt_wd : line_buf[0], bt_a, bt_us, 19'd0, bt_we, bt_be, 8'd4} :
                mw_ev    ? {96'd0, m_rdata[63:32], mw_we ? mw_wd : m_rdata[31:0], mw_a, bt_us, 19'd0, mw_we, mw_be, 8'd4} :
                dfin     ? {64'd0, dfin_info, bt_us, 16'd0, 4'd0, dfin_ch,
                            (dfin_type == 2'd0) ? 8'd5 : (dfin_type == 2'd1) ? 8'd8 : 8'd9} :
                itr_tr   ? {192'd0, bt_us, 16'd0, itr_st, 8'd10} :
                itr8_ev  ? {192'd0, bt_us, 16'd0, itr8_st, 8'd11} :
                           {160'd0, adb_tr_info, bt_us, 24'd0, 8'd6};

assign c_ack   = cpu_m_ack | dev_ack | v_ack;
assign c_rdata = v_ack    ? v_rdata :
                 ~dev_ack ? m_rdata :
                 c_line   ? {line_buf[0], line_buf[1], line_buf[2], line_buf[3],
                             line_buf[4], line_buf[5], line_buf[6], line_buf[7]} :
                            {224'h0, line_buf[0]};

endmodule
