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
ADB reset, then the boot.

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

**Next step**: the 048981b build (TRACE_INT: kind 4 records of every write to
Grand Central's interrupt registers F30000xx and to the VIA F3016000-F3017FFF)
is built: `output_files/BandaiPippin.rbf` of 2026-10-19 09:57 (worst slack -0.020 ns
at 58.33 MHz), not yet on the board (rebuild from 048981b if output_files has
changed since). Put it on .92 (`MISTER_KEY=~/.ssh/id_rsa python3
syn/mister.py put-core`), start `python3 syn/mister.py trace-capture 150`, load
the core through the OSD (F12, up, right = System page, enter = Core, the
browser opens in `_Console` on BandaiPippin, enter), wait 150 s,
`trace-fetch F` and `trace --file F`. Find the last clear (writes to
F3000028) and the VIA writes (IFR at +1A00, IER +1C00, SR +1400) before the
stop, and compare with the bench: run the same disc with the same build
options (`MACH_GFLAGS=-GSOUND_IN_DMA=0 PIPPIN_BUILD=~/.cache/applepippin/<dir>
python3 verilator/run_machine.py --no-lockstep --module 32 --cd CUE
--trace-out F ...`) and decode its F the same way. Consider also a bench run
with CUDA_FAST_BOOT=0 (`MACH_GFLAGS=-GCUDA_FAST_BOOT=0`; the Makefile also
passes -GCUDA_FAST_BOOT=1, so change the Makefile or the order) to see if the
stall reproduces in simulation.

Trace decoding caveat: **kind 7 is already the SCSI target's "command start"**
in `syn/mister.py trace` (its branch comes first), so the interrupt-state
records print as "ID0 start". Read them from the capture file directly (36
bytes a record: 4-byte index, 32-byte record; record byte 0 = 7, bytes 1-3 = 0,
4-7 cycle, 8-11 mask, 12-15 events, 16-19 lines, 20 IFR, 21 IER, 22 bit 0 irq
bit 1 via_irq, 24-31 zero), or better: move it to a free kind (e.g. 16) in
`Pippin_system.sv` and the decoder. Kind 14 records are the CPU's PC samples
(bytes 8-11 PC, 12-15 last exception PC, 16-17 its vector, 18-19 MSR, 28-31
the instruction; their time stamps use another clock: align by record index).

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
