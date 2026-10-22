# Resume: the Pippin on the board (rewritten 2026-10-22 04:10, at v0.1.0)

Resume the Bandai Pippin MiSTer core's work on the board. **State: released
v0.1.0.** The stall that blocked every disc (~16 s into the boot) is found
and fixed; Super Marathon, Racing Days, Power Rangers Zeo and Macintosh on
Pippin boot to their first interactive screen; the keyboard and the mouse
reach Mac OS. Read this file first. The hunt's evidence, entry by entry,
is in `LOG_pippin_board_20261021.md` (the morning) and
`LOG_pippin_board_20261022.md` (the evening and the night); the plan is
`docs/pippin_plan.md`, the titles tried `docs/compatibility.md`, the
MacPPC7300 candidate fixes `docs/fix_macppc7300.md`.

## Rules the user set (follow them)

- **Work on your own** (said 2026-10-21): decide and run builds, board
  captures and bench runs without asking, within the rules below, and report
  results. Ask only for things outward-facing beyond this workflow (pushing
  `pippin` to origin is part of it: the Mac pulls from GitHub).
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
- Do not modify the MacPPC7300 repository; candidate fixes go to
  `docs/fix_macppc7300.md`.
- The core is **BandaiPippin** (Quartus project, `_Console/BandaiPippin_
  <date>.rbf`); its OSD name is **Pippin** (`games/Pippin`, `config/Pippin.*`).

## Where things are

- Repo `~/repos/ApplePippin_MiSTer`, branch `pippin`, pushed to origin and
  pulled on the Mac. Main_MiSTer worktree `~/repos/Main_MiSTer-pippin`
  (`pippin-cdrom`; never switch the shared `~/repos/Main_MiSTer`). On .92:
  `/media/fat/MiSTer` is the consolidated Main; `games/Pippin` has boot.rom
  (Kinka 1.3), the other ROMs, Super Marathon (CUE/BIN), Racing Days,
  Macintosh on Pippin, Power Rangers Zeo (CHD); `config/Pippin.s4` mounts
  the last disc chosen at every core start (Macintosh on Pippin now).
- Build settings (`BandaiPippin.sv`): `CPU_MHZ = 58` (58.333 MHz); the
  tree is at the release's `TRACE = 0`, `PERF = 0` (slack +0.201). A
  debug build sets `TRACE = 1`, `PERF = 1` (the instruments below; slack
  then -0.3 to -0.65, which never mattered to the fault but is no release).
  `Pippin_machine` `TRACE_INT = 1` stays (it only gates trace records).
- Releases: `releases/<rbf>` committed, a tag, `gh release create` with the
  rbf and `releases/README.md` as the notes (v0.1.0 = build 30 = 64bdeb2).

## The instruments (all in the working tree, all decoded by `syn/mister.py trace`)

- Kind 4: with TRACE_INT, every write to Grand Central's interrupt registers
  and the VIA, **every VIA read**, every SWIM3 and ESCC access and the
  floppy DMA channel, the memory test's DBG registers, and one in 256 of
  the interrupt registers' reads. Kind 16: the interrupt state every 2^22
  cycles; **kind 17: the same at every change of the events or the CPU's
  interrupt line**. Kind 18: every block of the card the SCSI target gets
  (LBA, XOR: `syn/cdxor.py IMAGE.BIN --check TRACE.txt`). The trace ring
  holds 16,384 records (`Pippin_trace`, `trstream.py`, `mister.py`,
  `core_main.cpp`).
- Kind 14: DSPPC603's PERF sample every 8,192 cycles (256 in the dense
  window: 20 ms after SWIM3's interrupt is enabled, `Pippin_system`
  `cpu_dbg_dense` from int_dbg[115]): PC, instruction, MSR, the last
  exception, **the last load's effective and physical address**.
  `syn/tmview.py TRACE.txt [after] [before]` (the Time Manager's view from
  the SWIM3 mask write), `syn/pctrail.py TRACE.txt [after] [before]` (the
  samples labelled by ROM routine: the Time Manager, the floppy driver).
- **Kind 19: the capture** (DSPPC603 g_perf): from the first data access
  the cache takes with EA `DBG_TRIG_EA` (a localparam, now 0xFFCF7B8C, the
  emulator's fetch of the floppy driver's prime routine), every instruction
  leaving EX (PC, word, the last data access's EA and write bit), 8,192 of
  them in a RAM of 4,096 pairs, drained afterwards as one record per 64
  cycles. `syn/capview.py TRACE.txt [FIRST [COUNT]]` prints the stream
  disassembled (Retro68's `powerpc-apple-macos-objdump`). The 68k
  emulator's RAM image (PCs 68xxxxxx) is the ROM at offset +0x300000;
  the ROM is disassembled with `objdump -b binary -EB -m powerpc:common
  --adjust-vma=0xffc00000` (PPC) and `m68k-apple-macos-objdump -b binary
  -m m68k --adjust-vma=0xffc00000` (68k), both in
  `~/repos/Retro68-build/toolchain/bin/`.
- The board's memory test (Advanced > Boot: Memory test, Apply and reset;
  `verilator/progs.py memtest` generates `Pippin_bootrom.sv`): one pass
  over the contiguous 4 MB, the RAM zeroed, then the castout phase
  (status 5: castout and dcbf patterns, same-line misaligned loads, the
  TMTask line's own store sequence), status 6 at the end; its DBG writes
  are in the trace.
- The bench (`verilator/run_machine.py`, the Mac): `--mem-wait N` (the
  SDRAM stand-in's latency; the real controller takes ~24 memory clocks a
  line), `--stall P`, `--cpu-mhz`, `--disk-latency`, `--clock`, `--ram-fill
  SEED`, `--joy MODE` (5 = the AppleJack), `--boot memtest` (with
  `--rom ""`), `--trace-out` (the same records as the board's trace).

## The stall, resolved (the whole story in LOG_pippin_board_20261022.md)

Every title stalled ~16 s in: the floppy driver's init primed a Time
Manager task (the 500 ms disk-insertion poll), then its wait found the
task's `tmAddr` zero ("already fired"), primed it again, and the second
InsTime linked the task to itself: the Time Manager's walk looped with
interrupts masked. `tmAddr` was zero because **the TMTask lives in a
cache-inhibited page**, so its byte and misaligned stores are partial
SDRAM word writes, and **on MiSTerss1 a WRITE beat with both DQMs high is
executed anyway, as zeros** (a single-byte mask works; the Sun-2 core's
controller never issues a fully masked halfword): InsTime's byte store
zeroed `FFCF`, the tmCount store zeroed `7BA2`. Proven by the memory test's
cache-inhibited pattern (200,001 failing rounds with DQM masking, 0 with
the fix) and the memory-port trace of the line. **The fix: `Pippin_sdram`
writes a partial word by read-modify-write (`RMW = 1`, bfcfb4f).** Why the
chip ignores a fully masked beat is not explained (the logic, the timing
report and the pins all check out); MacPPC7300's identical controller has
the same latent problem on this board. The hunt's instruments remain in
the tree: the capture (`DBG_WATCH`, `DBG_TRIG_EA`, hard-wired to the
TMTask), the memory-port trace (`TRACE_RAM_LINE`), the memory test's
status-5 patterns, the SDRAM bench (`make sdram`), `syn/boardcap.sh`.

## What works, what is missing (2026-10-22)

- **Boots** (build 29/30): the four titles above; mount another disc from
  the OSD's first item (the file browser), then reload the core (the core
  list opens on the last entry used, so `F12, right, enter, enter`).
- **Input**: keyboard and mouse verified in the Finder (misterkvms-cli's
  `key`, `mouse move`; Mac OS accelerates relative moves ~5x; `mouse pos`
  is not absolute on this core). The **AppleJack** (OSD Input >
  Controller, the MiSTer gamepad through Pippin_adb) is implemented but
  untested: it needs a real gamepad. In the games the system pointer
  sits at the top-left; they take the pad.
- **Sound**: AWACS and CD audio (Pippin_cdaudio, through the Main's Mac
  CD layer) mixed to HDMI, the MT32-pi option — MacPPC7300's path; the
  boot chime's DMA runs. **Not verifiable remotely** (the KVM stream
  carries no audio): listen on the board. Racing Days' menu runs no sound
  DMA, so its music would be CD audio, untested.
- **Not yet done**: playing a title through, CD audio, the flash save,
  Kickstart (needs the signed `pippin-kickstart-1.1.iso`; not downloaded).
- **Open problem: Athens never gets Mac OS's video clock** (below).
- **Timing**: 58 MHz; 70 MHz fails by 1.8-2.7 ns (Pippin_sdram's and the
  CPU's fq_a_mem_r/cr[5] paths). RAM 5 MB; the OSD's 13/21 MB are
  MacPPC7300's, untested on the Pippin's map.

## Next steps

1. With a gamepad on the board: the AppleJack in Super Marathon / Racing
   Days (does the pad steer, do the buttons work; "Stick moves pointer").
   Listen for sound (the chime, Racing Days' CD audio).
2. Play each title a few minutes; note what breaks in `docs/compatibility.md`.
3. Athens's video clock (open problem below).
4. The DQM quirk: a scope on DQML/DQMH at the module during a fully masked
   WRITE, or the same memory test on another MiSTer (.94 answers SSH with
   a changed host key and has no KVM), to know whether it is this module;
   then MacPPC7300's controller gets the same RMW.
5. Housekeeping: the hunt's instruments could move behind a parameter
   (the capture RAM costs 4,096 x 194 bits), the memory test's status-5
   patterns are permanent regression tests.

## Open problem 2: Athens never gets Mac OS's video clock

On the board and in the bench the ROM sends Cuda `01 22 52 03 01`, `01 22
52 01 10`, `01 22 52 02 2E` (14.375 MHz) at the start, then one write to
I2C 0x28 (no device) and `07 82`, and no Athens write after that; Mac OS's
driver never reprograms Athens. dingusppc's Pippin takes a different early
branch because it finds no save flash (ours has the AMD ID at 40000000, as
the real machine). `STD_DOT` in `Pippin_taosvideo` keeps the picture right
meanwhile. A logging change sits in the cached dingusppc clone
(`~/.cache/applepippin/dingusppc/devices/common/clockgen/athens.cpp`,
"ATHENSLOG"): revert with `git -C ... checkout` when done.

## Other open items

- The AppleJack changes the ROM's ADB address resolution (a side effect seen
  in the bench, `LOG_pippin_board_20261021.md`); harmless so far.
- Kickstart (`~/repos/Pippin_Kickstart`) needs the signed
  `pippin-kickstart-1.1.iso` from blitter.net; the user has not said yes to
  downloading it.
- The 603e's page-crossing alignment rule (`docs/DSPPC603_notes.md`), not
  implemented.
- Grand Central's other sources (MESH, SCCs) have the same "event only at a
  line change" exposure the VIA had.
- Timing: 70 MHz fails by 1.8-2.7 ns; the worst paths are Pippin_sdram's at
  100 MHz (0.012 ns) and the CPU's fq_a_mem_r/cr[5] (0.14 ns).
- The plan's remaining days (`docs/pippin_plan.md`): CD audio (Racing Days)
  and compatibility; the release is done (v0.1.0).

