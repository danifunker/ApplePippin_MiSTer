# cputest — PowerPC 603 CPU test suite for a Performa 62xx

Built 2026-10-16. Purpose: record what a real PowerPC 603 does, instruction
by instruction and exception by exception, on the one 603 machine we will
have (a Performa 62xx: the 75 MHz 6200/5200 carry a 603; the 100 and
120 MHz 62xx/63xx models carry a 603e), so that the Pippin core's CPU
(`DSPPC603`, to be derived from MacPPC7300's `DSPPC604`) can be checked
against the real chip rather than against emulators.

Everything reuses MacPPC7300's `ppctest/` (the vector sets, the record and
CSV formats, the Python assembler, the supervisor sequences and the
decoders). Nothing there is changed; this tree imports it from
`../../MacPPC7300_MiSTer/ppctest` (override with `--ppctest DIR`). What is
new is the **route onto the machine**: a 62xx has no Open Firmware and no
Linux, so ppctest's two routes (boot from OF, or a Linux executable) do not
exist there. The suite therefore has two tiers:

| Tier | What it records | How it runs on the 62xx | Status |
|---|---|---|---|
| **User mode** (`ppc603test.py`, `macapp/`) | ppctest's 79,624 single-instruction vectors: integer, FP, FPSCR, XER, loads/stores (`vectors.build_v4`) | a Mac OS application, built with Retro68, reading `ppc603.vec` and writing `ppc603.res` on the same HFS volume (a BlueSCSI image) | **ran on the Performa 6300CD (603e) 2026-10-18, twice, byte-identically**: all 79,624 vectors each time, checksums verified, 39 s; `runs/results_603e_6300_run1.csv` and `_run2.csv` |
| **Supervisor mode** (`super/super603.py`) | ppctest's supervisor sequences (SPRs, MSR, `rfi`, every exception kind, `lmw`/string edge cases, opcode and SPR sweeps) plus a new `tlb603` group: the 603's software TLB reload, with the program's own handlers at 0x1000/0x1100/0x1200 | a firmware-free blob, loaded anywhere and entered in supervisor mode. Runs today under MAME's Pippin (a 603). On the 62xx it needs a way into supervisor mode: see "Supervisor mode on the 62xx" | runs under MAME; the 62xx route is designed, not built |

Both tiers write files in ppctest's CSV formats, so `ppctest.py diff`,
`verilator/fpmodel.py check` and the Verilator bench's `run.py --csv` take
them unchanged, and a 603 run compares directly with the 604 runs in
`ppctest/runs/`.

## 1. User-mode tier: the Mac OS route

### Build

```bash
python3 ppc603test.py vectors                 # -> ppc603.vec (10 MB, 79,624 vectors, build id printed)
cd macapp && cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=$RETRO68/powerpc-apple-macos/cmake/retroppc.toolchain.cmake \
  && cmake --build build && cd ..            # -> macapp/build/PPC603Test.bin (MacBinary)
python3 ppc603test.py image                  # -> HD40_512_ppc603.hda: a 32 MB HFS volume with both
python3 ppc603test.py selftest               # the file formats and the decoder, no Mac needed
```

`$RETRO68` is the Retro68 toolchain prefix. On this machine it was built
into `/home/dani/repos/Retro68-build/toolchain` (PowerPC only, Multiversal
interfaces; its host tools link against Boost built in
`/home/dani/.local/boost`, so `LD_LIBRARY_PATH=/home/dani/.local/boost/lib`
is needed for `Rez`/`MakePEF` until Boost is installed system-wide).

### What the application does (`macapp/main.c`)

Exactly what ppctest's `harness.py` does from Open Firmware, in user mode:
for every vector it writes the instruction into a two-word slot
(instruction, `blr`), flushes that line (`dcbst`/`icbi`, both legal in user
mode), loads r3–r6, CR, XER, CTR, FPSCR, f3–f6 and the memory buffer, calls
the slot with `blrl`, and stores the same state in ppctest's 64-byte output
record (`layout.py` `O_*`). It keeps the running checksum ppctest uses,
counts mismatches against the expected records carried in the vector file,
prints one dot per 64 vectors, rewrites the results header after every
chunk (so an aborted run still says how far it got), and records Gestalt's
CPU type, machine and system version. It restores FPSCR and CR after each
vector, so Mac OS is left as it was found.

Why user mode is enough for this tier: the vectors touch only user state,
and ppctest's Open Firmware runs also had FE0/FE1 off (MSR 0x3030), which is
what Mac OS gives an application. The two things the OS could still get in
the way of are an instruction that traps (there should be none: every
vector is legal on a 603, `fsel`/`fres`/`frsqrte`/`stfiwx` included) and
floating-point traps being enabled by the system (they are not expected to
be; a run with `--no-fp-enables`-style filtering can be added if they are).

### Run it on the Mac

1. Get `PPC603Test` and `ppc603.vec` into one folder on the Mac. The
   intended way is the BlueSCSI: see "Getting the image onto the Mac".
2. Double-click `PPC603Test`. It prints the Gestalt values, the vector
   count and build id, dots, then
   `n=000137... sum=XXXXXXXX miss=XXXXXXXX ticks=NNN write=ok`.
   A 75 MHz 603 should take well under a minute. Write the line down if
   anything looks wrong.
3. Bring `ppc603.res` back (the BlueSCSI's SD card, or any other way).

```bash
python3 ppc603test.py decode ppc603.res --machine 6200    # -> runs/results_603_6200_run1.csv
python3 ppc603test.py diff ../../MacPPC7300_MiSTer/ppctest/runs/results_604_7300_of_run1.csv runs/results_603_6200_run1.csv
python3 ../../MacPPC7300_MiSTer/verilator/fpmodel.py check runs/results_603_6200_run1.csv
```

`decode` checks the build id against the vector file, the checksum against
the Mac's, prints per-source match/differ/no-expectation counts (the
expectations are the 604's values and the software model's, so on a 603
the "differ" column is exactly the 603-vs-604 list: `fres`/`frsqrte`
tables, denormal handling, undefined divide results, FPSCR details), and
compares with the 604 golden run.

### Getting the image onto the Mac

Classic Mac OS only mounts a SCSI disk at boot when its Apple partition
map carries a driver partition. `ppc603test.py image` therefore starts
from the first 96 blocks of the Quadra 800 bench disks
(`envelope/driver43_96blk.bin`, git-ignored; taken from
`~/quadra800-bench/DONE quadra800-cpu.hda`: driver descriptor, partition
map, Apple_Driver43), stretches the HFS partition entry to the image
size, formats that partition with `hformat IMG 1` and fills it with
`hcopy`. The same envelope is what the 040 and 020 benches booted and
wrote their results through, so the Mac treats it as an ordinary disk.
hfsutils refuses partitions under 32 MB in this envelope; the default is
64 MB. Results come back the same way:
`hmount HD4.hda 1; hcopy -r :ppc603.res .; humount`.

The application writes `ppc603.res` beside itself; if that volume is
locked (a CD) it writes to the desktop of the startup disk instead and
says so. Anything that gets the two files onto the Mac works (a floppy
plus a CD image for the 10 MB vector file, an existing disk); the
writable BlueSCSI disk is simply the round trip with the fewest steps.

Prior reports for this machine family: the DB-25 BlueSCSI has worked on
Performa 630-class machines, and 6200/6360 owners have reported both
successes and hangs; USB-powering the BlueSCSI and keeping the internal IDE
drive's ID clear of it are the usual advice. The 62xx has an external DB-25
SCSI port.

## 2. Supervisor-mode tier: `super/super603.py`

ppctest's second stage (`stage2.py`) with the Open Firmware parts removed.
The output is a position-independent blob with the sequence records
appended; it is loaded at a 64 KB-aligned address (`--base`, default
`0x100000`) and entered at its first word in supervisor mode, with
translation off or an identity mapping. It then

1. saves the MSR it was entered with, turns translation off, clears the
   BATs, maps the low 256 MB with BAT3 cache-inhibited (the same mapping
   ppctest's programs run under), and saves the supervisor state it will
   put back after every sequence (segment registers, BATs, SPRGs, DEC,
   SDR1, and the performance monitor on a 604/750);
2. takes the exception vectors (a three-word stub at every vector 0x200–
   0x1700 into a handler that records vector, SRR0, SRR1, DAR, DSISR and
   the handler's MSR, steps over synchronous faults, and abandons a
   sequence after five exceptions or an instruction-fetch fault);
3. runs every sequence under the MSR its record names (supervisor by
   `mtmsr`, user by `rfi`), with r3–r8, CR, XER, CTR from the record, LR and
   CTR pointing at the appended `sc` that ends it, and writes the 256-byte
   output record (`layout.py` `SO_*`) over the input record in place;
4. writes a header (`S603`, counts, checksum, PVR, HID0, entry MSR) and
   branches to itself. Whoever loaded it dumps memory back out.

Nothing is printed and no disk is touched, so the same blob runs on every
target: MAME, a Verilator bench, QEMU's 603 model, and the real machine.

### The `tlb603` group

For these sequences (`SF_TLB` flag) the runner additionally invalidates the
TLBs (`tlbie` over the 32 sets, and the test pages by name because MAME's
model only invalidates the page named), zeroes a 64 KB page table at
`base + 0x10000`, writes the PTEs the record asks for (its scratch words:
count, then offset-in-table, hi, lo), fills two test pages at `base +
0x20000`/`0x21000` (page A with a counting pattern, page B starting with a
`blr`), sets SR1 to VSID `0x123` and SDR1 to the table, and claims a
512-byte **TLB log**. The handlers at 0x1000/0x1100/0x1200 run in the
603's TGPR mode (r0–r3 are the shadow set), and for each miss log the
vector, SRR0, SRR1, IMISS/DMISS, ICMP/DCMP, HASH1, HASH2, the shadow r0–r3
as found, then search the primary and secondary PTEG as the 603 manual's
example handlers do, set R (and C on a store miss) in the PTE, log the PTE
address and the word loaded into RPA, and `tlbli`/`tlbld` and `rfi`. A
miss with no PTE abandons the sequence (`ABANDONED(no PTE)` in the CSV).
After the sequence the page table is flushed and the PTEs and the first 16
words of page A are copied into the log.

The 37 sequences cover: load, store, load-then-store (a store to a page the
TLB holds with C = 0 should miss again on a real 603), a PTE with C already
set, a read-only page, the secondary hash, a PTE in way 7 of its PTEG, no
PTE, a wrong VSID, two pages, two and three pages in one TLB set (to see
`SRR1[WAY]` and the replacement order), `tlbie` of the page and of another
set, instruction fetches through the TLB in supervisor and user mode, a
fetch with no PTE, misaligned and page-crossing loads, `lmw` across pages,
`dcbz` and loads on a cacheable page, a guarded page, user-mode key and PP
checks, a page under a BAT (the BAT wins), the miss SPRs read and written
directly, `tlbld`/`tlbli` in user mode, HID0/HID1/IABR, and DEC against
the time base.

SRR1 for a TLB miss, from the 603e User's Manual (tables 4-x and 5-10;
page citations to be added to the spec file when the DSPPC603 work
starts): bits 0–3 CR0, bit 12 KEY (Ks or Kp by MSR[PR]), bit 13 I/D (1 =
instruction), bit 14 WAY (the set to replace, per LRU), bit 15 S/L, bits
16–31 MSR. The two tables disagree on the sense of S/L (table 4-x: 1 =
store; table 5-10: "set if the miss was for a load"); the real chip will
say.

### Run under MAME (done here)

```bash
python3 super/super603.py mame                       # the basic groups: 325 sequences
python3 super/super603.py mame --groups tlb          # the tlb603 group alone
python3 super/super603.py list --groups tlb          # the sequences, assembled
```

Needs `pippin.zip` and `cuda.zip` in `--rompath` (default `~/mame/roms`).
Here they were made from `ROMs/2BF65931 - Bandai Pippin (Kinka Dev).ROM`
(MAME's `kinka-pre.rom`, bios `pre`) and MacPPC7300's
`rtl/machine/cuda/341s0060.bin`, with zero-filled stand-ins for the CD
MCU ROM and Cuda NVRAM (MAME warns about the checksums and runs; the
Pippin ROM itself executes only for an instant). MAME is driven by a Lua
autoboot script: the blob is written into RAM, the reset vector in the ROM
region is replaced by a branch to it, the machine is soft-reset, and the
memory is dumped when the header says DONE (a partial dump is taken every
50 frames, so a stuck run still decodes as far as it got). `--trace FILE
--trace-start LABEL --trace-stop LABEL,...` writes a bounded instruction
trace through the MAME debugger. Results go to
`runs/sresults_<name>.csv` and `runs/tlb_<name>.csv`.

State on 2026-10-16:

- `--groups tlb`: all 37 run; the handlers log misses with SRR1, HASH1/2
  and the PTE loaded (`runs/tlb_603_mame_tlb.csv`).
- `--groups basic` (everything but the sweeps): all 325 run, 65 exceptions
  recorded (`runs/sresults_603_mame_basic.csv`, `runs/tlb_603_mame_basic.csv`).
  Three `exc` sequences are abandoned on purpose: MAME's 603 delivers the
  BAT protection faults of `dsi-ro-store`, `dsi-noaccess` and `dsi-nobat`
  as TLB misses (see below), and a miss outside a `tlb603` sequence has no
  page table of ours to search, so the handler records it (vector 0x1100 or
  0x1200, DMISS in the DAR column, DCMP in DSISR's) and abandons the
  sequence. Before that rule existed the handler searched whatever SDR1
  pointed at and the run went astray after `dsi-ro-store`; found by
  bisecting with `--skip-groups`/`--skip`.
- `--groups sweep`: not possible under MAME. Its 603 aborts the emulator on
  an instruction it has not implemented (`eciwx` first, then others in the
  opcode sweep) instead of raising the program exception; `MAME_SKIP` holds
  the names known so far, `--skip` adds more. The sweeps are for QEMU, the
  RTL bench and the real machine.

What MAME's 603 does differently from the manual, seen so far: it never
raises a DSI: every data-access fault, a BAT protection violation included,
is delivered as a DTLB miss (`ppcdrc.cpp`, the `tlbmiss` label); `tlbie`
invalidates one page, not the set; `tlbld` picks the way at random (so
`SRR1[WAY]` and the three-pages-one-set sequences are noise there); a
reloaded entry is writable iff the PTE's C bit was set (PP is ignored, so
`store-readonly` does not fault and `load-then-store` does not miss again);
SRR1 carries only the I/D and load bits, never KEY or WAY. Each of these is
a reason the real chip is the reference.

### Other targets

- **MiSTer core, Verilator bench:** MacPPC7300's `verilator/run_core.py`
  runs programs from memory images; load the blob at `--base` with
  translation off and PC at the base, run until the DONE word, dump. To be
  wired up when `DSPPC603` exists.
- **QEMU** (`qemu-system-ppc -cpu 603`, a software-TLB 603 model): needs a
  machine whose firmware will hand over to a raw blob; a tiny ELF wrapper
  for `-kernel` on `g3beige` is the likely route. Not tried yet.
- **The real 62xx:** below.

### First real run: Performa 6300CD, 2026-10-18

Gestalt `cput` 0106 (603e), machine 42, System 7.5.5. All 79,624 vectors
ran in 2,332 ticks (39 s); the file's checksum matched the Mac's. A second
run produced byte-identical records (the standard the 604 data met). An
intermediate run aborted at vector 0x104C0 for lack of disk space: the
image builder had sized the HFS partition by the wrong map field (20 MB
instead of 64); fixed the same morning. Against
the 604 reference, 37,036 of 37,336 shared vectors are identical. The 855
vectors that differ from the expectations (604 values or the software
model) are the 603e's own behaviour, now data for `DSPPC603`:

- **Undefined divides** (`divw`/`divwu` by zero, `0x80000000 / -1`): the
  603e returns 0 for a non-negative dividend and `FFFFFFFF` for a negative
  one, and `80000000` for the overflow case. The 604 returns other values.
- **Single-precision fused ops** (`fmuls`, `fmadds`, `fmsubs`, `fnmadds`,
  `fnmsubs`, with and without `.`): about 400 vectors differ in the low
  bits of the result and in FPSCR's FR/FI bits, in the `gen-fma`,
  `gen-fp-binary` and `model*` sources. The 603e rounds these differently
  from the 604 and from the model.
- **`stfs` of doubles below the single-precision range** (83 vectors, the
  `model-mem` source): the 603e stores a different bit pattern from the
  model's flush-to-zero prediction. The architecture leaves this
  undefined.
- A handful of `dingus-int`/`dingus-fp` and `model-enable` cases, to be
  looked at one by one.

The probe disk ran the same morning: Mixed Mode from a boot block works
(the echo returned), `mfmsr` did not return. Boot-block code is in user
mode on this machine, so the supervisor tier needs the Booter route.

## 3. Supervisor mode on the 62xx

### The question the probe disk answers first

The 040 and 020 benches ran in supervisor mode because their boot blocks
own the machine before the System loads. On a PowerPC Mac the boot
blocks are 68k code under the ROM's emulator, and whether code reached
from there runs with the PowerPC in supervisor mode is not documented
anywhere we found. `probe/` settles it in one boot: `probe_boot.s` is a
1 KB HFS boot block (the 040 bench's header and driver-queue walk) that
builds a Mixed Mode routine descriptor around three PowerPC routines held
in the block (`li r3,0x5050`; `mfmsr`; `mfspr PVR`), calls each through
the emulator's `$AAFE` trap, and writes a record to `/Results` with the
driver's `_Write` before and after every call. `build_probe.py build`
makes the disk (same envelope as above, 32 MB) and `build_probe.py read`
prints the record: how far it got, and if `mfmsr` returned, MSR[PR].

If PR = 0, boot blocks are a supervisor route and the next step is a boot
block that loads `super603.bin` to its base and jumps to it (the blob
already needs nothing else; `/Results` becomes its dump area). If
`mfmsr` never returns, the route below is the one.

### If not: the MkLinux Booter route

Under classic Mac OS every piece of code outside the NanoKernel (the 68k
emulator, the Toolbox, applications, drivers) runs in user mode. There is
no Open Firmware on a 52xx/62xx, and no NetBSD/Linux port for the board
(MkLinux listed the 52xx/53xx/62xx/63xx as supported; monolithic Linux and
NetBSD never ran on them). So the supervisor tier cannot be a Mac OS
application, and the Open Firmware route of ppctest does not exist.

The route that is known to have worked on exactly these machines is
**Apple's MkLinux Booter**: a Mac OS extension (type `scri`, so it loads
before other extensions) that loads a kernel image file from the System
Folder and hands the machine to it in supervisor mode, on NuBus-class
Power Macs including the 5200/6200. MkLinux's kernel source
(`slp/osfmk-mklinux` on GitHub, `osfmk/src/mach_kernel/ppc/boot.h`,
`ppc_init.c`) documents what the kernel receives: a `boot_args` structure
(version, the kernel's and bootstrap task's region tables, a command line,
the physical DRAM banks, the video frame buffer, the machine type) and an
entry with translation on through BAT0/BAT1 identity-style mappings of the
low megabytes. Our blob is already position-independent and sets its own
MSR and BATs, so it needs only a small entry shim that reads the physical
base it was loaded at (from `boot_args`, or by `bl`/`mflr` while the
booter's identity mapping is still in force) and jumps to the program.

What is not yet known is the **container format** the Booter loads
(`makeboot` in the MkLinux build, which is not in the conserved source
tree; the Booter binary and the kernels it loaded are on SourceForge under
`nubus-pmac`). The plan:

1. Fetch `Apple_MkLinux_Booter.sit.hqx` and one `MkLinux Booter kernels`
   image from the nubus-pmac project files; unpack the kernel image and
   compare it with a Mach/ELF kernel of the same release to learn the
   header `makeboot` prepends (or confirm it is a plain Mach-O/ELF the
   Booter parses).
2. Wrap `super603.bin` in that container with a shim that fills in the
   base, and a results path: the blob's header and records sit in RAM;
   the shim's exit either returns to the Booter (if the protocol allows)
   or soft-resets through Cuda, after which a Mac OS application reads the
   results out of physical memory (`Mac OS` does not clear RAM on a warm
   restart; a second `boot_args`-style marker makes them findable), or,
   simplest, the shim writes them to the serial port at 38400 8N1 before
   resetting, as the 7300 tools print to Open Firmware's console.
3. Test the whole path under an emulator that runs Mac OS with a 603
   first: DingusPPC's Pippin boots the Pippin ROM on a 603 model, but the
   Booter needs Mac OS proper; DingusPPC's PDM (6100, a 601) or a 7300
   with `--cpu 603` are the candidates.

The 603's exception-level facts the `DSPPC603` work needs most (the TLB
miss register contents, TGPR, `tlbie` semantics, the alignment DSISRs,
which SPRs exist) all come from this tier on the real machine. Until the
Booter route is built, MAME's run is a check of the program, not data.

## 4. Files

| File | Purpose |
|---|---|
| `ppc603test.py` | host tool for the user-mode tier: `vectors`, `image`, `decode`, `diff`, `selftest` |
| `vec603.py` | the vector-file and results-file formats shared with the Mac application |
| `macapp/main.c`, `macapp/CMakeLists.txt` | the Mac OS runner (Retro68, PowerPC CFM) |
| `super/super603.py` | the supervisor tier: sequences (`tlb603` group), the program, the MAME runner, the decoder |
| `probe/probe_boot.s`, `probe/build_probe.py` | the bootable probe disk: is boot-block code in supervisor mode on a PowerPC Mac? |
| `envelope/` | the 96-block Apple partition map + Driver43 envelope the images start from (git-ignored) |
| `DAY1.md` | the checklist for the first session with the machine |
| `runs/` | decoded results: `results_*.csv` (user mode), `sresults_*.csv` and `tlb_*.csv` (supervisor) |
| `ppc603.vec`, `*.hda`, `super/super603.bin`, `macapp/build/` | build outputs, git-ignored |
