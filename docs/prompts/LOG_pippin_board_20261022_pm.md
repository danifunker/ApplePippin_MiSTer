# Log: the Pippin after v0.1.0, 2026-10-22 afternoon

The user's priorities for the work after v0.1.0 (said 2026-10-22):

- Phase 0: the hunt's instruments behind parameters (the clock goes up later).
- 1: Grand Central's other interrupt sources (the VIA's "event only at a line change" exposure).
- 2: Athens's video clock.
- 3: the 603e's page-crossing alignment rule; the memory test's patterns as regression tests.
- Then: the other ROMs, RAM sizes, saves. The compatibility sweep (playing, CD audio) later.
  The user is away from the board; they will say when they are there (gamepad).

## Phase 0 (2f9b0eb): the instruments behind switches

`CAPTURE` (DSPPC603's capture; its trigger and watched line are now the parameters
`CAP_TRIG_EA`, `CAP_WATCH`, `CAP_WATCH_A`), `DENSE` (the 256-cycle PERF window),
`TRACE_RAM` (the memory-port trace of one RAM line, `TRACE_RAM_A`/`A2`) with
Pippin_sdram's `DIAG` word: all off; `BandaiPippin.sv` has a switch each. A PERF debug
build no longer carries the capture. Build 31 (2f9b0eb, release flags): slack -0.039 ns on
the CPU clock (v0.1.0: +0.201; the release's logic is the same less the SDRAM diagnostic
word: placement noise). Not put on the board. run27 (the lockstep boot to 420 M): PASS.

## 1: Grand Central's interrupt sources (1156710)

dingusppc reports SWIM3, MESH and the 53C94 only at a line change, as we did; only its VIA
reports while the line is high (and MAME is level-sensitive throughout). In rep26 (the
bench's Super Marathon boot) MESH's line was high, unmasked, with no event 124 times, each
ended by the line falling within 18 k cycles: the bench never needed more. The change
(`INT_REPORT = 1`, `Pippin_system`): in 68k mode an access to MESH, SWIM3, the ESCC, MACE
or Curio that leaves the device's line high is an event (the VIA's rule), so a handler
that leaves a second condition pending gets its interrupt back; and every DMA interrupt is
an event in 68k mode, also while the channel's level is still set (dingusppc's
`ack_dma_int`). run28 (the lockstep boot with it): PASS. On the board (build 32): Macintosh
on Pippin, Super Marathon, Racing Days boot as before.

## 2: Athens's video clock (cd2424d, 9f5e92b)

The cause of "the driver never reprograms Athens": the ROM probes the save flash at
FFF0533C (AMD's AA 55 90 through the reversed data lines: 55 AA 09, the ID 01 read as 80),
leaves E1 at F00DFFFA when it answers and E2 when not. With E1 the early set-up (FFF04818)
programs the Athens at I2C 29 (14.375 MHz) and nothing else, and the Taos driver
(FFE54F9C) talks to the Athens at **28** (I2C byte 50); with E2 to 29. dingusppc has no
flash (E2; machref with the ATHENSLOG patch: 0B/1B/22 then 02 at 29, 24.545 MHz); MAME
forces E1 and does not use the pixel clock. The real board has two Athens Primes; ours had
only 29, so the driver's first byte went unacknowledged and it gave up. Pippin_machine now
has both. Acknowledged, the driver writes only that chip's P2_MUX2 = 02 (PLL, post-divider
2) and 07 = 82 to the 29 one (run28's `athens:` lines): D2 and N2 stay at power-up, which
nobody models. Power-up values D2 0B, N2 1B (the E2 path's) would make 24.545 MHz, NTSC's
clock exactly (our dot is half Athens's output: Taos counts in dingusppc's units, ours two
half-lines a line), but that is unproven, so `STD_DOT` stays 1 (the standard rate). The
picture on the board is unchanged. **Open:** the 28 chip's power-up D2/N2 (a real Pippin, or
Apple's Athens Prime data); then `STD_DOT = 0` (cd2424d's path, tested only in the bench).

## 3: regression tests (88ba866)

`sdram_tb --dqm-quirk`: the chip model writes zeros for a WRITE beat with both DQMs high, as
MiSTerss1's module does. `make sdram` (RMW) passes it on 32 and 128 MB; `make sdram-normw`
(RMW = 0) fails it (1,255 differences): the bench sees the board's fault. The memory test
with its status-5 patterns already has PASS/FAIL in the bench (`--boot memtest`,
`--mem-fault` must find an injected fault). The alignment rule is not done.

## The board, v0.1.0 and build 32 (9f5e92b: debug, TRACE = 1, TRACE_FL = 1; slack +0.274)

- **Sound reaches HDMI and can be checked remotely**: `misterkvms-cli record 25s F.wav`
  (no ffmpeg needed). The boot chime: ~2 s of decaying tone right after a reset
  (`scratch/boot_chime_v0.1.0_20261022.wav`); the idle Finder is silent.
- **ROMs**: Kinka 1.0, 1.2, 1.3 and GM flash each boot Macintosh on Pippin to the Finder
  (5 MB, OSD Load ROM).
- **RAM**: 13 MB (v0.1.0) and 21 MB (build 32) boot Macintosh on Pippin to the Finder;
  Super Marathon at 21 MB to its launcher. The size Mac OS sees: the bench (`ram5/13/21.txt`
  on the Mac, MemTop at 108), since the KVM cannot open menus (About This Macintosh).
- **CD audio is silent**: Racing Days sends PLAY AUDIO MSF 1B:34:34-1B:3A:33 at ~17 s and
  1C:04:34-23:2E:05 (the menu music, 7.7 min) at ~27 s, both status 00, then polls READ
  SUB-CHANNEL; the car-select screen's audio records as zeros. Not investigated (the
  compatibility sweep). A first look (`scratch/tr_rd1.txt`): the target forwards the
  commands to the Main (blocks 7D47xxxx for PLAY AUDIO MSF, 7E42xxxx for READ SUB-CHANNEL,
  the trace's flags b4: cd_ok, the disc mounted), but no AUDIO STATUS (7ECC0000) or frame
  (7C000000) block appears; whether Pippin_cdaudio's channel requests are traced at all
  (kind 18 is the target's `t_rq`) is the first thing to check.

## Saves (the flash): what happens

- The 68k Flash! driver (FFCCE4A0-FFCCEC26) keeps the volume in **Taos's VRAM at
  F00E0000-F00FFFFF**. At boot it reads the flash's 130C-130F (a signature; FF here) and
  copies the flash into VRAM only if it matches; the volume then lives in VRAM. Creating a
  folder and putting the volume away touch the flash not at all (tr_fl2). Our VRAM is in
  DDR3, which a core reload and the memory test leave alone: so the Flash! volume and its
  folders survive core reloads although the flash itself is blank (a real Pippin's VRAM is
  lost at power-off).
- At **Shut Down** (the PC keyboard's Menu key is the ADB power key: `misterkvms-cli key
  compose` gives the shut-down dialog, Return) the driver writes the volume back sector by
  sector: compare, erase (80/30, then poll the byte for bit 7 and FF, up to 5,000,000
  reads), program the bytes that differ (A0), with the command bytes from a table in ROM
  (FFCCE5A0 reversed wiring, FFCCE5B0 straight). The first capture (tr_fl3, build 32) shows
  sector 0 erased and then nothing more programmed before the power-off; the erase's sweep
  flooded the trace (one record a byte), so what followed is not known yet.
- The save module works: 2 s after the flash changed it wrote the image (the erased flash,
  all FF) to `games/Pippin/Pippin flash.sav` on slot 2 (mounted through OSD Advanced >
  Save flash; Main remembers it in `config/Pippin.s2`).
- Build 33 (3731652): the trace takes the flash's line accesses too and an erase sweep as one
  record. The shut-down capture (tr_fl4): erase sector 0, three polls reading FF, then the
  program sequence (AA 55 A0, the byte 00 at 0), the read-back FF, a retry, the same, and
  nothing more: **our flash answered FF during its erase sweep** (so the driver took the
  erase as done) and the program, arriving while the sweep held the RAM port, was dropped.
- **Fixed (38ac0a1)**: during an erase a read answers the embedded algorithm's status (DQ7 0,
  DQ6 toggling, DQ3 1) and writes are ignored; the flash bench (`make flash`) gains the
  driver's sequence; PASS. **And 53670e3**: `VRAM_CLEAR`, the VRAM's DDR3 zeroed once at FPGA
  configuration, so a core load is a power-up for the Flash! volume too.
- **Build 34 (53670e3, debug; slack -0.023): saves work.** After the load Flash! is empty
  (0 items: the VRAM cleared, the image blank); a folder "Saved by MiSTer" made; the Menu
  key, Return (Shut Down): the image changes (md5 8772187b..., the signature "NuMc" at
  130C-130F, the bytes in the flash's own bit order); the core reloaded: Flash! holds the
  folder (`scratch/flash_save_roundtrip_20261022.png`).
