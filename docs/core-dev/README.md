# Apple Pippin MiSTer core: core-development reference

Gathered 2026-10-16. This folder holds the software references (emulator source, MiSTer framework, prior art) for
building the core. Hardware PDFs (Apple developer notes, the PowerPC 603 manual, chip datasheets, CD drive manuals)
are in `scratch/pdfs/` (index: [../pdf-index.md](../pdf-index.md)). They are collected separately and not duplicated here.

> **Paths:** the saved source excerpts (`reference-src/`, `mister/`) were moved to the git-ignored `scratch/core-dev/` folder. Every `reference-src/...` and `mister/...` path below is relative to `scratch/core-dev/`, and `../pdfs/` means `scratch/pdfs/`.

**How to read this document.** Plain statements with a `file:line` citation say what that source does.
Paragraphs marked **[inference]** are my reading or estimates; check them against hardware docs before relying on
them. "MAME says X" means MAME's model does X. It does not prove the real hardware does.

## 0. What is in this folder

| Path | What | Source / version | License |
|---|---|---|---|
| `reference-src/mame/` | Sparse MAME checkout: `pippin.cpp` and every Apple device it instantiates (Aspen/Bandit, Grand Central, DBDMA, MESH, Taos, AWACS, Athens Prime, Cuda, ADB incl. the Pippin controller), plus the generic devices those use (6522 VIA, Z8530 SCC, SWIM3, NSCSI bus + CD-ROM, PCI, I2C HLE, intelfsh, PPC headers, MN1880). Also `hash/pippin.xml` (88 CD titles, metadata only). | github.com/mamedev/mame @ `ad252799ed2e7c495fb7889c64007920adf387de` (2026-10-16), see `reference-src/MAME_COMMIT.txt` | BSD-3-Clause for these files (headers); MAME overall GPL-2.0+ (`COPYING`); softlist CC0 |
| `reference-src/dingusppc/` | Sparse DingusPPC: `machines/machinepippin.cpp`, Aspen, Bandit/PCI host, Grand Central, Taos, AWACS, MESH + SCSI CD, VIA-Cuda, DBDMA, the whole `cpu/ppc/` interpreter + MMU (test CSVs dropped), `zdocs/developers/*.md` | github.com/dingusdev/dingusppc @ `6d8ce06052194c92ad0a76cb33b88bdaa8b4728f` (2026-10-15) | GPL-3.0 |
| `reference-src/Template_MiSTer/` | Template top level (`Template.sv/.qsf/.qpf/.sdc`, `files.qip`, `rtl/`), plus `sys/sys_top.v`, `hps_io.sv`, `emu_ports.vh`, `ascal.vhd`, `ddr_svc.sv`, `sysmem.sv`, `video_mixer.sv`, `video_freak.sv`, `audio_out.sv`, `sd_card.sv`, `sys*.tcl`. Full `sys/` listing in `reference-src/Template_MiSTer_sys_listing.txt` | MiSTer-devel/Template_MiSTer @ `5dda37366d02b04b8448da7b322235c1831af811` | GPL-2.0 |
| `reference-src/Main_MiSTer/` | HPS-side CD/SCSI support: `support/mac/*` (the Mac SCSI-family CD-ROM translator: CUE/CHD to a 2048-byte-sector virtual disc plus TOC/CD-DA windows), `support/chd/*`, `support/next/next_cdrom*`, PSX/Saturn/MegaCD/PCE-CD/NeoGeo-CD drivers, `user_io.cpp/.h`, `cd.h` | MiSTer-devel/Main_MiSTer @ commit in `reference-src/MAIN_MISTER_COMMIT.txt` (`e836aea7`, 2026-10-16) | GPL-3.0 |
| `reference-src/mister-cd-cores/` | FPGA-side `hps_ext.v` CD bridges from MegaCD, TurboGrafx16, NeoGeo, Saturn (+`hps2cdd.sv`), PSX | commits/licenses in `SOURCES.txt` | GPL-2/3 (TG16, Saturn: no SPDX on repo; check file headers) |
| `mister/wiki/` | MiSTer wiki pages on core development, saved as markdown: emu top level, HPS-IO, core config string, DDR usage, SDRAM, video_mixer/video_freak/arcade_video, savestates, porting notes, contributing, folders/paths, MGL | Wiki_MiSTer.wiki, commit in `mister/wiki/SOURCE.txt` | MiSTer wiki |

Total about 11 MB. No ROM images or firmware were downloaded.

---

## 1. Pippin hardware as MAME (and DingusPPC) model it

Main file: `reference-src/mame/src/mame/apple/pippin.cpp` (337 lines; abbreviated `pippin.cpp` below. Other MAME
paths are relative to `reference-src/mame/src/`).

### 1.1 Chips and the source file for each

| Chip (part #) | Role | MAME model | DingusPPC model |
|---|---|---|---|
| PowerPC 603 @ 66 MHz | CPU | `PPC603(config, m_maincpu, 66000000)` at `pippin.cpp:201`. Device: `devices/cpu/powerpc/ppccom.cpp:272-273` (caps `OEA, VEA, FPU, MISALIGNED, 603_MMU`, **timebase divisor 4**) | `ppc_cpu_init(aspen_obj, PPC_VER::MPC603, false, 16500000ULL)` at `machines/machinepippin.cpp:77` (timebase 16.5 MHz = 66/4) |
| Aspen 343S0152 | Bandit-derived PCI host bridge + RAM/ROM controller | `ASPEN(config, m_aspen, 66000000, "maincpu")`, `set_dev_offset(1)` at `pippin.cpp:205-207`; `mame/apple/bandit.cpp` (`aspen_host_device`, regs at 0xF8000000 `bandit.cpp:93-98`, regs_r `:140-157`) | `devices/memctrl/aspen.cpp`/`.h` (regs `aspen.h` enum; bank sizes 1/4/8/16 MB) |
| Taos 343S0153 | 640x480 framebuffer video, double buffering, flicker convolution for NTSC/PAL | `APPLE_TAOS(config, m_taos, 31.3344_MHz_XTAL)` `pippin.cpp:244`; `mame/apple/taos.cpp`/`taos.h` | `devices/video/taos.cpp`/`.h` (has the VBL interrupt enable, Bt856 at I2C 0x44, Athens at 0x29) |
| Grand Central 343S1125 | PCI "Mac I/O": interrupt controller, DBDMA, VIA, SCC, SWIM3, audio (DAVbus) port, SCSI ports | `GRAND_CENTRAL(config, m_grandcentral)` `pippin.cpp:215-217`; `mame/apple/heathrow.cpp` (`grandcentral_device`) + `dbdma.cpp` | `devices/ioctrl/grandcentral.cpp`, `macio.h`, `devices/common/dbdma.cpp` |
| MESH 343S1146 (discrete) | SCSI controller (539x-derived); the CD-ROM sits on its bus | `APPLE_MESH_SCSI(config, m_mesh, 50_MHz_XTAL)` on SCSI ID 7, CD at ID 3, `pippin.cpp:219-242`; `mame/apple/mesh.cpp` | `devices/common/scsi/mesh.cpp` (see discrepancy D2 below) |
| Cuda 341S0060 (68HC05) | ADB, PRAM, RTC, reset/power, I2C master | `CUDA_V2XX(config, m_cuda, XTAL(32'768))`, BIOS `341s0060`, `pippin.cpp:266-289`; `mame/apple/cuda.cpp` (LLE of the 68HC05 firmware via `cpu/m6805/m68hc05e1`) | `devices/common/viacuda.cpp` (HLE) |
| Athens Prime 343S1191 (x2 on board) | I2C-programmed PLL (pixel clock / system clock) | `APPLE_ATHENSPRIME(config, m_athensprime, 20_MHz_XTAL)`, pclock goes to Taos `pippin.cpp:259-260`; I2C addr 0x29 `mame/apple/athensprime.cpp:26` | `AthensClocks(0x29, 20000000.0f)` in `devices/video/taos.cpp` |
| AWACS (CS4217 DAC) | Audio codec on Grand Central's DAVbus, DMA-fed | `AWACS_MACRISC(config, "codec", 45.1584_MHz_XTAL / 2)` `pippin.cpp:248-257`; `mame/apple/awacs_macrisc.cpp` | `devices/sound/awacs.cpp` |
| Z8530 SCC | Serial | inside Grand Central: `SCC85C30(config, m_scc, C7M)` `mame/apple/heathrow.cpp:186-188` | inside GC |
| R65NC22 VIA | Cuda shift-register link, timers | `R65NC22(config, m_via1, C7M / 10)` `heathrow.cpp:137` (= 783,360 Hz) | inside GC |
| SWIM3 | Floppy (part of GC; the Pippin itself has no floppy drive **[inference: optional dock]**) | `SWIM3(config, m_fdc, C31M)` `heathrow.cpp:178` | `swim3.md` doc only |
| Bt856 | Composite/S-video encoder, I2C controlled | not modeled (header comment only, `pippin.cpp:21`) | `Bt856(0x44)` in `taos.cpp` |
| AMD Am29F010 | 128 KB save flash, byte per 32-bit word, data bus bit-reversed | `pippin.cpp:23-24, 145, 158-166, 246` | not present |
| Matsushita CR504-L CD-ROM (MN1880 MCU, firmware 504par4.0i) | 4x SCSI CD drive | Modeled at the SCSI level as `NSCSI_CDROM_APPLE` with CDDA to the speakers (`pippin.cpp:223-227`). The drive MCU is instantiated but **disabled** (`pippin.cpp:291-294`). | `ScsiCurio:3` (`machinepippin.cpp:91-92`) |
| ADB "AppleJack" controller | Gamepad | `ADB_CONNECTOR ... "pippin_controller"` `pippin.cpp:263`; `devices/bus/adb/adbhlepippin.cpp` (button bits at `:15-24`) | `adb_devices = "AppleJack,Keyboard"` |

### 1.2 CPU physical memory map (MAME, confirmed by DingusPPC where noted)

| Address | Size | What | Citation |
|---|---|---|---|
| `0x0000_0000-0x003F_FFFF` | 4 MB | RAM bank 0 (onboard) | `pippin.cpp:108` |
| `0x0040_0000`, `0x00C0_0000`, `0x00C0_1000` (4 KB each) | | Mirror windows of bank 0 + 0x200, probed by the ROM's memory sizing | `pippin.cpp:107-111`; DingusPPC derives the same aliases from the DRAM row/column geometry, `aspen.cpp:146-168` |
| `0x0100_0000-0x010F_FFFF` | 1 MB | RAM bank 1 (onboard), plus mirrors at `0x0140_0000` and `0x01C0_0000/1000` | `pippin.cpp:112-115` |
| `0x0200_0000-0x027F_FFFF` | 8 MB | Expansion bank 2 (when RAM > 5 MB) | `pippin.cpp:117-123` |
| `0x0300_0000-0x037F_FFFF` | 8 MB | Expansion bank 3 (when RAM > 13 MB) | `pippin.cpp:125-131` |
| | | Banks sit on 16 MB boundaries in DingusPPC as well | `aspen.cpp:120` |
| `0x4000_0000-0x4007_FFFF` | | Save flash (byte lane D0-D7 of each 32-bit word, bit-reversed) | `pippin.cpp:145` |
| `0x8000_0000-0xEFFF_FFFF` | | PCI memory window (Bandit generic) | `bandit.cpp:179-180` |
| `0xF000_0000-0xF00F_FFFF` | 1 MB | Taos VRAM | `pippin.cpp:147` + `taos.cpp:31`; DingusPPC `taos.h:39-41` |
| `0xF080_0000-0xF080_03FF` | | Taos registers (32-bit, value in the top byte(s)) | `taos.cpp:32`, regs enum `taos.h:30-72` |
| `0xF100_0000-0xF100_07FF` | | Taos CLUT (256 entries, RGB in bits 31-8) | `taos.cpp:33, 174-180` |
| `0xF200_0000-0xF27F_FFFF` | | PCI I/O space (Aspen dev_offset 1 gives base 0xF2000000) | `bandit.cpp:208-209, 232` |
| `0xF280_0000` / `0xF2C0_0000` | | PCI config address / data (byte-swapped). Aspen's IDSEL mapping is in `aspen_host_device::be_config_address_w`. | `bandit.cpp:233-234, 332-347` |
| `0xF300_0000-0xF3FF_FFFF` | | PCI memory window 1. Grand Central (PCI dev 0x10, 128 KB BAR, ID `106b:0002`) is placed here by firmware. | `bandit.cpp:192-195`; `heathrow.cpp:425-429`; DingusPPC comment "IOBus Device #4 0xF301D000" `grandcentral.cpp:135` |
| `0xF800_0000-0xF800_07FF` | | Aspen registers: SYSTEM_ID (`0x40010000`) at +0x10, VERSION (`0x01000000`) at +0x14, MEM_CONFIG +0x18, GPIO +0x30/34/38 | `bandit.cpp:26-31, 97-98, 140-157`; `aspen.h` enum; `aspen.cpp:34` |
| `0xFFC0_0000-0xFFFF_FFFF` | 4 MB | Boot ROM (64-bit big-endian) | `pippin.cpp:149, 311`; DingusPPC `machinepippin.cpp:65` |

Grand Central internal offsets (add 0xF3000000, see `heathrow.cpp:77-112`): 0x00000 interrupt/ID registers,
0x08000-0x08A1F DBDMA channels (SCSI0, floppy, Ethernet tx/rx, SCC A/B tx/rx, audio out/in, SCSI1),
0x10000 SCSI0 ("Curio" 53C94 slot, **unconnected on Pippin in MAME**), 0x11000 Ethernet (MACE, unused on Pippin),
0x12000/0x13000 SCC, 0x14000 AWACS, 0x15000 SWIM3, 0x16000 VIA (Cuda), **0x18000 SCSI1 = MESH**, 0x1A000-0x1FFFF IOBus
devices (NVRAM etc.).

### 1.3 Interrupts

- The CPU has a single external interrupt (`PPC_IRQ`, `ppc.h:36`) driven only by Grand Central
  (`pippin.cpp:217`).
- Grand Central latches events into InterruptEvents/Mask/Levels (registers at +0x20/+0x24/+0x28 clear/+0x2C).
  Bit 31 of the mask selects the "emulation" (68k-style) or native mode. `heathrow.cpp:615-770`
  (`macio_r/macio_w/recalc_irqs/set_irq_line`).
- Bit assignments (MAME `heathrow.cpp`/`heathrow.h`; DingusPPC `grandcentral.cpp:470-519` agrees):
  DMA 0 SCSI0, 1 floppy, 2/3 Ethernet, 4-7 SCC DMA, 8/9 audio out/in, **10 SCSI1(MESH) DMA**;
  12 SCSI0 (Curio) device, **13 SCSI1 (MESH) device** (`heathrow.h:172`), 14 Ethernet, 15/16 SCC A/B, 17 DAVbus,
  **18 VIA/Cuda**, 19 SWIM3, 20 NMI. DingusPPC also maps the Pippin's PCI slot INTs to EXT9/EXT10
  (bits 0x1D/0x1E, `grandcentral.cpp:498-499`, `machinepippin.cpp:38-44`).
- VBL: MAME's Taos exposes VBL only as a polled GPIO bit (bit 25 of GPIO_IN, `taos.cpp:138-146`; it has no IRQ
  output). DingusPPC's Taos has an INT_ENABLES register with a VBL-enable bit 29 (`taos.cpp:~165`), but no
  routing to GC is visible in the files saved here. **Open question Q4.**

### 1.4 Clocks (as configured in the emulators)

| Clock | Value | Citation |
|---|---|---|
| CPU core | 66 MHz | `pippin.cpp:201` |
| Time base / decrementer | CPU/4 = 16.5 MHz | `ppccom.cpp:273` (divisor 4); `machinepippin.cpp:77` |
| Aspen / "bus" | 66 MHz as passed to the device (no bus/core ratio is modeled). **The real 60x bus ratio is open question Q1.** | `pippin.cpp:206` |
| Taos | 31.3344 MHz XTAL; pixel clock reprogrammed by Athens. The MAME screen is initially 25.175 MHz, 800x525. | `pippin.cpp:244`, `taos.cpp:44, 72, 76-79` |
| Athens reference | 20 MHz | `pippin.cpp:259` |
| AWACS | 22.5792 MHz (45.1584/2). Sample rate = clock / {512..3072}, so 44.1 kHz at /512, 22.05 kHz default. | `pippin.cpp:248`, `awacs_macrisc.cpp:80, 165-172` |
| MESH | 50 MHz | `pippin.cpp:232` |
| VIA | 783,360 Hz (C7M/10, C7M = 7,833,600) | `heathrow.cpp:34-37, 137` |
| SCC | PCLK 7.8336 MHz, RTxC 3.6864 MHz | `heathrow.cpp:186-187` |
| SWIM3 | 31.3344 MHz | `heathrow.cpp:178` |
| Cuda | 32.768 kHz crystal (the 68HC05 PLL multiplies it) | `pippin.cpp:266` |

### 1.5 Video modes

- MAME's Taos renders a fixed **640x480** from VRAM, either **8 bpp CLUT** or **16 bpp xRGB555**
  (`COLOR_DEPTH` bit 31). Stride comes from `ROW_WORDS`, base from `FB_BASE` (`taos.cpp:81-118`).
  Timing (`HAL/HFP/HPIX/VAL/VFPEQ/VHLINE`) is decoded DAFB-style (`taos.cpp:182-200`).
- GPIO_IN reports the monitor ID: 3 = PAL, 5 = NTSC, 6 = VGA 640x480 at 30 kHz. Bit 27 = CD tray closed
  (`taos.cpp:138-146`; DingusPPC `taos.h:110-112`, OSD-style option `video_out` NTSC/PAL/VGA `taos.cpp:71-77, 266`).
- Not modeled by either emulator: the interlace convolution filter, field timing, Bt856.
- **[inference]** For MiSTer, the simplest route is to make Taos report monitor ID 6 (VGA), which gives a
  progressive 640x480 at about 60 Hz. NTSC (ID 5) could then be offered as an option for 15 kHz/CRT users, with
  convolution added later. Both emulators let software choose by monitor ID.

### 1.6 Boot and reset sequence (MAME)

- At machine reset the CPU is halted until Cuda releases it (`pippin.cpp:136-140, 152-156, 268`).
- Cuda talks to GC's VIA over the shift register (CB1/CB2, PB3-5: `pippin.cpp:270-271, 286-289`). Cuda is also
  the I2C master to Athens Prime (`pippin.cpp:274-282`).
- `config.set_perfect_quantum(m_maincpu)` (`pippin.cpp:284`).

### 1.7 ROMs (metadata only, nothing downloaded)

From `pippin.cpp:297-332` and DingusPPC `machines/romidentity.cpp:104-107`:

| BIOS | MAME CRC32 / SHA1 | DingusPPC id (ROM version, checksum) |
|---|---|---|
| Kinka 1.3 (1996-09-20, 4 MB) | `87a1337d` / `8e512af6...ecad54` | `077d2cf8`, `3e6b3ee4` |
| Kinka 1.2 (1996-06-28) | `4fead4b3` / `3fa02e9b...2f1f` | `077d2cf5`, `3e10e14c` |
| Kinka 1.0 (4x 1 MB, 341S0251-0254) | per-chip CRCs at `pippin.cpp:319-322` | `077d2cf2`, `2bef21b7` |
| Kinka GM / pre-release ("dev") | `4ff875e6` | `077d2cc6`, `2bf65931` |
| CD drive MCU (CR504-L) | `25f7dd46` (`504par4.0i.ic7`) | n/a |
| Cuda | 341S0060 (same part as Power Mac 7300 Cuda) | n/a |

Part numbers in the comment at `pippin.cpp:299-306`: monitor 341S0241-250, 1.0 = 341S0251-254,
1.2 = 341S0297-300, 1.3 = 341S0328-331. **[web, not verified]** Pippin Kickstart (Keith Kaisershot, GPL-2.0,
2019-2021) boots unsigned CDs only on 1.0/1.2/1.3 consumer ROMs, not dev ROMs.

### 1.8 Discrepancies between the two emulators

- **D1, RAM size.** MAME defaults to 13 MB, with 5 MB and 21 MB options (`pippin.cpp:211-213`). DingusPPC uses
  4 + 1 MB onboard plus two expansion banks of 0/1/4/8/16 MB (`machinepippin.cpp:83-90`). Both agree on
  5 MB onboard. **[web]** Retail @WORLD = 6 MB (5 MB DRAM + 1 MB VRAM).
- **D2, which SCSI controller the CD is on.** MAME puts the CD on a discrete MESH at GC's SCSI1 port
  (0x18000) and leaves SCSI0 (53C94/Curio) unconnected. DingusPPC's Pippin device list
  (`machinepippin.cpp:99-101`) has no MESH, so GC falls back to a MESH stub (`grandcentral.cpp:95-99`) and
  the CD is configured as `ScsiCurio:3` (on the 53C94). Both boot titles to some degree, so the ROM may probe
  both. Check against the developer note in `../pdfs/`. **Q2.**
- **D3, Cuda.** MAME runs Cuda as a real 68HC05 executing 341S0060; DingusPPC uses HLE. MacPPC7300_MiSTer
  ships an RTL 68HC05 running 341S0060 (see §3), which matches MAME's approach.

---

## 2. MiSTer framework notes relevant to this core

Files: `reference-src/Template_MiSTer/` and `mister/wiki/`.

- **Top level.** `module emu` in `<core>.sv` takes its ports from ``sys/emu_ports.vh`` (`Template.sv:19-22`).
  Don't modify `sys/` (`Readme.md`). You must provide a PLL in `rtl/pll`. Macros: `MISTER_FB`,
  `MISTER_DUAL_SDRAM`, `MISTER_DEBUG_NOHDMI`.
- **Memory.**
  - SDRAM (32-128 MB module, low latency): `SDRAM_*` in `emu_ports.vh:117-128`.
  - DDR3, shared with Linux, high latency, Avalon 64-bit bursts: `DDRAM_*` in `emu_ports.vh:104-115`. Keep the
    top address nibble at 3 to stay out of Linux (`mister/wiki/DDR-Usage.md`).
  - **[inference]** The Pippin needs 4 MB ROM + 5-6 MB RAM (up to 21 MB with expansion) + 1 MB VRAM, all of
    which fits comfortably in a 32 MB SDRAM. MacPPC7300 keeps RAM + ROM in SDRAM and VRAM in DDR3.
- **Video.**
  - The core outputs `CLK_VIDEO/CE_PIXEL/VGA_*` with DE/HS/VS. The framework's `ascal.vhd` scaler handles HDMI,
    and `video_freak.sv` handles aspect/crop.
  - Alternatively, `MISTER_FB` lets the core hand ascal a framebuffer that already sits in DDR3
    (`emu_ports.vh:46-73`: FB_FORMAT 8bpp palette / 16bpp 1555 / 24 / 32, plus an `FB_PAL_*` palette port).
  - **[inference]** Taos is a pure linear framebuffer (8bpp CLUT or 16bpp 555), which maps almost 1:1 onto
    `MISTER_FB` with `FB_FORMAT` 8bpp + palette or 16bpp 1555. VRAM would then live in DDR3 and ascal would scan
    it with no scan-out logic in the core, at the cost of no analog/CRT output from that path. A normal
    scan-out (as MacPPC7300's Control video does) keeps analog output working.
- **Audio.** `AUDIO_L/R` are 16-bit at any rate, with `CLK_AUDIO` = 24.576 MHz (`emu_ports.vh:88-92`). AWACS
  produces 16-bit stereo, and CD-DA is mixed in (MAME routes CDDA directly to the speaker, `pippin.cpp:225-226`).
- **hps_io** (`sys/hps_io.sv:35-200`):
  - Block devices: `img_mounted/img_size/sd_lba/sd_blk_cnt/sd_rd/sd_wr/sd_ack/sd_buff_*` with `VDNUM` slots
    and `BLKSZ` (`hps_io.sv:128-143`).
  - Downloads (ROM): `ioctl_*` (`:146-157`).
  - `EXT_BUS` for core-specific HPS protocols (`:160-200`, used by all the CD cores' `hps_ext.v`).
  - `RTC` (`:164`) for setting Cuda's clock.
  - OSD menu from `CONF_STR` (`mister/wiki/Core-configuration-string.md`).

### 2.1 How existing cores get CD images (CUE/BIN, CHD)

There are two patterns in Main_MiSTer (saved in `reference-src/Main_MiSTer/`):

1. **Drive-level streaming over EXT_BUS** (MegaCD, PCE-CD, NeoGeo-CD, Saturn, PSX).
   - Main parses the CUE/CHD (`support/chd/mister_chd.cpp` wraps libchdr) and emulates the CD drive's command
     timing in C++ (`support/megacd/megacdd.cpp`, `support/pcecd/pcecdd.cpp`, `support/saturn/saturncdd.cpp`).
   - Sectors and subcode are pushed to the core through `UIO_CD_GET/UIO_CD_SET` (`user_io.h:62-63`) and the
     core's `hps_ext.v` (`mister-cd-cores/*/rtl/hps_ext.v`).
   - Saturn additionally uses a DDR3 shared-memory window (`saturncdd.cpp:8-11`, `SHMEM_ADDR 0x31000000`).
   - PSX sends the TOC as a download (index 251) and then reads sectors through the normal block-device path
     (`support/psx/psx.cpp:421-433, 474, 770-806`; `user_io.cpp:3577-3597`).
2. **SCSI block device with HPS-side translation** (the Mac SCSI family: MacPlus, MacLC/LCII, MacQuadra800,
   **MacPPC7300**). This is the one that fits the Pippin.
   - The CD is an ordinary `hps_io` block slot (`MAC_CDROM_SLOT 4`, `support/mac/mac_cdrom.h:9`).
   - Main translates CUE/CHD/raw-2352 images into a flat 2048-byte-sector virtual disc (`mac_cdrom.cpp`). It also
     exposes out-of-band windows at magic LBAs for the TOC blob (`0x7FFF0000`), CD-DA frames (`0x40000000 +
     lba`), and command/response windows (`mac_cdrom.h:11-21`).
   - The SCSI CD target itself (INQUIRY, READ, READ TOC, PLAY AUDIO...) is RTL in the core:
     `MacPPC7300_scsidisk.sv` + `MacPPC7300_cdaudio.sv`, or MacLC's `scsi.v`.
   - **Gating is by core name**: `is_mac_scsi_family()` matches `maclc`, `macplus`, `macquadra800`,
     `macppc7300` (`support/mac/mac.cpp`, upstream; first lines of the file). **[inference]** A Pippin core
     must either be added to that list with an upstream Main_MiSTer PR, or be named so that it matches.
     **Q6.**
   - NeXT has a parallel SCSI CD implementation (`support/next/next_cdrom*.cpp`, `next_scsi.cpp`).

**[inference]** The Pippin's CD is a SCSI device behind MESH, so pattern 2 can be reused almost verbatim, along
with MacPPC7300's MESH + SCSI-CD RTL. MAME's `NSCSI_CDROM_APPLE` (`devices/bus/nscsi/cd.h:156-196`) shows which
Apple-specific vendor commands (audio play/stop position) the ROM/OS may issue.

---

## 3. Prior art

| Project | URL | License | Relevance |
|---|---|---|---|
| **MacPPC7300_MiSTer** (DSPPC604 CPU + Power Mac 7300/7600 machine). The user's own repo; local copy at `/Users/dani/repos/MacPPC7300_MiSTer` (local HEAD `a30e029`, 2026-10-14; GitHub pushed 2026-10-15) | github.com/danifunker/MacPPC7300_MiSTer | GPL-2.0 | **The decisive prior art.** It is a working 32-bit PowerPC (604-class, in-order, 6-stage, FPU, MMU with hardware tablewalk, 16 KB+16 KB caches) on the DE10-Nano at 65-70 MHz, booting Mac OS 7.6.1-9.1 and Debian. The 7300 (TNT) uses Bandit + **Grand Central** + MESH/53C94 + **Cuda 341S0060** + **AWACS** + **Athens** + DBDMA + SWIM3 + ESCC, which is almost the Pippin's I/O set. Its README explicitly names the Pippin as the long-term goal (`README.md:162, 182`), and its plan reserves a `DSPPC603` model and a Pippin machine module (`docs/MacPPC7300_plan.md:79-84`). |
| MAME `pippin.cpp` | github.com/mamedev/mame | BSD-3 (driver files) | Executable spec, saved here. Best for Cuda LLE, MESH, flash, GC interrupt semantics. |
| DingusPPC | github.com/dingusdev/dingusppc | GPL-3.0 | Executable spec with Pippin support (`machinepippin.cpp`, "kudos to Keith Kaisershot"). Its `cpu/ppc` is the reference MacPPC7300 uses for lockstep testing (`MacPPC7300 README`: "dingusppc is trusted most"). |
| Microwatt | github.com/antonblanchard/microwatt | CC-BY 4.0 | 64-bit POWER ISA 3.0 VHDL softcore. Wrong ISA level and mode for a 603 (64-bit, radix MMU, no 32-bit OEA BATs/segment registers). Useful only as a design reference. |
| OpenPOWER A2I / A2O | github.com/OpenPOWERFoundation/a2i, /a2o | CC-BY 4.0 (A2I); A2O "Apache-2.0 as modified" | 64-bit Book-E. A2O fills a large Xilinx VU FPGA with one thread at 50 MHz (A2O README). Far too large for a Cyclone V and the wrong MMU architecture. Not applicable. |
| mikeakohn/powerpc_fpga | github.com/mikeakohn/powerpc_fpga | MIT | A tiny microcontroller-style PowerPC subset on an iCE40 (no mul/div, no MMU/FPU). Educational only. |
| IBM PPC405/440 hard/soft cores | (Xilinx Virtex-II Pro/4/5 hard cores; IBM licensable) | proprietary | Book-E MMU (not OEA), not available as source. Not applicable. |
| GameCube/Gekko FPGA | none found (web + GitHub search 2026-10-16) | | No public effort found. |
| MacPlus_MiSTer | github.com/MiSTer-devel/MacPlus_MiSTer (local `/Users/dani/repos/MacPlus_MiSTer`) | (repo has no SPDX) | 68000 (fx68k/tg68k), NCR5380 SCSI, SD-backed SCSI disks. Mac SCSI-family CD path. |
| MacLC_MiSTer / MacLCII / MacIIvi | github.com/MiSTer-devel/MacLC_MiSTer; danifunker/MacLCII_MiSTer, MacIIvi_MiSTer (local copies) | | TG68K 68020/68030+PMMU; Egret/Cuda 68HC05 work, ADB, CD-ROM over SCSI with CD audio (`cd_audio.sv`). |
| MacQuadra800_MiSTer | github.com/MiSTer-devel/MacQuadra800_MiSTer | GPL-2.0 | AP68040 CPU, DAFB video (**Taos is "DAFB-like"**, `taos.cpp:7-9`, so DAFB timing-register decoding is relevant), 53C96 SCSI. |
| NeXT_MiSTer | github.com/MiSTer-devel/NeXT_MiSTer | GPL-2.0 | Another SCSI CD-ROM via HPS (`support/next`). |
| Pippin research: Keith Kaisershot (blitter.net), "Exploring the Pippin ROM(s)" parts 1-9, Pippin Kickstart | blitter.net (unreachable from here, connection refused); summary at pippin.fandom.com/wiki/Pippin_Kickstart | Kickstart GPL-2.0 (per fandom wiki) | ROM internals, authentication, boot flow. Credited by both emulators. Read this before working on the CD boot path. |
| abzman/Apple-Pippin-stuff | github.com/abzman/Apple-Pippin-stuff | Unlicense | Photos, memory-expansion module pinout PDFs (72-pin SIMM, 16 MB), archived Pippin web pages. Hardware context only; not downloaded. |
| mmoeller86/APippinEmu | github.com/mmoeller86/APippinEmu | none | Empty (README only). |
| MiSTer forum: "Macintosh PowerMac Core" | misterfpga.org/viewtopic.php?p=117158 | | The MacPPC7300 thread. Per search snippets, the developer states the goal of running the Pippin as another core. (Returned 403 to the fetcher; not read directly.) |
| MiSTer forum: "Apple PowerPC G3/G4 Core?" | misterfpga.org/viewtopic.php?t=1400 | | Older (about 2020) skepticism thread ("DE10-Nano handles roughly 486-class CPUs"). It predates and is contradicted by MacPPC7300. (403, snippets only.) |
| MiSTer forum: "Is the Atari Falcon 030 possible", "A second PS1 core" | mail.misterfpga.org/viewtopic.php?p=81174, misterfpga.org/viewtopic.php?p=38738 | | Context: ao486 is the largest MiSTer core and barely fits. |

No Pippin-specific threads were found on AtariAge or tinkerdifferent (searched 2026-10-16), and no other Pippin
FPGA project was found.

---

## 4. Feasibility and risks

### What the evidence says (MacPPC7300 README tables)

> **Outdated (correction from the author, 2026-10-16):** the figures below come from the MacPPC7300 README
> tables at the time of collection. The DSPPC604 is now close to closing timing at 70 MHz, so a 66 MHz
> Pippin clock is not at the edge. Check the current MacPPC7300 repo before relying on any number here.

- **CPU size.** The whole DSPPC604 (pipeline, FPU, MMU, 2x16 KB caches) is **15,711 ALMs (37%), 77 RAM blocks,
  7 DSPs**, Fmax 63.7-65 MHz standalone. The integer pipeline alone is 3,208 ALMs at 78.6 MHz; the FPU alone is
  3,303 ALMs at 73.5 MHz; before the MMU it was 10,781 ALMs at 69.5 MHz.
- **Full machine.** The full 7300 machine is **35-38K ALMs (84-92%), 322-329 RAM blocks (with a 128 KB L2), 49
  DSPs**. Static timing has negative slack (about -0.3 to -2.5 ns at 65-70 MHz), but **the board runs at 65 MHz
  and then 70 MHz** and boots Mac OS 7.6.1/9.1.
- **Performance.** About 1.57 cycles per instruction with the L2. Speedometer CPU 2.50 against a Quadra 605. The
  author's estimate: "the territory of a Power Macintosh 6100/60 or a Pippin" (MacPPC7300 `README.md:238-243`).
- SDRAM controller at 100 MHz with a clock crossing to the CPU. DMA coherency goes through the CPU's snoop port.

### [inference] What that means for the Pippin

- **Logic: likely fits, with margin.** A Pippin machine replaces Bandit + Control + RaDACal + MACE +
  53C94 + L2 with Aspen (trivial) + Taos (a simple framebuffer, simpler than Control/RaDACal). It drops
  Ethernet and probably SWIM3. A 603 has 8 KB+8 KB 2-way caches instead of 16 KB+16 KB 4-way, so RAM blocks go
  down. Expect noticeably less than the 7300's 85-90%, perhaps 70-80% ALMs, with room for the HPS CD path.
- **Clock: 66 MHz is at the edge.** The CPU closes at about 64-65 MHz standalone and runs at 65-70 MHz on the
  board despite negative slack. Running the Pippin at 66 MHz is consistent with that. But the real 603 is
  roughly 1-1.3 CPI with dual issue limited to branch folding, versus about 1.5 CPI for DSPPC604 here (the
  author compares with a 6100/60, which is a 601). So **the core will likely be somewhat slower than a real
  Pippin**, unless the core clock can be raised (the 7300 build already runs at 70 MHz) or caches/pipeline
  tuned. Pippin titles are mostly Mac-style multimedia (QuickTime/Director). Timing-sensitive games are a risk.
- **Remaining CPU work: the 603's MMU differs.** The 603 has **no hardware page-table walk**:
  - TLB misses raise exceptions 0x1000 (ITLB miss), 0x1100 (DTLB load miss), 0x1200 (DTLB store miss).
  - GPR0-3 are shadowed (MSR[TGPR]).
  - New SPRs: IMISS/DMISS/HASH1/HASH2/ICMP/DCMP/RPA; new instructions `tlbld`/`tlbli`.
  - The PVR is 0x0003xxxx.
  - Caches are 8 KB 2-way with 32-byte lines.
  
  MAME models these exceptions (`PPCCAP_603_MMU`, `devices/cpu/powerpc/ppccom.cpp:273, 999-1001`, `ppc.h:328-330`).
  **DingusPPC does not**: its `tlbld`/`tlbli` are empty placeholders (`dingusppc/cpu/ppc/ppcopcodes.cpp:2199-2211`),
  and its MMU always walks the hashed page table in hardware. Yet DingusPPC lists the Pippin as a working machine
  with `PPC_VER::MPC603`.
  
  **[inference]** So the Pippin ROM/NanoKernel probably runs correctly on a 603 PVR with a hardware tablewalk.
  The NanoKernel's 603 miss handlers would simply never be entered. If that holds, DSPPC604's existing MMU,
  plus a 603 PVR, `tlbld/tlbli` as no-ops and 8 KB caches, may be enough for a first boot. Full software-reload
  fidelity (MacPPC7300 plans it as a separate `DSPPC603` module, `docs/DSPPC604_plan.md:715-718`) could follow
  later. This needs testing: run DingusPPC's Pippin and confirm that no TLB-miss vectors are taken. Check
  against the 603 User's Manual in `../pdfs/chips/`.
- **Memory bandwidth: low risk.**
  - The Pippin's DRAM is 5 MB on a 64-bit 60x bus at 66 MHz or less (peak ≤ 528 MB/s, effectively much less).
  - SDRAM at 100 MHz x 16-bit (200 MB/s peak), shared with the cache fills.
  - The 7300 core already feeds a faster CPU plus 832x624 video from DDR3.
  - Taos 640x480 8 bpp at 60 Hz is about 18 MB/s, or 37 MB/s at 16 bpp, from DDR3 or SDRAM. That is fine.
- **CD-ROM: low-to-medium risk.**
  - The path exists: the Mac SCSI-family HPS translator + MESH + SCSI CD target RTL + CD-DA (all in MacPPC7300
    plus Main_MiSTer).
  - Risks:
    - Main_MiSTer's core-name gating (Q6).
    - The D2 controller ambiguity (MESH vs 53C94).
    - Apple vendor-specific CD commands, and how CD-DA timing interacts with multimedia titles.
    - The Pippin's CD authentication check, which is in ROM code. Faithful emulation passes it automatically,
      since the signatures are on genuine discs.
  - 4x CD speed (600 KB/s) is trivial for SD/HPS.
- **Video: low risk** (8/16-bpp linear framebuffer, one resolution in practice). The convolution/interlace
  features matter only for NTSC/PAL output modes.
- **Audio: low risk** (AWACS RTL exists in MacPPC7300).
- **Unknown-firmware risk.** The CD drive MCU (MN1880) is not needed if the drive is modeled at the SCSI level,
  which is what MAME does.
- **Unknown: the Taos/Aspen register details beyond what the emulators implement.** Both emulators stub most of
  Aspen and Taos (MAME `bandit.cpp:159-161` ignores Aspen writes; `taos.cpp` handles a handful of registers).
  Where the ROM relies on unmodeled behavior, the emulators simply don't exercise it. Real-hardware probing
  (as MacPPC7300 did with `hwprobe/`, `cudadump/`) may be needed.

**[inference] Overall: feasible, with the hard part (a verified 32-bit PowerPC with FPU/MMU/caches at about
65 MHz on the DE10-Nano) already demonstrated.** The critical path is (1) a DSPPC603 variant (603 PVR and 8 KB caches; the
software-TLB-reload MMU is possibly deferrable, since DingusPPC boots the Pippin without it), (2) an Aspen + Taos machine module around the shared GC/MESH/Cuda/AWACS
RTL, and (3) the Main_MiSTer CD hook.

---

## 5. Open questions

1. **Q1** What is the real 60x bus clock and the core:bus ratio on the Pippin (66:66? 66:33?), and does Aspen add
   wait states? Both emulators set only 66 MHz and TB = 16.5 MHz. The ratio affects cache-miss cost and the
   DRAM timing to emulate. (Check the Pippin developer note / service manual in `../pdfs/apple`, `../pdfs/bandai`.)
2. **Q2** Is the internal CD on the discrete MESH (MAME) or on GC's 53C94/Curio (DingusPPC `ScsiCurio:3`)? What
   is on the external SCSI/dock port? Does the ROM probe both buses?
3. **Q3** Which RAM configuration should the core default to: 5 MB DRAM (retail), 13 MB (MAME default with an
   8 MB expansion card), or up to 21 MB? Which expansion cards existed (see abzman's SIMM PDFs)?
4. **Q4** How does the Pippin generate its VBL/60 Hz interrupt? Options: Taos INT_ENABLES bit 29 (DingusPPC)
   routed to which GC input, or the VIA/Cuda tick. MAME exposes VBL only as a polled GPIO bit.
5. **Q5** How much of the Taos register set (convolution, field start, HEQ/HSERR, INT_*) does the ROM or titles
   actually touch? Is a 640x480 progressive output acceptable to all titles when monitor ID = 6 (VGA)?
6. **Q6** Main_MiSTer CD support: should we add the core name to `is_mac_scsi_family()` upstream, or reuse a
   matching name? Which hps_io slot layout (MacLC's `VD_CDROM = 4`) should be kept for compatibility?
7. **Q7** Does the Pippin boot on a hardware-tablewalk 603 (as DingusPPC suggests), or do some titles/OS paths
   need real 603 TLB-miss exceptions (MAME implements them)? DSPPC603: should it be a fork of DSPPC604 in this repo, or a parameterised/sibling module in the
   MacPPC7300 tree, shared as a submodule? What 603 revision is the Pippin's (PVR 0x0003xxxx exact value)? Does
   the ROM's NanoKernel depend on 603-specific HID0/HID1/IABR behavior?
8. **Q8** The save flash (Am29F010, bit-reversed, one byte per word): should it persist via the SD card the same
   way MacPPC7300's `nvsave.sv` persists GC NVRAM?
9. **Q9** Does the Pippin's Cuda firmware 341S0060 behave identically to the 7300's (same part number in MAME),
   so that MacPPC7300's `hc05` + `cudarom` can be reused unchanged? What does the AppleJack ADB controller's
   protocol need beyond MAME's `adbhlepippin.cpp`?
10. **Q10** The Bt856 encoder and the second Athens Prime: does the ROM fail if their I2C ACKs are missing (MAME
    doesn't model Bt856; DingusPPC does at 0x44)?
11. **Q11** The 1.0/1.2/1.3 ROM differences that matter to hardware (e.g. dev/GM ROMs may expect different
    Aspen/Taos IDs). DingusPPC identifies all four.
12. **Q12** Licensing: MacPPC7300 is GPL-2.0, DingusPPC GPL-3.0 (used only as a reference/test oracle, not linked
    into RTL), and MAME's driver files are BSD-3. Pick GPL-2.0(-or-later?) for this core, consistent with
    Template_MiSTer.
