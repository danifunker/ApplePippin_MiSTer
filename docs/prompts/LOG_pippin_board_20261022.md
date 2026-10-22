# Log: the Pippin on the board, 2026-10-21 evening to 2026-10-22 (the stall's hunt and fix)

The entries of `RESUME_pippin_board.md` as they were written during the hunt (moved here
2026-10-22 04:10 when the resume was rewritten as the state at v0.1.0). The morning's entries
are in `LOG_pippin_board_20261021.md`.

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

## 22:45: build 26's landings (`scratch/tr_cap5.bin`, `cap5_stream.txt`; efbf06e, slack -0.235) — THE TMTASK'S PAGE IS NOT CACHED

(cap5's `** dcache` lines are build 26's older entry format decoded by the
newer viewer: read them as `store landed EA = merged word`; the scratch
script in the log groups them.) Stores to the 68k stack page (003FF000)
and the low-memory page (00007000) land in the dcache; **none of the 22
stores to page 00081000 does** (nor to the device pages F3015000/F3017000,
as expected). So the TMTask's page is cache-inhibited (I = 1; a write-
through page would still land once a load had filled the line): every
access to it is an uncached word with byte enables, straight through
Pippin_machine, DSPPC603_memcdc and Pippin_sdram (a word = two halfword
WRITEs with DQM, or a READ burst). The dcache was never involved; the
memory test never exercised partial-word SDRAM writes (its data goes
through the cache as whole lines). The lost bytes are the two halves of
the misaligned tmAddr store (81C74 be=0011, 81C78 be=1100, two posted
writes back to back, crossing an 8-byte boundary); tmCount's halves (81C78
be=0011 — unprovable, the block was zero — and 81C7C be=1100, read back)
and the byte stores (be=1000) land. Read and found nothing by inspection:
Pippin_sdram's word write (two WRITEs on consecutive clocks, DQM with the
command, PRECHARGE 2 clocks after), DSPPC603_memcdc, the CPU's port
arbitration (data before instructions, the owner kept until the ack), the
dcache's posted-write rules (S_PWAIT while one is out).
**cd171e8 (build 28)**: the memory test does the TMTask's accesses through
DBAT2's cache-inhibited alias of RAM (EA 10000000 + A): the misaligned
stores as two partial words, the byte stores, the misaligned load, alone
and in the driver's order. If it fails: the fault is in the uncached word
write path (most likely the SDRAM controller's back-to-back partial
writes, or the posted write's hand-over on the port); fix, verify with the
test, then the disc.

## 2026-10-22 00:00: REPRODUCED AND LOCALIZED — masked halfwords are written as zeros (`scratch/tr_mt6.bin`, `.txt`)

Build 28 (832abbf's memory test + cb0d605's trace, slack +0.329) on the
board: **the cache-inhibited pattern fails from the first round**, 200,001
errors (one per round: the first failing check), the first at A = 5C280,
read 00000000. The memory test's pseudo-random A fell on the watched lines
81C60 and 81AC0 six times each, so the trace has the complete rounds with
the memory port's records and the SDRAM controller's diagnostic:

    stw Y,16(U)    RAM 81C70 sdram be f issued 2 col 038  w fff7c0ac
    stw X',22(U)   RAM 81C74 sdram be 3 issued 2 col 03a  w 0000ffff   <- lost
                   RAM 81C78 sdram be c issued 2 col 03c  w ffff0000   <- lost
    stb X,20(U) x2 RAM 81C74 sdram be 8 issued 2 col 03a  w 53000000
    stw Y,16(U)    RAM 81C70 ...
    stw Y,26(U)    RAM 81C78 sdram be 3 issued 2 col 03c  w 0000fff7
                   RAM 81C7C sdram be c issued 2 col 03e  w c0ac0000
    lwz 22(U)      RAM 81C74 r 53000000     RAM 81C78 r 0000fff7

The controller served every write with the byte enables as given (two
WRITEs, the right column). The read-backs fit exactly one rule: **a masked
halfword (DQM = 11) is written with the zeros the window carries in its
place instead of being skipped** — the byte store's masked second halfword
zeroes 81C74's bytes 2-3 (X' lost), the later misaligned store's masked
first halfword zeroes 81C78's bytes 0-1 (X' lost), while FFF7 and 53 land.
Replaying the driver's sequence with that rule: InsTime's `move.b
d0,4(a0)` (be 8) zeroes tmAddr's FFCF, PrimeTime's tmCount store (be 3 at
81C78) zeroes 7BA2, `tst.l 6(a0)` reads 0 — the stall. Everything else
checked out: Pippin_sdram and DSPPC603_memcdc are byte-identical to
MacPPC7300's (whose bench covered random byte enables against a chip
model), the dqm register is packed in the I/O cells, the datasheet report
(quartus_sta, `scratchpad/datasheet.txt`) has every SDRAM output changing
12.6-13.0 ns after the reference with the SDRAM_CLK edge 5 ns later, the
mode word sets single writes, DQMH/DQML are on AF13/AG13 as in sys.qsf.
So either DQM does not reach the chip on MiSTerss1's module (a hardware
fault would look exactly like this; .94 has SSH open but gave a host-key
warning and has no KVM, so it was not tried), or something subtler in the
I/O; cores that do not mask bytes (line and full-word writes: the memory
test's own sweep, MacPPC7300's Mac OS?) never see it.
**The fix (bfcfb4f, build 29): Pippin_sdram writes a partial word by
read-modify-write** (RMW = 1: READ the word in the open row, merge the
enabled bytes, WRITE both halfwords unmasked, ~12 clocks more per partial
write; RMW = 0 masks with DQM as before). The SDRAM bench (`make sdram`,
from MacPPC7300, with the chip model) passes with it on 32 and 128 MB
boards. run25 (the bench with the memory-port trace) shows the same page
uncached in the bench with every write landing.

## 04:00: v0.1.0 released; four titles boot; input verified

- **Release v0.1.0** (`releases/BandaiPippin_20261022.rbf`, tag v0.1.0,
  the GitHub release with the rbf): build 30 = 64bdeb2 (TRACE 0, PERF 0;
  slack +0.201). Verified on the board: Macintosh on Pippin boots to the
  desktop with it. Its notes: `releases/README.md`.
- **Compatibility** (`docs/compatibility.md`): Super Marathon (launcher),
  Racing Days (car select, animating), Power Rangers Zeo (menu), Macintosh
  on Pippin (the Finder) all boot with build 29/30 (screenshots in
  `scratch/*_boots_20261022*.png`). Mounting another disc: the OSD's first
  item (the file browser), then reload the core; the core list opens on
  the last entry used (BandaiPippin), so `F12, right, enter, enter` loads it.
- **Input**: in the Finder the mouse moves the pointer (Mac OS accelerates
  misterkvms-cli's relative moves ~5x; `mouse pos` is not absolute here),
  its button selects an icon, the keyboard selects icons by name. The
  AppleJack path (OSD Input > Controller) needs a real gamepad to test.
  In the games the system pointer sits at the top-left; they take the pad.
- **Sound**: not verifiable remotely (the KVM stream carries no audio);
  the path is MacPPC7300's (AWACS + CD audio mixed to HDMI, MT32-pi
  option) and the boot chime's DMA runs. Racing Days' menu runs no sound
  DMA (its music is probably CD audio: Pippin_cdaudio, untested). Listen
  on the board.
- The debug builds' instruments stay in the tree behind TRACE/PERF (the
  release has them off); the capture (DBG_WATCH, DBG_TRIG_EA) and the
  memory-port trace (TRACE_RAM_LINE) are hard-wired to the TMTask hunt.

## 00:41: FIXED — Super Marathon boots on the board

Build 29 (bfcfb4f + the Makefile fix, slack -0.647): the memory test's
cache-inhibited pattern passes (`scratch/tr_mt7.txt`: status 5, 0 errors;
200,001 with DQM masking), and **Super Marathon boots to its "CHOOSE ONE:
Marathon / Marathon 2" launcher** (`scratch/marathon_boots_20261022_0041.png`,
`scratch/tr_boot29.bin`, `.txt`: at 15.791 s the TMTask's line reads
`8000ffcf` after InsTime's byte store — tmAddr's FFCF survives the masked
half that used to zero it). The core is on .92 (`_Console/BandaiPippin_
20261022.rbf` = `scratch/BandaiPippin_rmw29.rbf`), the disc running.

Loose ends for the morning:
- The instruments are all still in (PERF's 4,096-pair capture RAM with the
  line watch, the kind-19 drain, the memory-port trace, the dense window,
  the extra kind-4 records, the RAM-sized memory test): a release build
  wants PERF's capture off (or DBG_WATCH 0 and a smaller RAM) and TRACE_INT
  0; the slack went from +0.3 to -0.65 with them (the fault never depended
  on timing, but the margin should come back).
- The quirk, refined (00:50, from the Sun-2 session: on this board a
  mask of one byte within a halfword works, and its controller never
  writes a halfword with no byte enables): **a WRITE beat with both DQMs
  high is executed anyway, as zeros**; a single-byte mask works (our byte
  stores landed). Why is not explained; a scope on DQML/DQMH would say
  whether the chip sees both high. A cheaper fix than the RMW would skip
  such halfwords (one line in S_WRITE); the RMW is what was verified.
  MacPPC7300's identical controller has the same latent problem here.
- Regression done: `make lint` clean, `make sdram` (the controller against
  the chip model, random byte enables) PASS on 32 and 128 MB boards, run25
  (the bench boot, 420 M instructions) PASS; run26 = the lockstep boot
  (run5) on the final tree: PASS (01:41, `runrep26.txt`).
- Then: the game itself (controller input through the AppleJack, sound),
  and open problem 2 (Athens's video clock) below.

## What is running / where things stand (00:15, superseded)

- **Quartus: build 29** = bfcfb4f + the Makefile fix (the RMW controller,
  the memory test with the uncached pattern, the traces), started 00:12
  (waiter: `scratch/BandaiPippin_rmw29.rbf`). Then on .92: the memory test
  (expect 0 errors in status 5), then **Super Marathon** (`syn/boardcap.sh
  scratch/BandaiPippin_rmw29.rbf cap6` — the capture still triggers at the
  prime routine; what matters is the screen: does the disc boot?). If it
  boots: the fix is confirmed; clean up (the instruments can stay, PERF's
  capture costs RAM: consider DBG_WATCH/the capture off for a release),
  rerun the CPU's and the machine's regression (`make lint`, the sdram
  bench, the lockstep boot run5), update the notes, save the memory.
  If the memory test passes but the disc still stalls: capture and read
  the `RAM 00081C7x` records around 15.74 s.

## What was running (23:15)

- **The Quartus lock**: the Sun-2 session's compile took it at 23:04; build
  28 (chain bnhfpdyr8, pid file quartus28.pid) waits on the flock and starts
  when it ends (~23:45), done ~00:20. run24 (the bench): 0 errors through
  the uncached pattern. **run25** on the Mac (38ea07b: the memory-port
  trace watching both TMTask lines, 81C60 and the bench's 81AC0; 420 M
  instructions; watcher bxqnoixq3): the bench's `RAM 00081ACx` records for
  the same stretch, the reference for the board's `RAM 00081C7x` ones.

## What was running (22:55)

- **Quartus: build 26 = efbf06e** (the store-landing capture) in its
  fitter (chain b4khbc21z, `scratch/BandaiPippin_efbf06e.rbf`): the disc
  capture round (`syn/boardcap.sh RBF cap5`), then `grep "store landed"`
  around the stores at 51/52, 250, 980, 1215. Then **build 27 = eadc78c**
  (chain b1h9rj4fj, `scratch/BandaiPippin_memtest27.rbf`): the memory test
  with the dcbz cases AND the line watch (the watch should now show NO
  dcache events for the line itself: it is uncached). Then **build 28 =
  cb0d605** (chain bnhfpdyr8, `scratch/BandaiPippin_memtest28.rbf`; the
  chain compiles the working tree, so it has 832abbf's memory test with
  the cache-inhibited accesses AND cb0d605's trace): (1) the memory test
  round on the board (`grep DBG`: errors in status 5 = the uncached word
  write path is the fault); (2) a disc capture round: the trace now has a
  kind-4 record `RAM 00081Cxx r|w data (be)` for every uncached word
  access to the TMTask's line as the memory port serves it, a write's with
  the SDRAM controller's diagnostic (`sdram be X issued N col C`,
  `after-refresh`): compare the two halves of the tmAddr store (51) with
  tmCount's (1215) and the byte stores. **run24** on the Mac (832abbf's
  memory test, `--memtest-passes 2`; waiter b5uku2q0r) validates the
  uncached pattern's expected values (0 errors expected; RESULT: FAIL is
  only the instruction limit). Build 27 (dcbz cases, the line watch) is
  moot for an uncached page: not run on the board. **run22** on the Mac (efbf06e, no lockstep, 290 M
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

