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
