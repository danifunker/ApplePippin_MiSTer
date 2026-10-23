# Resume: the Pippin on the board (rewritten 2026-10-22 19:00)

Resume the Bandai Pippin MiSTer core's work. **State: v0.1.0 released
(04:00); since then the afternoon's work below, not yet a release.** Read
this file first. The afternoon's evidence is in `LOG_pippin_board_20261022_pm.md`;
the stall's hunt in `LOG_pippin_board_20261021.md` and `LOG_pippin_board_20261022.md`;
the plan is `docs/pippin_plan.md`, the titles and tests `docs/compatibility.md`,
the MacPPC7300 candidate fixes `docs/fix_macppc7300.md`.

## Rules the user set (follow them)

- **Work on your own** (said 2026-10-21): decide and run builds, board
  captures and bench runs without asking, within the rules below, and report
  results. Ask only for things outward-facing beyond this workflow (pushing
  `main` to origin is part of it: the Mac pulls from GitHub). **Everything on
  `main`** (said 2026-10-22 evening; `main` was fast-forwarded to `pippin`,
  which is kept but no longer used; no side branches).
- **One simulation at a time per box** (machine_tb, machref, run_core,
  run.py). **Quartus on this Linux box, Verilator on the Mac only**
  (`ssh dani-dev.local`, tools under `zsh -lc`, Homebrew's Verilator 5.052,
  `VJOBS=6`). The checkouts stay in step through git (push here, `git pull`
  there; the Mac clones over HTTPS). Not in git and present on both at the
  same paths: `scratch/pippin/` (ROMs, discs), `~/repos/Main_MiSTer-pippin`,
  `~/.cache/applepippin/dingusppc`. Bench runs there live in
  `~/pippin_bench/` (`runN.sh` scripts, `repN.bin` traces, `runrepN.txt`
  logs; `run5.sh` is the template: lockstep, `--module 32 --mem-wait 20
  --cpu-mhz 58.333`, `-GSOUND_IN_DMA=0 -GCUDA_FAST_BOOT=0 -GCPU_HZ=58333333
  -GCPU_HZ_FAST=58333333`, Super Marathon, to 420 M instructions; copy it
  with `sed -e s/rep5/repN/g -e s/runrep5/runrepN/g`, start it with
  `nohup`, watch `runrepN.txt` for `progress`, `MISMATCH`, `RESULT`).
- **Every Quartus flow under `flock /tmp/quartus.lock ...`** (shared with the
  other sessions). A full compile is ~25 min: `nohup flock /tmp/quartus.lock
  quartus_sh --flow compile BandaiPippin > LOG 2>&1 &` with Quartus 17's
  bin on PATH; the slack is in `output_files/BandaiPippin.sta.rpt`.
  **Commit before every build.** Keep the previous `.rbf`
  (`scratch/BandaiPippin_<commit>.rbf`): `put-core` removes the older dated
  copies on the board.
- Shell pitfall here: `pkill -f` / `pgrep -f` inside a tool command matches
  the command's own shell line (and a `kill` on a grep of "quartus" hits
  one's own wrappers): kill by PID from `ps -eo pid,args`.
- **Boards**: copy files over SSH (`syn/mister.py put-core`), **load cores
  and drive the screen only with misterkvms-cli through the OSD**, never
  mrext's `/api/launch`:
  `~/Downloads/MiSTerKVMS-0.9.5-linux-x86_64/misterkvms-cli --mister
  192.168.99.92` (`screenshot F.png`, `key F12|up|down|left|right|enter|
  backspace`). The board is **192.168.99.92** (MiSTerss1), SSH root with
  `~/.ssh/id_rsa` (`MISTER_KEY=~/.ssh/id_rsa`). OSD paths that work: from
  the core page `F12, right` is the System page with "Core" first (`enter,
  enter` loads BandaiPippin, the highlighted entry); `F12, down x6, enter`
  is Advanced (Boot: ROM / Memory test; `backspace, down, enter` = Apply
  and reset); `F12, down x4, enter` is Input (Controller). A capture:
  `python3 syn/mister.py trace-capture SECONDS` before loading, then
  `scp root@192.168.99.92:/tmp/trace.bin OUT.bin` once `/tmp/trstream.log`
  says `records`, then `python3 syn/mister.py trace --file OUT.bin > OUT.txt`.
  The OSD reopens on the page last used: screenshot before navigating. The
  KVM records the HDMI audio (`record 25s F.wav`, no ffmpeg): sound is
  checkable remotely. It cannot hold a mouse button (no Mac menus); Alt is
  Command; `key compose` (the PC Menu key) is the ADB power key (Mac OS's
  shut-down dialog, Return = Shut Down). The DDR3 trace ring survives core
  reloads, so a capture holds older sessions' records too.
- **Boards are shared**: the Sun-3 session uses .143 (MiSTerPi) and stays
  off .92; Quartus builds queue on the same lock.
- Do not modify the MacPPC7300 repository; candidate fixes go to
  `docs/fix_macppc7300.md`.
- The core is **BandaiPippin** (Quartus project, `_Console/BandaiPippin_
  <date>.rbf`); its OSD name is **Pippin** (`games/Pippin`, `config/Pippin.*`).

## The user's priorities (2026-10-22, after v0.1.0)

Phase 0 the instruments behind switches (done) → 1 Grand Central's other
interrupt sources (done) → 2 Athens's video clock (cause found, one value
open) → 3 the 603's page-crossing alignment rule (branch `align603`, in
test) and regression tests (done). Then other ROMs, RAM sizes, saves (done,
saves fixed). The compatibility sweep (playing, CD audio) later. The clock
goes up (66/70 MHz) later. **The user is away from the board and will say
when they are there** (gamepad: the AppleJack; listening).

## Where things are

- Repo `~/repos/ApplePippin_MiSTer`, branch **`main`** (pushed; the Mac pulls),
  plus `align603` (pushed, held off `main` until the user decides; see below).
  Main_MiSTer worktree `~/repos/Main_MiSTer-pippin` (`pippin-cdrom`, rebased
  2026-10-22 onto upstream master 065d0d2 at the user's request: 7729396 the
  Pippin in the Mac SCSI family, 54632e3 the CHD pregaps, bae97b3 a data read
  leaves CD audio playing on the Pippin; local only, not pushed to the fork);
  its `bin/MiSTer` is the Main on .92 (cross-compiled with
  `~/gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf/bin` on PATH; the
  previous one kept as `/media/fat/MiSTer.prev-20261022-2156`). The Mac's copy
  of that worktree lacks the CD-audio commit (the bench's `maincd`). On .92: `games/Pippin` has
  boot.rom (Kinka 1.3), Kinka 1.0/1.2/1.3/GM flash, the four discs, and
  `Pippin flash.sav` (128 KB, mounted on slot 2 through Advanced > Save flash;
  `config/Pippin.s2`); `config/Pippin.s4` mounts the last disc (Macintosh on
  Pippin now). `_Console/BandaiPippin_20261022.rbf` on .92 is **build 34**
  (53670e3, a debug build), not v0.1.0 (that is `releases/` and
  `scratch/BandaiPippin_release30.rbf`).
- Builds today (`scratch/BandaiPippin_<commit>.rbf`, logs `scratch/buildNN_*.log`):
  31 2f9b0eb release flags (-0.039, not on the board); 32 9f5e92b debug
  (+0.274); 33 3731652 debug (+0.128); 34 53670e3 debug (-0.023, on .92).
- `BandaiPippin.sv` now: `TRACE = 1`, `TRACE_FL = 1` (debug). **A release sets
  `TRACE = 0`, `TRACE_FL = 0`** (and keeps `PERF`, `CAPTURE`, `DENSE`,
  `TRACE_RAM` at 0).
- The Mac (`~/pippin_bench`): `chainram.sh` (the bench at 5/13/21 MB to 400 M,
  `ram5/13/21.txt`, MemTop at 108: 5 MB gives 004EC000 = 5,040K, Kickstart's
  figure), then `chainalign.sh` (checks out `align603`: `run_core.py` →
  `runcore_align.txt`, then the lockstep boot run29; back to `pippin`;
  `chainalign.txt` ends with `done`).

## The instruments (switches in `BandaiPippin.sv`; all decoded by `syn/mister.py trace`)

- `TRACE` (the DDR3 trace) with `TRACE_INT` (Pippin_machine, always 1: GC's
  interrupt registers, the VIA, SWIM3, ESCC, the memory test's DBG; kinds 4,
  16, 17), the SCSI target's blocks (kind 18).
- `TRACE_FL` (2026-10-22): the save flash's CPU accesses (word and line), and
  at 4F000000 + kind (1 an image block loaded, 2 an image block read for a
  save, 3 the CPU programmed/erased, once per run): `FLASH` lines.
- `PERF` (kind 14 samples), `DENSE` (256-cycle samples for 20 ms from
  SWIM3's interrupt enable), `CAPTURE` (DSPPC603's instruction capture, kind
  19, `syn/capview.py`; `CAP_TRIG_EA`, `CAP_WATCH`, `CAP_WATCH_A`), `TRACE_RAM`
  (one RAM line at the memory port, `TRACE_RAM_A`, with Pippin_sdram's `DIAG`
  word). All 0 now.
- The memory test (Advanced > Boot), the bench (`verilator/run_machine.py`,
  options as before), `make sdram` / `make sdram-normw` with `--dqm-quirk`,
  `make flash`, machref (`~/.cache/applepippin/machref/machref`, here; with
  `--machine pippin --cpu 603 --pvr 00030302 --ram 4 --set rambank1_size=4
  --set rambank2_size=1 --set rambank3_size=0 --set rambank4_size=0`;
  `--trace-from 1`, not 0; `MACHREF_LOG=0` shows INFO lines such as
  ATHENSLOG, the logging still in the cached dingusppc clone's athens.cpp).

## What changed today (details in the pm log)

- **Phase 0** (2f9b0eb): the hunt's instruments behind the switches above.
- **1, interrupts** (1156710, `INT_REPORT`): in 68k mode an access leaving
  MESH's, SWIM3's, the ESCC's, MACE's or Curio's line high is an event (the
  VIA's rule); every DMA interrupt is an event (dingusppc's ack_dma_int).
  run28 (lockstep boot) PASS; the titles boot.
- **2, Athens** (cd2424d, 9f5e92b): the ROM's flash probe (E1 at F00DFFFA
  when the save flash answers) sends Mac OS's Taos driver to the **second
  Athens at I2C 28**, which we lacked. Now present; the driver writes only
  its P2_MUX2 = 02. Its power-up D2/N2 are unknown (0B/1B would give NTSC's
  24.545 MHz exactly), so `STD_DOT = 1` (the standard rate) stays.
- **3, regressions** (88ba866): the SDRAM bench's `--dqm-quirk` (PASS with
  RMW, FAIL without: 1,255 differences).
- **Saves fixed**: the Flash! volume lives in VRAM (F00E0000-F00FFFFF; the
  68k driver FFCCE4A0-FFCCEC26) and is written back at Shut Down (erase,
  poll, program). Our flash answered FF during its erase sweep, so the
  driver's program was lost (38ac0a1 answers the status: DQ7 0, DQ6
  toggling, DQ3 1). And the DDR3 kept the VRAM over core reloads, so an
  unsaved volume survived (53670e3 `VRAM_CLEAR` at FPGA configuration).
  Build 34: folder made, Shut Down, image written, core reloaded, folder
  back.
- **Board results**: all four ROMs boot Macintosh on Pippin; 13 and 21 MB
  boot (Super Marathon at 21 MB too); the chime plays on HDMI
  (`scratch/boot_chime_v0.1.0_20261022.wav`); **CD audio is silent** (Racing
  Days's PLAY AUDIO MSF accepted, the menu records as zeros).

## Late on 2026-10-22: the user's next list (their order: the second controller first)

- **Second controller** (ea881f5): Pippin_adb's aj2, a second AppleJack from joystick 1 (OSD
  Input > AppleJack 2, default Yes, with Controller = AppleJack). Bench (`runaj2.txt`, --joy 5
  --joy2): the ROM's address resolution separates them (mouse 15, joy 14, aj2 3); both stay
  handler 01 until a game's driver sets 46. Needs two pads on the board (the user).
- **Flicker** (d7ba2eb): OSD Video > Interlace, Progressive (default: every frame-buffer line
  each field, 31 kHz, the vertical blank unchanged) or Original (the fields).
- **Settings** (28d3b79): the slot-2 image holds the flash and then Grand Central's 8 KB NVRAM
  (136 KB; 128 KB images keep the flash alone); each region saved 1 s after its last write.
  On the board the 136 KB load works; no boot so far has written the NVRAM (dingusppc's boot
  without a disc never touches it either), so the save of that region is unexercised. The
  board's image is 136 KB now (`Pippin flash.sav`; the 128 KB copy `.sav.128k-backup`).
- **Video clock**: the driver writes only P2 = 02 to Athens 28 whatever the monitor (bench
  runmon3/6: PAL, VGA). Hypothesis: Athens 28 (straps ~24.5 MHz) halved for NTSC and whole
  for VGA, PAL from Athens 29 (the ROM's 14.375 MHz = 920 x 15,625 Hz); check the PAL timing
  the ROM writes to Taos (HPIX 918?).
- **66 MHz**: later ("soon"); build 37's failing paths are DSPPC603's (ex_b -> cr, msr ->
  TLB valid; one of its three boots failed). **Build 38** (3acff21, seed 3, slack +0.120):
  on .92, three core loads boot Macintosh on Pippin; Video > Interlace and Input > AppleJack 2
  in the OSD.
- **Instant saves** (6961fda, build 39): measured on .92 with build 38 (2026-10-23): a folder
  made on Flash!, the image's mtime unchanged for five minutes; Restart (power key, R) wrote
  it 4 s later; the Finder refuses to put away the startup CD. So Mac OS writes the volume
  only at Shut Down or Restart (a real Pippin's eject of the boot disc restarts). The VRAM
  copy at DDR3 300E0000 equals the CPU's view of the flash byte for byte (2 bytes differed:
  dates touched after the restart). OSD Advanced > Flash! saves: Instant (default) mirrors each
  VRAM store into F00E0000-F00FFFFF into the flash (Pippin_flash mir_*, armed by the driver's
  read of 130C, cleared by reset), so the SD image follows 1 s later; At Shut Down = before.
  An OSD disc change does not restart the Pippin (the media just changes under Mac OS).
  Build 39 (6961fda, slack +0.078; `scratch/BandaiPippin_6961fda.rbf`, on .92 as
  `_Console/BandaiPippin_20261023.rbf`) is untested on the board: .92 was running
  IBMRS6K7248 for another session. Test: folder on Flash!, the image's mtime within ~2 s,
  core reloaded without Shut Down, the folder still there.
- **PPP**: after these; port MacPPC7300's serial DMA (a13d565 ... f8ff304), also its SDRAM
  DQM-on-A12/A11 fix (35af5ad) and Cuda's time-set flag (c65af4a).

## Next steps

1. When `chainalign.txt` says `done`: `run_core.py` and run29 PASS → merge
   `align603` into `main` only if the user wants the rule (it slows the boot:
   run29 at 150 M instructions 534.6 M cycles against 364.3 M), push. If
   run_core's lockstep random programs with translation trip on the new
   exception (dingusppc does not take it), hand it to the reference there
   as `core_main.cpp`'s machine branch does.
2. The RAM-size numbers (`ram13.txt`, `ram21.txt`: MemTop) into
   `docs/compatibility.md` (targets 13,312K and 21,504K, About This Mac).
3. A release build: `TRACE = 0`, `TRACE_FL = 0`, commit, build, the four
   titles and a save round trip on .92, then v0.2.0 (`releases/`, tag,
   `gh release create` with `releases/README.md` updated: saves, ROMs, RAM,
   the chime; CD audio silent).
4. CD audio: fixed (build 36 + the Main's bae97b3; Racing Days's menu music
   plays). The rest of the compatibility sweep stays for later.
5. Athens 28's power-up D2/N2 (a real Pippin, or Apple's data), then
   `STD_DOT = 0`.
6. With the user at the board: the AppleJack in the games.
7. Later: the clock (70 MHz fails by 1.8-2.7 ns), Kickstart (needs the user's
   yes to download), the DQM quirk on another board, the PVR (the real unit's
   is 00030302; ours 00030100; nothing in the ROM depends on the revision).

## Other open items

- The AppleJack changes the ROM's ADB address resolution (bench side effect,
  `LOG_pippin_board_20261021.md`); harmless so far.
- MacPPC7300's controller has the same latent DQM problem (`docs/fix_macppc7300.md`).
- Two untracked screenshots in the repo root (`s7_boot.png`, `s7_rom_70s.png`,
  2026-10-21): the user has not said whether to keep them.
