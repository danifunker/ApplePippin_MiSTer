# Resume: the Pippin on the board (written 2026-10-19)

Resume the Bandai Pippin MiSTer core's board bring-up. The core boots to the
Pippin logo on the board with correct NTSC video; a disc (Super Marathon) does
not boot yet because the board stops taking interrupts about 16 s in. Read this
whole file first, then `docs/pippin_plan.md` (its progress log) and
`docs/fix_macppc7300.md`. Ask before anything outward-facing (pushing,
downloads, other people's boards).

## Rules the user set (follow them)

- **One simulation at a time**, ever (machine_tb, machref, run_core, run.py).
  The box is shared (6 cores, 14 GB) with other Claude sessions.
- **Quartus on this Linux box, Verilator on the Mac** (2026-10-21): the M1 Mac
  mini `dani-dev.local` (`ssh dani-dev.local`, tools under `zsh -lc` for
  Homebrew's Verilator 5.052) runs the benches; checkouts kept in step through
  git (push here, `git pull` there; the Mac clones over HTTPS). Not in git and
  copied to the same paths there: `scratch/pippin/` (ROMs, discs),
  `~/repos/Main_MiSTer-pippin` (no .git), `~/.cache/applepippin/dingusppc`.
  Bench runs there: `~/pippin_bench/` (`run.sh`, nohup). **Use only the Mac
  for Verilator** (no bench runs on this box): it compiles the machine bench in
  minutes (8 min to 50 M instructions including the build, against ~30 min
  here) and runs ~1.75x faster (17.5 M vs 10 M CPU cycles a minute), with the
  same results cycle for cycle (50 M instructions at 149,071,952 cycles on
  both). Build there with `VJOBS=6`.
- **Every Quartus flow under `flock /tmp/quartus.lock ...`** (the sessions'
  agreed lock; the SPARCstation, HP9K715 and HP9K385 sessions use it too, and
  message before long runs). Verilator builds at `VJOBS=2` or `3`.
- **Commit before every build**, so each `.rbf` has a rollback point.
- **Boards**: copy files over SSH (`syn/mister.py install`, `put-core`), but
  **load cores and drive the screen only with misterkvms-cli through the
  OSD**, never mrext's `/api/launch`:
  `~/Downloads/MiSTerKVMS-0.9.5-linux-x86_64/misterkvms-cli --mister 192.168.99.92`
  (`screenshot F.png`, `key F12|up|down|left|right|enter|backspace`,
  `type x`). The board is **192.168.99.92** (MiSTerss1), SSH as root with
  `~/.ssh/id_rsa` (`MISTER_KEY=~/.ssh/id_rsa`; `syn/mister_host` holds the IP,
  git-ignored). A second MiSTer (capture stream "MiSTer-Pi", 192.168.99.143)
  has not been touched: set it up only if asked.
- Do not modify the MacPPC7300 repository; add candidate fixes to
  `docs/fix_macppc7300.md` (15 items so far).
- The core's name is **BandaiPippin** (Quartus project, `_Console/BandaiPippin_<date>.rbf`);
  its OSD name is **Pippin** (folders `games/Pippin`, `config/Pippin.*`).

## Where things are

- Repo `~/repos/ApplePippin_MiSTer`, branch `pippin` (not pushed). Last
  commits: 048981b (TRACE_INT), 90f83bd (Grand Central VIA event), 77623d4
  (trace kind 7), 1b15550 (video STD_DOT), cc811b9 (OSD standard), 0ff2f8e
  (install: one shared Main).
- Main_MiSTer worktree `~/repos/Main_MiSTer-pippin` (never switch the shared
  checkout `~/repos/Main_MiSTer`): `pippin-cdrom` = upstream master bb73090
  (which has the HP 9000 family) + 2 commits (3520eb8 the core name `pippin`
  in the Mac SCSI family; a2903b3 a CHD mounts like its CUE). `consolidated` =
  the same for now; the user wants it to gather "all the cores'" unmerged Main
  work. Branches that conflict with master both ways (partly merged or
  superseded, owners to decide): the sun/SPARCstation branches,
  hp9k715-enhancements, the mac-ethernet line, next-color,
  add-bluescsi-toolbox-for-MacLC. Nothing pushed: ask before pushing.
- On .92: `/media/fat/MiSTer` is the consolidated Main (the old one kept as
  `MiSTer.prev-20261019-0419`, MiSTer.ini as `MiSTer.ini.prev-20261019-0419`;
  the earlier `MiSTer_pippin` and `[Pippin] main=` are removed).
  `games/Pippin`: boot.rom (Kinka 1.3), Kinka 1.3/1.2/1.0/GM Flash .rom,
  Super Marathon (CUE/BIN), Racing Days, Macintosh on Pippin, Power Rangers
  Zeo (CHD). `_Console/BandaiPippin_20261019.rbf` is the 90f83bd build.
- Disc images: `scratch/pippin/discs/` (Super Marathon unpacked; CHDs in
  `chd/`); the zips stay in `scratch/pippin/`. Staging for install:
  `scratch/pippin/install/` (symlinks).

## The working tree's build settings (debug, not release)

`BandaiPippin.sv`: `CPU_MHZ = 58` (58.333 MHz, the PLL's 700 MHz / 12; 70 MHz
misses timing by 1.8-2.7 ns), `TRACE = 1`, `PERF = 1`; `BandaiPippin.qsf`
SEED 7. `Pippin_machine` parameter `TRACE_INT = 1` (default: set it to 0 for
release). `Pippin_athens.sv` prints I2C traffic under Verilator only. A
release build later: TRACE 0, PERF 0, TRACE_INT 0, and the CPU clock decided
by timing (58.33 MHz builds close to within 0.5-0.6 ns).

## Done and verified

- Kinka 1.3 boots to the Pippin logo on the board; the RTL's logo frame equals
  dingusppc's pixel for pixel (the bench). The RTL is ~100 M instructions
  behind dingusppc in the boot because the boot chime plays in real time.
- **Video**: Athens is left at 14.375 MHz by the ROM, which made 18.43 kHz /
  70 Hz. Interim fix `STD_DOT` in `Pippin_taosvideo`: the dot clock is the
  standard's line rate x Taos's line (HPIX + 2): NTSC 15,734.27 Hz, PAL
  15,625 Hz, VGA 31,468.75 Hz. Board info page: 640x480i 15.74 kHz 59.8 Hz.
- **OSD**: the standard of `~/repos/hp9000-715/docs/osd-standard.md`
  (Pri. CD-ROM (ID 3), Load ROM, Memory, P2 Video, P3 Input, P4 Audio, P5
  Advanced, "Changes pending", Apply and reset; no "(on reset)").
- **CHD**: the Main's Mac CD layer reads CHD; `verilator/maincd` builds the
  Main's own CD code on the host; `cdcheck A B` compares two images as the
  core sees them. All three CHDs equal their CUE/BIN (after a2903b3).
  The bench's slot 4 is served by that same code (`verilator/cdhost.h`).
- DSPPC603: the 604's string-crossing-4 KB alignment rule removed (the 603e
  has none; f07b7e2). `dcbz` alignment exceptions are handed to the lockstep
  reference.

## Open problem 1 (the main one): the board stops ~16 s in

Super Marathon mounted (also with no controller, at 58 and 70 MHz): the ROM
reads the disc's boot blocks (READ(10) of sectors 0 and 16, twice), READ TOC,
TEST UNIT READY, PREVENT, then the ADB address resolution (19 x "listen r3"
to address 2), a reset/flush, ADB polling for ~1 s, and then **nothing**: no
SCSI, no ADB. The bench (same RTL, same disc) goes on: READ(6) 1.5 s after the
ADB reset, then the boot: at 700 M instructions it shows the disc's own
**Bandai Digital Entertainment splash** (no lockstep, `--cd` through the
Main's CD code, 2,195 blocks read by 900 M). So the core boots a disc in
simulation; the board does not.

The CPU keeps running 68K-emulator code (68060CC0, 68060D2C, MSR D072, EE on)
but takes no external interrupt again. The trace's interrupt-state record
(kind 7, every 2^22 cycles) on the board, before and after:

```
before:  mask 9017a000 events 00000000 lines 00000000 IFR 40 IER 24 irq 0 via 0
         (a VIA interrupt comes and goes: lines 00040000 IFR 44/60 via 1)
stuck:   mask 901fa000 events 00000000 lines 00040000 IFR 64 IER 24 irq 0 via 1
```

So the VIA's line is high with T2 (bit 5) and the shift register (bit 2) set
and enabled, Grand Central's event for it was cleared, and nothing raises it
again: Mac OS took the event and never acknowledged the VIA (the pending SR
flag also explains Cuda/ADB going silent). 90f83bd (an event for every VIA
flag newly set while enabled, in 68k mode, as dingusppc's ack_int does) is
correct but does not cure it: no flag is new.

Things ruled out on the board: CPU timing (58 and 70 MHz the same), the
AppleJack (no controller: same), SOUND_IN_DMA (the bench with 0 goes on).
Remaining differences board vs bench: Cuda FAST_BOOT=1 in the bench (0 on the
board), the bench's functional memory model vs the real SDRAM controller, the
CPU clock ratio (bench 66 MHz), the Main's real timing on slot 4, real input
devices/RTC from the Main.

**2026-10-21: the TRACE_INT capture, and a fix that did not cure it.**

- The 048981b capture (`scratch/tr_int1.bin`, `.txt`): a steady pattern of T2
  (Time Manager) interrupts and ADB polls, each interrupt's handler writing
  Grand Central's clear register with "clear all" (`clear w 00000080`, i.e.
  0x80000000 byte-swapped), until **15.732 s: the mask write `00a01f90`
  (9017a000 -> 901fa000, adding bit 19 = SWIM3's interrupt)**. T2 is then
  loaded once more (~1.2 ms), a clear at about the moment it fires, and from
  there T2's flag stays set with the line high and no event (IFR 60); at
  ~15.79 an interrupt arrives (the SR flag), its handler writes "clear all",
  and nothing services the VIA: IFR 64 for good.
- bbc509d (built 05:59, worst setup slack +0.057 ns at 58.33 MHz, **on .92
  as `_Console/BandaiPippin_20261021.rbf`**): Grand Central now does what
  dingusppc does, in 68k mode every report of the VIA's line while high is an
  event (any flag set, enabled or not; reads of T1CL/T2CL/SR; writes of
  T1CH/T1LH/T2CH/SR/IFR/IER), in place of 90f83bd's rule. It is right by the
  reference but **does not cure the board**: capture `scratch/tr_fix1.bin`,
  the same stall at the same place (mask write 15.732, the clear at 15.747,
  the SR interrupt at 15.837 delivered and cleared, the VIA never serviced).
  The interrupt-state record is now **kind 16** (decoder reads 16 and old 7);
  the decoder prints VIA writes by register name.
- So the event is delivered and the 68k side does not dispatch it: **68k
  interrupts look masked while Mac OS polls**. During the stall the CPU runs a
  short 68k loop in the emulator (PC samples 68060CC0/CC4/D2C, the opcode
  fetch `lhau r27,2(r24)` and dispatch; ~15 handler spots, one a load
  `lwz r4,0(r17)` at 68092088) and still takes decrementer exceptions (0x900).
  The **leading suspect is the floppy driver's init after SWIM3's interrupt is
  enabled** (`Pippin_swim3.sv`: Grand Central source 0x13; dingusppc's
  swim3.cpp/superdrive.cpp), waiting for something with interrupts masked.
  Not checked yet: what that 68k loop reads (the trace does not record reads;
  r24 holds the 68k PC), and whether the bench passes the same mask write.

**The bench against the board** (bbc509d, SOUND_IN_DMA=0, CUDA_FAST_BOOT=0,
the 1956 clock): the bench reaches the same mask write `00a01f90` (its trace
time 8.666 s, cycle ~0x22000000) and **goes on with the same steady pattern**
after it (a pair of clears and two T2 loads every ~5 ms, the VIA's line low).
On the board the pattern changes right at that write: three T2 loads, then
single, longer T2 loads (0x0357, 0x027D, 0x0440, 0x03BA), then the stall: a
driver waiting through timeouts on the board only. Ruled out as the
difference: a floppy image (none mounted on the board: only `config/Pippin.s4`,
the CD), a saved NVRAM or flash (none on the board).

**2026-10-21 07:30, the comparison in detail and the next capture.** The
bench's bbc509d trace (the old scratchpad's `rep.bin`, decoded) after its
mask write: the Time Manager loads T2 twice (0x0bfb, 0x0ba4: 3.9 ms) and
the steady pattern returns. The board: three loads (0x0659, 0x05b6, 0x0511:
2.1, 1.9, 1.7 ms), a short task re-armed (0x0440 at 15.736, 0x03ba at
15.746), the clear at 15.747 and nothing after: T2 fires at ~15.7472 (IFR 60
later), the nanokernel's clear-all is written, the 68k VIA handler never
runs. So a driver on the board retries something with ~1.5 ms waits, then
sits in a 68k loop with interrupts masked. The board is also slower in
machine time: the SCSI bus reset at 10.73 s against 5.05 s, the ADB address
resolution 1.34 s against 0.78 s (the SDRAM's latency, or something
time-based): a driver with a timeout would hit it on the board only.
dingusppc's clear-all in 68k mode zeroes the events and re-raises nothing
until the VIA's next report (grandcentral.cpp:438, viacuda.cpp:333), as the
RTL does: no divergence there. **ab959c0** (TRACE_INT): kind 4 now records
every access to SWIM3's registers (F3015000) and its DMA channel 1
(F3008100), reads included, and one in 256 of the reads of the VIA or the
interrupt registers (so the stalled loop shows what it polls); the decoder
names SWIM3's registers; **9405b9d**: `trstream.py` no longer drops reads
of the interrupt registers. A Quartus build of it started 07:29 (this box,
flock); then `put-core` (the bbc509d .rbf kept as
`scratch/BandaiPippin_bbc509d.rbf`), `trace-capture`, the core loaded
through the OSD with Super Marathon, and the decode: the SWIM3 accesses
around 15.73 s and the sampled reads during the stall. The user said yes to
the build and capture only (no push, no bench run yet).

**The ab959c0 capture (`scratch/tr_swim1.bin`, `.txt`; built 07:54, slack
-0.169 ns, on .92 as `_Console/BandaiPippin_20261021.rbf`): the same
stall (mask write 15.727).** The floppy driver's init, in Linux swim3.c's
names (register 4 is `select`: CA0-2 and LSTRB; 7 written sets control
bits, read gives the drive's status line in bits 2-3; the status address
is SELECT (control 0x20) as bit 3 over the CA lines): the chip probe
(select 5/6/7 read back), mode 95, setup 4c; drive 1 (control 02):
ONEMEG_MEDIA 0, DRIVE_PRESENT 0 (a drive), SINGLE_SIDED 1, ONEMEG_DRIVE 1;
drive 2 (04): all 1 (no drive); a MOTOR_OFF strobe (select 0e) to drive 2;
deselect. Then a **Time Manager task polling DISK_IN on drive 1**
(`control -04 +02, select 03, control +20, select 20 (CA 0: address 8),
read 0c = no disk, control -18 -06`) at 15.728, 15.728, 15.731, 15.746,
each re-arming T2 — and after the 15.746 poll **no T2 reload**: the task
hangs inside the Time Manager's interrupt, 68k mask raised; T2 fires at
15.747 and the SR byte at 15.832, the nanokernel clears both, dispatches
neither. **During the stall not one sampled read of the VIA, the
interrupt registers or SWIM3** (before it, the usual IFR/mask/levels mix),
so the loop polls RAM or an untraced device: a wait on Ticks or on a flag an
interrupt would set (a deadlock inside the task) fits. The PC samples are
the emulator's dispatch (`lhau r27,2(r24)` at 68060CC0 and 68067EF8, the
decrementer taken at 68067F60): the 68k PC is in r24. **fa7e049**:
DSPPC603's PERF sample carries the last load's effective address (bytes
20-23; the counts kept: alignment, DSI, external, decrementer in 24-27);
at the dispatch that is the 68k PC + 2, elsewhere the polled address.
`mister.py trace` prints the sample as text (`cpu PC ... ld ea ...`);
`scratch/k14.py` likewise. Not built yet: the next build and capture give
the 68k PC of the loop, to be looked up in the Kinka ROM's .Sony/SWIM3
driver.

**2026-10-21 09:20, the fa7e049 capture (`scratch/tr_swim2.bin`, `.txt`;
built 09:16, slack +0.304): the loop found.** The samples' load addresses
during the stall alternate between ROM fetches FFC3B488-FFC3B496 (68k
ROMBase FFC00000) and RAM 00081C70 / 00081C7A. The ROM there
(`m68k-apple-macos-objdump -b binary -m m68k --adjust-vma=0xffc00000`) is
**the Time Manager's queue walk inside PrimeTime/InsTime** (entered at
FFC3B3EA; FFC3B42E `jsr ([0x2080],0x14)` masks interrupts, restored by
`move.w d3,SR` at FFC3B536 after the T2 reload at FFC3B4D8; the dispatch
from the T2 interrupt is FFC3B4B0): `lea (a2),a1; move.l (a1),d2; beq;
exg d2,a1; move.l 10(a1),d1; sub.l d1,d0; bcc.s` — and the two loads are
one TMTask at 00081C70 whose qLink points to itself with tmCount 0: a
self-linked queue, walked for ever with interrupts off (hence T2 and the
Cuda SR byte cleared by the nanokernel and never dispatched). Two more
facts: (1) samples 99376-99378 show the walk already running before the
15.739/15.740 interrupt, and that interrupt *was* dispatched (T2 reload,
floppy poll) inside the masked section: a nested PrimeTime is how the
self-link arises; (2) **the bench's trace of the same build
(`scratch/rep2.bin`, `.txt`, the Mac, 1956 clock) has the identical driver
init at 8.666 and then its DISK_IN poll task fires once, 500 ms later
(9.167 s)**: it is a 500 ms periodic disk-insertion check. On the board the
task fires at once and every 1-2 ms (the T2 reloads 0x070a, 0x06bb, 0x05c2,
0x04c2: 256 ticks less each time) until the corruption. So PrimeTime(500
ms) gives a near-zero delta on the board: the ms-to-ticks conversion
(FFC3B3D2: `mulu.l` 64-bit by 0xC3D70A3E, a 68020 instruction the
emulator does with mulhwu/mullw) or the queue arithmetic goes wrong on the
board only, i.e. a timing-dependent CPU result, which real SDRAM latency
would expose and the bench's one-cycle memory would not. **Running on the
Mac since 09:27: `~/pippin_bench/run3.sh` = the lockstep bench
(dingusppc's CPU) with `--stall 25` (random bus wait states), the 1956
clock, Super Marathon, to 420 M instructions, trace `rep3.bin`, log
`runrep3.txt`.** If lockstep diverges, the first divergence is the CPU bug;
if the machine stalls without diverging, the problem is elsewhere (the
nanokernel's masking under the interrupt timing); if neither, raise the
stall rate or the clock ratio (`-GCPU_HZ=58333333`).

**10:10: run3 (`scratch/rep3.bin`, `.txt`) ran to 420 M instructions in
lockstep with `--stall 25` with no divergence and no stall: its DISK_IN
polls at 9.206 and 9.706 s, 500 ms apart.** `--stall` only delays line
fills (633 M cycles at 400 M instructions against 630 M without), so it is
a weak stimulus. Running since 10:11 on the Mac: `run4.sh` = lockstep,
`--stall 60 --cpu-mhz 58.333` (the C++ side's clock ratio: 58.33/100 as on
the board) and `-GCPU_HZ=58333333 -GCPU_HZ_FAST=58333333` (the RTL's tick
dividers), trace `rep4.bin`, log `runrep4.txt`. And on this box a Quartus
build of **534693e: TRACE 0, PERF 0** (the fa7e049 .rbf kept as
`scratch/BandaiPippin_fa7e049.rbf`), to put on .92 and watch whether the
disc boots without the trace and the CPU's sampling: if it does, the
trace/PERF machinery is implicated; if not, that variable is out. Then the
remaining board-only variables are the SDRAM controller (`Pippin_sdram.sv`,
Sorgelig's sdram.sv with a new request side, replaced in the bench by the
C++ stand-in; the same RTL runs MacPPC7300 on the board) and the memory
clock-domain crossing at the board's ratio. CPU-side reading so far: the
multiplier holds its product while waiting (no hazard); a trap takes a
second EX cycle with its compare registered (`slow_held`, `trap_hit_q`);
`ex_first` is the sequencer's first operation, not EX's first cycle, so an
external interrupt during a trap's second cycle annuls it with vector 500
(SRR0 at the trap). Nothing found there yet.

**10:40.** The TRACE 0 / PERF 0 build (534693e, slack -0.039) **still shows
the logo at 100 s**: the trace machinery is out (36e7cc8 restores TRACE 1,
PERF 1; the fa7e049 core is back on .92). run4 (`--stall 60`) was stopped
at 250 M instructions: `--stall` adds a geometric wait only to line fills
(443 M cycles at 250 M instructions against 439 M without), no stimulus.
The real controller (`Pippin_sdram.sv`) takes ~24 memory clocks per 32-byte
line (ACTIVE, two 8-beat bursts at CAS 2, PRECHARGE; single-location
writes), against the stand-in's 1: that is the board's 1.4-1.7x slowness.
**e08a6a5: `--mem-wait N`** sets the stand-in's latency. **Running on the
Mac since 10:40: `run5.sh` = lockstep, `--mem-wait 20 --cpu-mhz 58.333`,
`-GCPU_HZ=58333333 -GCPU_HZ_FAST=58333333`, trace `rep5.bin`, log
`runrep5.txt`.** And building here: **5ab1405**, the RTL's memory-test
boot program on the board (Advanced > Boot: Memory test, status[34],
counted in "Changes pending"; Apply and reset starts it), its DBG writes
(status 1 writing / 2 reading, passes, errors, first error address, read,
expected) in the trace with TRACE_INT: a test of the real SDRAM controller
and clock crossing with the CPU's own accesses. Each pass writes the RAM
(ram_mb) with pass-seeded words, dcbf per line, then reads it back.

**11:10, the memory test on the board (5ab1405, slack +0.081; capture
`scratch/tr_memtest1.bin`, `.txt`, 90 M records lost to the error flood):
363 passes in 177 s, and every pass exactly 262,144 bad words = 1 MB,
the first at address 0 reading 00400E00 for 00000000.** That is the test's
linear sweep of "5 MB" meeting the Pippin's map (Aspen: 4 MB at 0, the
fifth MB at 16 MB; 4-5 MB is a 4 KB-wrapping window that aliases onto the
first bank), not the controller: the other 4 MB are perfect on every pass.
**The SDRAM controller and the clock crossing are sound at the board's
clock** (for this sequential pattern). To run the test cleanly, DBG+0x20
should report the contiguous bank (min(ram_mb, 4) MB); not done.
The 5ab1405 core stays on .92 (Boot set back to ROM). The remaining
board-only differences: the memory latency and clock ratio (run5), the
Main's CD latency (the bench's `--disk-latency`, default 2000 memory
clocks; the SD card answers in milliseconds), the real time (`--clock`),
the DDR3 VRAM path.

**12:10.** run5 (lockstep, `--mem-wait 20 --cpu-mhz 58.333`, `scratch/rep5.bin`,
`.txt`): identical to 420 M instructions, PASS; init at 10.293 s, the
DISK_IN polls every ~503 ms after it. run6 (`--disk-latency 200000`)
running since 11:31; run7 (`--clock` today) ready. **e129517, kind 17** (the
interrupt-state record at every change of the events or the CPU's
interrupt; the ESCC's accesses too), built (slack -0.376), captured
`scratch/tr_ev1.bin`, `.txt`: the same stall, and the picture is now
complete: a T2 interrupt is a rising-edge event (IFR 60), the nanokernel's
clear-all, the 68k handler's T2CL read (IFR 40), the falling-edge event
(68k mode), a clear-all, then the Time Manager's reload. **At 15.740 and
15.771 that whole sequence, floppy poll and PrimeTime included, runs while
the samples before, between and after show the queue walk** (30 samples
of it between 15.743 and 15.770): 68k interrupts are dispatched inside
PrimeTime's `ori #$700,SR` section (the table at 0x2080, set at ROM
offset 5A44, lists FFC062A0, FFC3B366, FFC3B3D2, FFC3B432, FFC3B4B4,
FFC3B630; entry +14 = FFC3B630 is the plain 68k mask-and-read-T2 routine).
And right after the init (15.737) the driver's poll runs twice with **no
interrupt event at all** between the T2 reloads: the task body runs
synchronously there. Checked and clear: the emulator's code in RAM (the
0x68xxxxxx PCs are RAM, the nanokernel's copy, not the ROM) has the same
instruction word at every PC sampled on both machines (2002 common PCs).
**a5472ac: every VIA read in the trace** (T2CH/T2CL/IFR as the Time
Manager reads them at FFC3B630/FFC3B4D8), building (12:10); the plan: the
same commit on the Mac (pushed; `run8` = run5's options plus the trace)
and on the board, then diff the Time Manager's inputs (T2 readbacks) and
outputs (reloads) around the init between the two machines.

**12:25.** run6 (run5 plus `--disk-latency 200000`, `scratch/rep6.bin`,
`.txt`): identical, PASS, polls every 503 ms: the CD's latency is out.
The ROM-resident PPC code sampled on the board (FFCxxxxx, 1061 + 1067
samples) matches the ROM file word for word, the emulator's RAM copy
matches the bench's: the upload is clean as far as sampled. The driver's
scheme (ROM FFCF668E, FFCF7B8C-FFCF7BF0): PrimeTime(500 ms) on the task at
SonyVars+1EC with tmAddr FFCF7BA2, then FFCF7BC2 pops its caller's return
address into a slot at task-20 and returns to the init; when the task
fires, FFCF7BA2 (in the Time Manager's dispatch) RmvTimes, clears tmAddr,
restores d1-d3/a3 and jumps to that continuation (FFCF66A0: `ori
#$700,SR`, the drives polled, SR restored, `bra FFCF668E`: prime again,
return to the dispatch). So every poll + PrimeTime runs inside the T2
interrupt, as the bench shows. On the board the continuation ran twice
right after the init with no interrupt event between (tr_ev1 114083-114111)
and the Time Manager's reloads in between: something entered the
dispatch (FFC3B4B0, table entry +10) without a T2 event. `syn/tmview.py
TRACE.txt [after] [before]` prints the Time Manager's view (VIA accesses,
clears, events, polls, samples) from the mask write. run8 (run5's options,
a5472ac: every VIA read) started 12:24 on the Mac; the a5472ac build here
is due ~12:32: then the board's capture, and the diff.

**12:50, the VIA-read capture (a5472ac, slack +0.012; `scratch/tr_via1.bin`,
`.txt`; 11,132 records lost by the ARM's streamer, all before the init: the
init stretch is complete) read with `syn/tmview.py`.** The Time Manager's
routines are recognisable by their VIA accesses: FFC3B630 (mask, read the
timer) = T2CH r, IFR r, T2CL r, T2CH r; FFC3B4D8 (reload) = T2CL r, then
T2CH w, T2CL w, T2CH w; the 68k VIA handler = IFR r, IER r. At the init
(15.713): PrimeTime (reads 09/40/6C/09, T2CL 30, reload 0925), a second
PrimeTime-like operation (08/40/BC/08, 8D, reload 0882), then **the
floppy's DISK_IN poll with no interrupt event**, a PrimeTime (reload
07DC), a poll, a PrimeTime's reads (07/40/7F/07) **and no reload: the
walk**. Every T2 interrupt after that (15.716, .719, .722, .726) enters
the dispatch **without** FFC3B630's reads (T2CL r alone, then the reload:
the table's +10 entry, FFC3B4B4), runs the poll (the continuation) and a
PrimeTime whose walk never ends, nested in the first. So PrimeTime(500 ms)
put the task at the head, due at once, and the dispatch inside the masked
walk is the +10 path. The multiplier is not a critical path (the CPU
clock's worst is 0.138 ns in fq_a_mem_r/cr[5]; the worst overall 0.012 in
Pippin_sdram at 100 MHz). **585c29e: the trace ring is 16384 records**
(building 12:45). **Stale RAM**: the board's SDRAM keeps the previous
run's contents across core reloads (a warm start for the ROM, heap blocks
reused uncleared), the bench starts from zeros. Booting the memory test
(RAM overwritten with its patterns) and then the ROM (`scratch/tr_cold1.bin`,
`.txt`) **still stalls** the same way: stale Mac OS contents are not it,
but nonzero garbage still differs from the bench's zeros. **7cc5675:
`--ram-fill SEED`** fills the bench's RAM (and the reference's: `mem` is
copied into `ref_ram()`) with xorshift32 bytes. **run9 = run5's options
plus `--ram-fill 0x9E3779B9`, lockstep, running on the Mac since 12:47**
(run8 stopped for it; `rep9.bin`, `runrep9.txt`). If run9 stalls, the
cause is a RAM-contents dependence, visible in full in the bench.

**13:10, the complete capture (585c29e, ring 16384, slack +0.153;
`scratch/tr_via2.bin`, `.txt`, 28 records lost, none near the init).** The
normal T2 cycle: handler IFR r E0, IER r A4; the dispatch's timer read T2CH
FF, IFR E0, T2CL (the flag clears: the falling-edge event and clear), T2CH;
the reload T2CL r, T2CH/T2CL/T2CH w; the periodic task's PrimeTime (timer
read, reload). At the init (15.728): PrimeTime #1 (06/40/6F/06, 34, reload
0629) and #2 (05/40/C0/05, 91, reload 0586) complete normally, then the
continuation (poll, PrimeTime 04E1, poll, PrimeTime without reload: the
walk) **runs with no interrupt**. The driver's only synchronous route into
the continuation is FFCF7BC2: `tst.l -20(a0)` nonzero → `_Debugger`
(nothing installed), mask, clear the slot and tmAddr, RmvTime, rts → into
the poll loop. The slot (SonyVars+1D8) is never written before that check
in the code read so far: zero on the bench (RAM starts zeroed), garbage on
the board (stale or the memory test's pattern). run9 tests the bench with
garbage RAM; a memory test that leaves RAM zeroed (then Boot: ROM) tests
the board.
An idea not tried: the same bench run with the board's date (`--clock` with
today in Mac seconds; the bench's default is the firmware's 1956), since the
Main gives the board the real time; it is a guess, as are the other
differences (the CPU clock ratio, bench 66 MHz; the SDRAM controller; the
Main's real slot-4 timing; input devices). On the Mac, `~/pippin_bench/`
holds `run.sh` (now with `--clock $CLOCK`; unset, it passes nothing useful:
edit it first) and the stopped runs' partial traces.

**Earlier step**: a bench run of bbc509d (the last one on this box; from now on
the Mac's `~/pippin_bench/run.sh`, the same options) was started 05:31:
build `~/.cache/applepippin/verilator-rep`,
`MACH_GFLAGS="-GSOUND_IN_DMA=0 -GCUDA_FAST_BOOT=0"` (Verilator keeps the last
-G, so FAST_BOOT is 0), Super Marathon, `--max-instr 900000000`, trace to the
session scratchpad `rep.bin` (log `runrep.txt`, frame `rep_700M.png`). When its
interrupt-state records pass cycle 0x26200000 (the board's stall), decode it
(`python3 syn/mister.py trace --file rep.bin`) and compare what follows the
mask write `00a01f90` with the board's: the SWIM3 activity, the T2 servicing,
the clears. If the bench is gone (a new session's scratchpad differs), rerun
it with the same options. Then, if needed, dingusppc's device log of the same
phase (`machref ... --log`, one simulation at a time). `scratch/k14.py FILE LO
HI` prints the kind 14 PC samples (bytes 8-11 PC, 12-15 last exception PC,
16-17 its vector, 18-19 MSR, 28-31 the instruction; align by record index).

## Open problem 2: Athens never gets Mac OS's video clock

On the board and in the bench the ROM sends Cuda `01 22 52 03 01`, `01 22 52
01 10`, `01 22 52 02 2E` (P2 01, D2 16, N2 46: 14.375 MHz) right at the start,
then one write to I2C 0x28 (no device: no acknowledge, as in dingusppc) and
`07 82`, and no Athens write after that. dingusppc's Pippin gets
`01 0B, 02 1B, 03 22`, then `07 82, 05 05, 06 99`, and Mac OS's driver later
sets `01 0B, 02 1B, 03 02` (24.545 MHz, Taos counting every second clock). The
early branch differs because the ROM finds the save flash (AMD ID at
40000000) in our machine and not in dingusppc's (no flash there): our path is
the real machine's. Why Mac OS's driver never reprograms Athens in our machine
is open. STD_DOT keeps the picture right meanwhile (STD_DOT = 0 for Athens's
clock once this is understood). A logging change was made in the cached
dingusppc clone (`~/.cache/applepippin/dingusppc/devices/common/clockgen/athens.cpp`,
"ATHENSLOG") to get those values; revert it with `git -C ... checkout` when
done.

## Other open items

- Kickstart (`~/repos/Pippin_Kickstart`, cloned from the user's GitHub; builds
  with Retro68 into the 1024-byte boot block): needs the signed
  `pippin-kickstart-1.1.iso` from blitter.net; **the user has not yet said yes
  to downloading it**. The user also wants the copyright/signer message to be
  an input or a switch (low priority; the banner sits in boot block 2 next to
  the 8 bytes kept for the authentication block).
- The 603e's other alignment rule (a plain misaligned load/store crossing a
  page under page translation takes an alignment exception) is noted in
  `docs/DSPPC603_notes.md`, not implemented.
- Grand Central's other sources (MESH, SCCs) have the same "event only at a
  line change" exposure as the VIA had.
- Timing: 70 MHz fails by 1.8-2.7 ns; the first build was 63.1 MHz worst case.
  The worst paths have not been examined.
- The Pippin plan's remaining days: CD audio (Racing Days), compatibility,
  release (`docs/pippin_plan.md`).
