# Resume: the Pippin on the board (rewritten 2026-10-21 19:50)

Resume the Bandai Pippin MiSTer core's board bring-up. The core boots to the
Pippin logo on the board with correct NTSC video; a disc (Super Marathon)
does not boot because the board stalls in the floppy driver's init, about
16 s in. Read this whole file first; the day's evidence, entry by entry, is
in `LOG_pippin_board_20261021.md`; the plan is `docs/pippin_plan.md`, the
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
  Super Marathon at every core start.
- Debug build settings (the working tree): `BandaiPippin.sv` `CPU_MHZ = 58`
  (58.333 MHz), `TRACE = 1`, `PERF = 1`; `Pippin_machine` `TRACE_INT = 1`;
  DSPPC603's PERF block has the capture (below). A release build: TRACE 0,
  PERF 0, TRACE_INT 0, the capture's localparam off, the OSD's Boot entry
  removed or kept.

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

## The stall: what is known (details and evidence in the log)

1. Mac OS's floppy driver init (`.Sony`, ROM FFCF5C4E) runs at ~15.7 s on
   the board (10.3 s in the bench): the SWIM3 probe, the drives, then
   FFCF668E: `PrimeTime(500 ms)` on the TMTask at SonyVars+1EC (tmAddr =
   FFCF7BA2, stored at FFCF7B94), then FFCF7BC2, the wait: `movem.l
   d1-d3/a3,-16(a0)`, `tst.l 6(a0)` — tmAddr nonzero → `tst.l -20(a0)`, the
   continuation slot zero → `move.l (sp)+,-20(a0)` (the return address of
   `bsr FFCF7BC2` stashed), `rts` to the init's caller. When the task
   fires 500 ms later, FFCF7BA2 (in the Time Manager's T2 dispatch) jumps
   to the stashed FFCF66A0: the drives polled under `ori #$700,sr`, `bra
   FFCF668E` (prime again). The bench does exactly this (polls every
   503 ms, the disc boots to its splash at 700 M instructions).
2. **On the board the wait returns into the poll loop at once**: the first
   capture (`scratch/tr_cap1.bin`, stream `scratch/cap1_stream.txt`) shows
   the `tst.l 6(a0)` load of 81C76 giving **zero** and the `beq` to 7BD8
   taken, `rts` popping FFCF66A0 — the designed tmAddr == 0 path. (Another
   boot, `tr_pa1`, took the 7BCE path and ended in the poll loop through
   the slot being nonzero; boots vary a little.) The poll loop then primes
   again; the task fires at the next T2 (delta ~0), nests PrimeTime inside
   the masked section, and the Time Manager's queue ends self-linked (the
   TMTask at 81C70 with qLink = itself, tmCount 0): the walk at FFC3B488
   never ends, interrupts stay masked, the Pippin logo stays.
3. **So a store to the TMTask's line (81C60-81C7F) is lost or clobbered
   between FFCF7B94 and FFCF7BC8** — in InsTime (A058), PrimeTime (A05A:
   FFC3B3EA, the timer read FFC3B630 masking with `ori #$700,sr`, the
   insertion FFC3B432, the walk, the reload FFC3B4D8) or the trap
   dispatcher — on the board only.

## Ruled out (each with a capture or run in the log)

The trace machinery (TRACE 0/PERF 0 still stalls); Grand Central's VIA
event rules (dingusppc's either-edge is needed: rising-only breaks the
early ROM); the SDRAM controller and clock crossing (the memory test: 4 MB
clean over hundreds of passes; castout, dcbf, same-line misaligned loads
and the TMTask line's own sequence all clean); RAM contents (stale,
garbage, zeroed: all stall; the bench with garbage RAM passes);
translation (every sampled load's PA = EA); the CD data path (every block
read before the stall matches the image); the ADB device set (the
AppleJack makes the ROM's resolution differ — a side effect to look at
later: with it the keyboard ends at address 14 — but Controller: None
still stalls); the Main's CD latency, the real-time clock; timing-marginal
paths (the same stall across a dozen fits, slacks -0.84 to +0.38); the
ROM upload (the sampled ROM-resident and emulator code match the file).
The bench with the board's CPU clock ratio, memory latency, random extra
stalls, garbage RAM, the AppleJack, the CD latency and today's date runs
in lockstep with dingusppc, identical, and boots the disc every time.

## 20:10: the big capture read (`scratch/tr_cap2.bin`, `.txt`, stream `scratch/cap2_stream.txt`)

From FFCF7B8C: line 50 `stwx r4,r16,r27` **st 81C76** (tmAddr = FFCF7BA2, a
misaligned word store: r16 = a0, r27 = 6); InsTime (ROM FFC139xx, the trap
dispatcher, FFC3B3BC..) with `stbx` **st 81C74** (line 249, qType's byte);
PrimeTime (FFC3B3EA.., the timer read FFC3B630.., the insertion) with `stb`
**st 81C74** (979), `stw` **st 81C70** (1211, qLink), `stwx` **st 81C7A**
(1214, tmCount, misaligned); the `movem.l` **st 81C60..6C** (1567-1580);
then `lwzx r4,r16,r27` **ld 81C76** (1588) and the `beq` taken: **zero**.
Between 50 and 1588: 409 data accesses, 48 distinct lines, **no other line
of the TMTask line's cache set (index 0x63)**, no stack access on the
line. So the dcache returns zeros for bytes 76-79 after that sequence of
hits — most plausibly because the first store **missed** (the line was not
resident before line 50) and its two halves' merge lost against the
write-allocate fill's row write under the board's longer fill (a
latency-ordered race the bench's stand-in does not show). Under test:
**the memory test's new pattern** (the line flushed, the set's ways
dirty, the misaligned store, a delay, the byte and word stores, the
misaligned load; building 20:10), and **run19** (run5 with
`--mem-wait 48`, queued after run18 on the Mac) to flip the race in
lockstep. If the memtest pattern fails on the board, the fix is in
DSPPC603_cache's miss-with-store path (the merge of a misaligned store's
halves against the fill); verify it with the pattern, then the disc.

## What is running / where things stand (19:50)

- **Quartus: bc28258** (the capture from FFCF7B8C, 8,192 instructions),
  started 19:40, in its fitter; its waiter prints the slack. Then: put the
  core on .92 (`put-core`), `trace-capture 150`, load it through the OSD,
  fetch, decode, `python3 syn/capview.py scratch/tr_cap2.txt 0 8192 >
  scratch/cap2_stream.txt`, and read: the `stw` of tmAddr at 81C76 (is it
  there, what EA), every later access to 81C6x-81C7x and the stack
  (3FFExxx), the A-trap dispatch of InsTime/PrimeTime, PrimeTime's stores
  to the task (+0, +4, +10, +14: the last crosses into 81C80), until the
  `lwzx` of 81C76 that gives zero.
- **The Mac: run18** (bc28258, `run5.sh`'s options; `rep18.bin`,
  `runrep18.txt`), since 19:42, ~1 h; its capture of the same stretch is
  the reference stream: diff the two (`capview.py` on both; the 68k
  instruction sequence should match exactly, the PPC handlers too; where
  they part is the fault).
- The board holds the af1bff3 core (the first capture build); the
  previous cores are in `scratch/BandaiPippin_<commit>.rbf`.
- If the lost store is visible in the capture (e.g. the `stw` to 81C76 is
  there and a later store or the trap dispatcher's path overwrites it, or
  the `stw` goes to another EA), the fault is named: a CPU bug if the PPC
  stream itself differs from the bench's at identical instructions (then
  the lockstep bench should be made to replay the board's interrupt
  timing), or a nanokernel/emulator path the board's timing provokes.
  If the capture window ends before the load, raise the RAM again or
  trigger a second capture at FFC3B432 (PrimeTime's insertion).

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

- The AppleJack and the ROM's ADB address resolution (above).
- Kickstart (`~/repos/Pippin_Kickstart`) needs the signed
  `pippin-kickstart-1.1.iso` from blitter.net; the user has not said yes to
  downloading it.
- The 603e's page-crossing alignment rule (`docs/DSPPC603_notes.md`), not
  implemented.
- Grand Central's other sources (MESH, SCCs) have the same "event only at a
  line change" exposure the VIA had.
- Timing: 70 MHz fails by 1.8-2.7 ns; the worst paths are Pippin_sdram's at
  100 MHz (0.012 ns) and the CPU's fq_a_mem_r/cr[5] (0.14 ns).
- The plan's remaining days: CD audio (Racing Days), compatibility, release
  (`docs/pippin_plan.md`).
