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

## 20:30: the two captures compared (`scratch/cap2_stream.txt` the board, `scratch/rep18_stream.txt` the bench, run18)

The bench's capture of the same stretch (rep18, `--mem-wait 20`, no
lockstep) **runs the identical 68k code and PPC handlers** until the floppy
driver's wait: only the heap addresses differ (the TMTask at 81AC0 in the
bench, 81C70 on the board; the 68k stack 76DA / 24E4A), and the Time
Manager's walk passes one task more on the board (a different queue, not a
fault). The driver (Kinka 1.3, the ROM the board and the bench run —
**do not disassemble the 1.0 ROM**; `scratch/pippin/...kinka 1.3...rom`):

    FFCF7B8C  movem.l d0/a1,-(sp); lea 7BA2,a1; move.l a1,6(a0)   ; tmAddr   <- st 81C76 (line 51)
              InsTime (A058); movem.l (sp)+; PrimeTime (A05A); rts
    FFCF7BA2  the task: move.l a1,a0; RmvTime; clr.l 6(a0); move.l -20(a0),d0; beq; clr.l -20(a0); ...jump to it
    FFCF7BC2  the wait: movem.l d1-d3/a3,-16(a0)                  <- st 81C60..6C
              tst.l 6(a0); beq.s 7BD8                            <- ld 81C76 (line 1588)
              tst.l -20(a0); bne.s 7BDC (DEBUGGER)
              move.l (sp)+,-20(a0); moveq #0,d0; rts             ; the continuation stashed, returns to the caller's caller
    FFCF7BD8  moveq #0,d0; rts                                   ; "the task already fired": return at once

On the board `tst.l 6(a0)` reads **zero** and the wait returns at once
(FFCF7BD8 -> the poll loop FFCF66A2 -> prime again, the same task InsTime'd
twice: the self-link at the second PrimeTime, FFC3B4AA `move.l a0,(a1)` with
a1 == a0, lines 3653-3664). The bench reads FFCF7BA2 and stashes the
continuation (FFCF5D34.. afterwards). **Nothing stored zero at 81C76**: the
task (7BA6 `clr.l 6(a0)`) never ran; the writes to tmAddr's two words after
line 51 are the merges of InsTime's `move.b d0,4(a0)` (FFC3B3CA, st 81C74,
line 250), PrimeTime's byte store at 81C74 (FFC3B43A, 980) and the
misaligned tmCount store at 81C7A (FFC3B4A6, 1215; words 6 and 7). So **the
dcache merged those stores against stale words** (the line's pre-store
contents: zeros, NewPtr's fresh block) — a cache fault the bench does not
show. Which merge, and what it merged, is what the next capture shows.

Instruments added:
- **cac11e1: the capture carries the data** of the last access answered in
  the instruction word's place (a load's value as the register gets it, a
  store's first word as the cache merges it); `capview.py --rom ROM` reads
  the word back from the ROM and prints `= value` when the data changes.
  Not built yet.
- **864f43f: the memory test's pipelined same-line pattern** (status 5):
  `stw A; lwz; lwz A+12`, `stw A; lwz; stb A+13; lwz A+12`, `stw A; stb
  A+13; lwz A+12` — a store hit's write lands one edge after its lookup, at
  the edge the request after the next reads the row; the cache forwards
  the written words and takes the rest from the RAM read during that write
  (DSPPC603_cache_ram: altsyncram, mixed width 128/32, OLD_DATA; the
  Verilator model gives old data; if the M10K does not, that is the board-
  only fault). run20 on the Mac checks the pattern's expected values.

## 20:45: the stall's own sequence passes on the board

f089ba8's memory test on the board (slack +0.063; `scratch/tr_mt4.bin`,
`.txt`): pass 1 over 4 MB clean, status 5 (the castout patterns, the
TMTask-line sequence in three cache states, and the stall's own sequence:
the line out of the cache, the set's ways dirty, the misaligned store, a
delay, the byte and word stores, the misaligned load) 200,000 rounds with
**0 errors**, status 6. The write-allocate race hypothesis is out. run21 on
the Mac (864f43f's test, `--memtest-passes 2`, `runrep21.txt`): 0 errors
through the castout phase, so the pipelined pattern's expected values are
right (RESULT: FAIL there only means the 120 M instruction limit; the test
stops at status 6 and never reaches pass 2). Also checked: an interrupt is
taken only before an access's first grant (`mem_irq`), so a misaligned
store's second half cannot be dropped by one; the exception sites in the
samples match between the board and the bench; the Pippin build has no L2;
no other line of set 0x63 is touched between the store and the load.

## 21:20: the data capture read (`scratch/tr_cap3.bin`, `.txt`, `scratch/cap3_stream.txt`; 175d96a, slack -0.146)

The same stall, instruction for instruction (the TMTask at 81C70 again),
now with each access's data (`= value` on the line after the access it
belongs to). The misaligned tmAddr store (51, `stwx` after `lhau r6`)
presents its halves right: `0000FFCF` (81C74, bytes 2-3) and `7BA20000`
(81C78, bytes 0-1). InsTime's byte store (250) writes 00 to qType (81C74),
PrimeTime's `btst/bset` writes 80 and **reads 80 back** (992); qLink
`00057E22` (1212) reads back (3591); tmCount's misaligned store (1215,
`00000000`/`57820000`, the same `stwx` handler) **reads back `00005782`**
(3567) and, after the second insertion, `0000000B` 57 times in the walk.
Only the two halves of the first store are gone: `tst.l 6(a0)` reads
`00000000` (1590, and 4023 in the second round). So the misaligned load
and store paths work; what is lost is one store's bytes, with no external
cause: between 51 and 250 the CPU touches 15 lines, none other in set
0x63, no cache instruction, no mtspr, no exception; only the sound DMA
(DMA-8) ever runs on the board and it stopped at 8.96 s (no snoops at the
stall). The difference from tmCount's store is the line's state at 51
(the first touch in the capture: likely a miss) and what surrounds it (a
load hit on the ROM line just before, the next opcode fetch queued behind).

- **88aa1e8 (build 24, 21:06)**: the capture records a store's word **as
  the dcache lands it** (`dbg_st_word` = the merge of the bytes into the
  word read), not the window word. It shows whether the first half's merge
  already lacked FFCF (the row read stale, or a miss handled wrong) or
  whether the written word was lost afterwards.
- **4c4629e (build 25, queued)**: the memory test with the emulator's
  sequence: `lwz B; stw X,22(A); lhz 2(B)` with A out of the cache, in it
  clean, in it dirty (B another resident line).

## 21:40: build 24's capture (`scratch/tr_cap4.bin`, `cap4_stream.txt`; 88aa1e8, slack -0.332) — the instrument was too coarse

The same stall a third time, the PPC stream identical to cap3's (the
fault is deterministic). But the merged word never shows: the data field
is overwritten by the next load's value (the opcode fetch follows every
store within a cycle or two) before an instruction samples it. **efbf06e
(build 26)** records each store's landing as an entry of its own (`**
store landed ADDR = word` in capview; PC DEAD0000, bit 0 = a landing was
lost; one held a cycle behind an instruction's entry). The entries cost
capture room (8,192 entries in all), so the capture covers fewer
instructions; the wait's load is ~1,600 instructions in and the stores of
interest are 51, 250, 980, 1215, 1567-1580.

## 22:10: build 25's memory test passes on the board too (`scratch/tr_mt5.txt`)

4c4629e (slack +0.057): status 5 with the pipelined same-line pattern and
the emulator's own sequence (`lwz B; stw X,22(A); lhz 2(B)` with A out,
clean and dirty): **0 errors**. run19 (lockstep, `--mem-wait 48`): PASS,
identical. So neither latency nor these sequences reproduce it; what the
test still lacks is the line's history before the store (how it came into
the cache: a fill by a load, a store miss, a `dcbz` — the native Memory
Manager may clear the TMTask's block with dcbz — and in which way).
**3cfe8dc (build 27)** adds the dcbz-allocated cases, and **eadc78c (in
build 27 too, lint clean)** is the **line watch**: `DBG_WATCH = 1` in
DSPPC603.sv's g_perf turns the capture into a ring (4,096 pairs) running
from reset that records only what concerns `DBG_WATCH_LINE` (81C60): the
first instruction to leave EX after each access to the line, and every
write of the dcache's RAMs in its set 0x63 (a fill, a store's landing with
the merged word, a tag write: valid/dirty/way/state), then everything from
the trigger for DBG_AFTER = 1,800 pairs; capview prints the writes as
`** dcache store|fill|tag ...`. It shows how the line came into the cache
and what every write to it did, before and through the stall.
(OSD note: after a fresh core load Boot is ROM, so ONE toggle makes the
memory test pending; two cancel out.)

## What is running / where things stand (22:15)

- **Quartus: build 26 = efbf06e** (the store-landing capture) in its
  fitter (chain b4khbc21z, `scratch/BandaiPippin_efbf06e.rbf`): the disc
  capture round (`syn/boardcap.sh RBF cap5`), then `grep "store landed"`
  around the stores at 51/52, 250, 980, 1215. Then **build 27 = eadc78c**
  (chain b1h9rj4fj, `scratch/BandaiPippin_memtest27.rbf`): the memory test
  with the dcbz cases AND the line watch: the memory test round, then the
  disc capture round (`boardcap.sh`), then read the `** dcache` entries of
  the line's set before the trigger. **run22** on the Mac (efbf06e, no lockstep, 290 M
  instructions, `rep22.bin`; watcher bwz9tsfz2): the bench's store-landing
  stream for the same stretch, the reference to diff against.
  The Sun-2 session is done with .92 for now (22:00); it will ask first
  if it needs it again. Loading the Pippin core while the
  Sun-2 core is up: the OSD's core list opens the Sun-2's folder, so go
  `..` (backspace, enter), Console, then down to BandaiPippin (the 9th
  entry), enter — `boardcap.sh`'s `F12, right, enter, enter` assumes the
  Pippin core is the one loaded. For
  each: `syn/boardcap.sh RBF NAME` does a disc capture round (put the
  core, stream, load through the OSD, fetch, decode, the stream with
  `--rom`). The memory test on the board: `trace-capture` first, then OSD
  Advanced > Boot: toggle twice to Memory test, backspace, down, enter =
  Apply and reset (the test is over in ~3 s and the ring holds 2 s, so the
  streamer must run before the apply); `grep DBG` for the error count.
  **The board is shared tonight**: the Sun-2 session (another Claude
  session, "OSD refactor and SunOS chesstool") drives .92 from 21:15 for
  1-2 h; message it (SendMessage to its address) before each 5-minute
  round and when the board is back. 175d96a's disc capture is done
  (cap3); its memory test was not run (864f43f's pattern is in build 25
  too). (`capview.py scratch/tr_cap3.txt 0 8192 --rom "scratch/pippin/
  bandai pippin,19960920 - kinka 1.3,- 3e6b3ee4-a52528e9ce8c.rom"`), and
  read the data at the stores to 81C74/81C7A and the load of 81C76.
- **The Mac: run19** (run5 with `--mem-wait 48`, lockstep; `rep19.bin`,
  `runrep19.txt`), since 20:52, ~1.5 h: a DIVERGED/MISMATCH or a stall
  there would be the race in simulation. (`--memtest-passes 1` stops before
  the castout phase: use 2 and read the error count, as run21.)
- The board holds the f089ba8 core; earlier cores in `scratch/BandaiPippin_<commit>.rbf`.
- If every memory-test pattern passes on the board, the data capture
  decides; if it shows a merge against stale data, the next step is to
  reproduce that access timing in the memory test (the exact sequence of
  the 68k handlers between the stores: ROM fetches of other sets between
  same-line stores).

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
