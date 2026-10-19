# Apple Pippin MiSTer core: the two-week plan

Written 2026-10-18 for review. It replaces the phase order of
[implementation_plan.md](implementation_plan.md) (which stays as background)
with a schedule aimed at a **workable Pippin on the DE10-Nano by
2026-11-01**. Everything marked "measured" was checked today; the rest is
reasoning, and says so.

## 1. What "workable" means

Done when, on the board:

1. The core loads from the OSD with the Kinka ROM, Cuda powers it up, and
   the Pippin logo and the insert-disc screen appear on HDMI at 640 x 480.
2. A Pippin disc image (CUE/BIN, CHD or ISO) mounted from the OSD boots to
   its title: Pippin Kickstart and at least three retail titles.
3. Sound plays: AWACS (the startup sound, a title's effects) and CD audio.
4. A MiSTer gamepad works as the AppleJack controller (buttons and the
   trackball as the pointer).
5. Saves survive a restart (the 128 KB flash, kept on the SD card).

Left for after the two weeks (section 9): the 603's software TLB reload,
NTSC/PAL output with Taos's flicker filter, the floppy dock, and the real-hardware run of the supervisor tests. The modem
port is in: Grand Central's ESCC is MacPPC7300's, with its UART, MIDI and
CTS/RTS wiring to the MiSTer.

## 2. What we know now (2026-10-18)

- **The CPU is ready.** DSPPC603 (milestones A and B,
  [DSPPC603_notes.md](DSPPC603_notes.md)) matches the 603e's 79,624 measured
  vectors bit for bit, passes MacPPC7300's whole pipeline suite in lockstep,
  and synthesises to 14,895 ALMs, 107 RAM blocks, 60.8 MHz worst case
  (DSPPC604 at the same settings: 57.6 MHz, and it runs at 70 MHz on the
  board).
- **The reference machine exists (measured).** `verilator/machref
  --machine pippin` runs DingusPPC's Pippin headless on our Kinka 1.0 ROM:
  the Pippin logo is on screen at 300 million instructions (about 5 s of
  machine time), with every device access logged. That run settles several
  of the old open questions, for DingusPPC's model at least:
  - **Q2, the CD controller:** the ROM talks to MESH (GC + 0x18000, 3,168
    accesses) and never to the 53C94 (GC + 0x10000). The CD is on MESH, as
    MAME has it.
  - **Q4, VBL:** Taos's interrupt-enable register is only ever written 0.
    The 60 Hz tick comes from the VIA/Cuda path, as on a Power Mac; Taos
    needs no interrupt.
  - **Q7, the TLB reload:** DingusPPC has no 603 TLB-miss exceptions at all
    (it walks the page table in hardware) and boots. So DSPPC603's
    hardware walk is enough for this plan; the faithful reload stays a later
    milestone.
  - **Devices the ROM touches before the logo:** Aspen (79 accesses), PCI
    configuration (44), Taos registers (180) and CLUT (352), and in Grand
    Central: the interrupt registers, DBDMA, the SCC, AWACS, SWIM3 (81),
    the VIA (213,000, mostly polling its interrupt flags: Cuda), MESH, and
    the NVRAM at + 0x1D000. No 53C94, no
    MACE, no flash yet (the flash is probed later, at 0x40000000).
  - **The PVR's revision half** is not used by any ROM code (21 reads, all
    on the version half): the core's `00030100` boots the same as any 603.
- **Most of the machine is already RTL** in MacPPC7300 (21ba191): Grand
  Central, DBDMA, the VIA and Cuda (the same 341S0060 firmware on an RTL
  68HC05), ADB, the ESCC, AWACS, MESH, the SCSI CD target and CD audio,
  SWIM3, Athens, the NVRAM save, the SDRAM controller and clock crossing,
  the video scan-out and the VRAM write combiner, the debug readout. New:
  Aspen, Taos, the flash, the machine's address decoder, the top level.
- **Main_MiSTer** turns its Mac CD support on by core name
  (`support/mac/mac.cpp`, `is_mac_scsi_family()`: `maclc`, `macplus`,
  `macquadra800`, `macppc7300`). A core named `BandaiPippin` needs one line
  on your `Mac-ppc-enhancements` branch.
- **Simulation speed** (MacPPC7300's machine bench): about 400,000
  instructions a second in lockstep, so the logo (300 million) is about 13
  minutes of bench time.

## 3. Decisions taken (change any of them in review)

| Decision | Why | Alternative |
|---|---|---|
| Keep DSPPC603's hardware page-table walk; milestones C and D (603 exception vectors, software TLB reload) after "workable" | DingusPPC boots the Pippin without the reload; the reload is a CPU-wide change with its own verification | Do D first (adds about 4 days, delays everything) |
| The machine RTL is copied from MacPPC7300 21ba191 into `rtl/machine/`, renamed `Pippin_*`, recorded in `cpu_import.md` | The rule of 2026-10-17: each core owns its copy | A submodule (the old plan's Phase 0 idea) |
| Kinka 1.0 is the bring-up ROM | It is the one we have with a retail identity; 1.3 replaces it as the default as soon as it arrives | |
| 5 MB RAM by default (the retail machine), OSD option 13 MB | DingusPPC's and MAME's retail setting | |
| Video: Taos reports **NTSC (monitor ID 5) by default**, the OSD offers VGA (ID 6) and PAL (ID 3); the scan-out follows Taos's own timing registers (480i at 15.7 kHz for NTSC, 640 x 480 at 31 kHz for VGA), from the frame buffer in DDR3 through MacPPC7300's video path; HDMI through ascal either way | The real @WORLD's default output, and DingusPPC's default (the reference run is NTSC); 15 kHz analog out for CRTs comes with it | VGA default (simpler timing, no interlace) |
| Clocks: CPU 66 MHz, memory 100 MHz (as MacPPC7300) | The real Pippin's 66 MHz; MacPPC7300's board runs at 70 | 70 MHz if titles need speed |
| Core name `BandaiPippin`, CD on block slot 4, Main_MiSTer's Mac CD path | The same contract as MacPPC7300, so its CD target RTL is reused unchanged | |
| Flash saves in a `.sav` on block slot 2, written back like MacPPC7300's NVRAM | The same mechanism, already proven | |

## 4. Architecture

```
BandaiPippin.sv            the MiSTer top (from MacPPC7300.sv): hps_io, OSD, PLL, SDRAM,
                          DDR3, video out, audio, block slots, ROM download
rtl/DSPPC603/             the CPU (done)
rtl/machine/
  Pippin_system.sv        CPU + machine + clock crossing (from MacPPC7300_system)
  Pippin_machine.sv       the address map and device decode (new; MacPPC7300_machine as model)
  Pippin_aspen.sv         new: RAM banks and their mirror windows, MEM_CONFIG,
                          SYSTEM_ID 40010000, VERSION 01000000, GPIO, PCI config
                          at F2800000/F2C00000 presenting Grand Central (106b:0002)
  Pippin_taos.sv          new: registers at F0800000, CLUT at F1000000, GPIO_IN
                          (monitor ID 6, tray closed), 8 bpp CLUT / 16 bpp 555
                          scan-out timing from its registers
  Pippin_flash.sv         new: Am29F010 at 40000000 (byte lane D0-D7, bit-reversed),
                          program / sector erase / chip erase / autoselect
  Pippin_gc, _dbdma, _cuda, _hc05, _cudarom, _adb, _escc, _awacs, _mesh,
  _scsidisk, _scsibus, _cdaudio, _swim3, _athens, _nvsave, _sdram, _vramwc,
  _video, _debug, _bootrom, _pkg   copies of MacPPC7300's, renamed
```

Memory map (MAME and DingusPPC agree; [core-dev/README.md](core-dev/README.md) §1.2):
RAM banks on 16 MB boundaries (4 MB at 0, 1 MB at 0x01000000, expansion at
0x02000000/0x03000000) with Aspen's mirror windows; flash at 0x40000000;
Taos VRAM 0xF0000000 (1 MB), registers 0xF0800000, CLUT 0xF1000000; PCI I/O
0xF2000000, PCI config 0xF2800000/0xF2C00000; Grand Central at 0xF3000000
(placed by the ROM through PCI config); Aspen registers 0xF8000000; ROM
0xFFC00000 (4 MB, in SDRAM). The CPU's one interrupt comes from Grand
Central. The time base ticks at 16.5 MHz (66 / 4).

The AppleJack: an ADB device at its own address with MAME's button layout
(`adbhlepippin.cpp`), added to MacPPC7300's ADB (which already has the
keyboard, mouse and game controllers), driven by the MiSTer joystick and
its analog stick.

## 5. How each step is checked

1. **The machine bench in lockstep** (`run_machine.py`, from MacPPC7300's,
   for `Pippin_system`): the ROM runs from reset with dingusppc's CPU
   checking every instruction's registers; device reads are handed to both.
2. **The device log against DingusPPC's whole Pippin** (`machref --machine
   pippin`, `devdiff.py`): where the RTL's devices answer differently, the
   two logs part.
3. **Frames**: the bench's frame at N instructions against `machref
   --frame-at N`, pixel for pixel (the logo at 300 million is the first).
4. **Disc boot in simulation**: `machref --set cdr_img2=disc.iso` puts a
   disc on DingusPPC's MESH; the RTL bench gets the same image through its
   SCSI image server.
5. **The CPU suites** stay green after any CPU change (`run.py`,
   `run_core.py`).
6. **The board**: an `.rbf` built here (Quartus 17.0 is installed), then
   loaded on the MiSTer. If you give me network access to it (section 8),
   MacPPC7300's `syn/mister.py` drives it from here (copy the core, load,
   screenshot, keys); otherwise you load it and send a photo or screenshot.

## 6. Schedule

Each day ends with a commit; the bench numbers go in the commit message.
The days are working days for me; board tests need you or remote access.

| Day | Work | Done when |
|---|---|---|
| 1 (Oct 19) | Import the machine RTL and the machine bench (`core_main` machine mode, `run_machine.py`, `run_gui.py`). `Pippin_machine` with ROM, RAM, Aspen (registers, mirrors, PCI config), Taos registers as storage, everything else open bus. | The ROM runs from reset in lockstep through Aspen's memory sizing and its PCI configuration of Grand Central (the first 1-2 million instructions), device log equal to `machref`'s to there |
| 2 | Grand Central, DBDMA, VIA, Cuda (cold start holds the CPU), ADB, ESCC, SWIM3, NVRAM, AWACS, Athens on Cuda's I2C; MESH with no targets | Lockstep through Cuda's power-up and PRAM traffic into Mac OS's start (tens of millions of instructions); devdiff clean apart from timing |
| 3 | Taos: CLUT, GPIO_IN, timing registers, the scan-out from VRAM in DDR3 (MacPPC7300's video path) | The bench's frame at 300 million instructions equals DingusPPC's Pippin logo |
| 4 | The MiSTer top: `BandaiPippin.sv`, `.qsf`, PLL (66/100 MHz), OSD (ROM, RAM size, reset), ROM download, video and audio out; first full Quartus build | It builds; timing within MacPPC7300's usual slack; size measured |
| 5 | **Board test 1** (you or remote): the logo on HDMI. Fix what the board shows. Meanwhile: the flash (`Pippin_flash`), its save on slot 2 | The logo and the insert-disc screen on the board; the flash passes its own bench (command sequences against the datasheet) |
| 6 | MESH with the CD target at ID 3 (MacPPC7300's, its INQUIRY changed to the Pippin's drive: MATSHITA CR-8005A 4.0i), CD audio; the Main_MiSTer line for `BandaiPippin` (commit on your branch, you build Main) | In the bench, a disc image boots past the insert-disc screen, its SCSI traffic matching DingusPPC's (`cdr_img2`) |
| 7 | The AppleJack on ADB, the gamepad and analog-stick mapping, OSD buttons (eject, reset, power) | The controller's ADB traffic as DingusPPC's AppleJack; the pointer moves in the bench |
| 8 | **Board test 2**: a disc (Kickstart, then a title) from the OSD, sound, controller | A title starts on the board with sound and controller |
| 9-10 | Compatibility: the titles you have, each to its first interactive screen; fix what fails (lockstep runs of the failing title in the bench find the CPU's and devices' part) | Most titles start; a list in `docs/compatibility.md` |
| 11 | Speed: compare a title's frame rate with DingusPPC/MAME and with a real Pippin if one is around; the 70 MHz option if needed. Timing pass on the full build's worst paths | No title slower than the real machine where we can compare; the build at its target clock |
| 12 | Kinka 1.3 (when you have it) as the default; RAM options; the OSD finished | Both ROMs boot to the insert-disc screen |
| 13-14 | Buffer for what the board finds; README (ROM files and CRCs, disc formats, OSD), the release `.rbf` in `releases/` | Your sign-off |

The buffer is thin. If a day slips, Days 11 and 12 move behind the first
release, not the board tests.

## 7. What can go wrong

| Risk | How it shows | What then |
|---|---|---|
| Something past the logo needs the 603's TLB-miss exceptions (DingusPPC never takes them, MAME does) | A title or Mac OS path crashes where DingusPPC also fails, or MAME works and DingusPPC does not | Milestone D (4-5 days) with the tests already written; it is the first thing after the two weeks or replaces Days 11-12 |
| A title is timing-sensitive (DSPPC603 runs more per clock than a 603, but has half a 604's cache) | Wrong speed, audio drift, a hang in a busy loop | A speed option (66 / 70 MHz, a throttle) |
| Taos or Aspen behaviour neither emulator models | The board shows what the bench does not | `hwprobe`-style measurements need a real Pippin: if you have one, say so |
| The CD contract (Main_MiSTer's Mac path) differs for the Pippin's drive commands | Disc boot fails at the SCSI level | MAME's `NSCSI_CDROM_APPLE` lists the Apple vendor commands; the CD target gets them |
| The full build misses 66 MHz by more than the 7300 does | Worst-case slack below about -2.5 ns | The worst paths are known (the FPSCR commit, the cache-to-FPU shift); Days 11-12 |
| ROM 1.0 refuses later titles (authentication) | A signed disc ejects | Kinka 1.3, or Kickstart |

## 8. What I need from you

1. **ROMs and discs:** received 2026-10-18 in `scratch/pippin/` (git-ignored):
   Kinka 1.3 (87a1337d) and 1.2 (4fead4b3), both MAME's; the GM/dev ROM; the
   1.0 ROM's four chips; Super Marathon (U), Power Rangers Zeo (USA),
   Racing Days (J, CD audio), Macintosh on Pippin (USA), all BIN/CUE. With
   1.3 here it is the default ROM from Day 1 (1.0 stays as the second ROM
   that must keep booting); Day 12's ROM work shrinks to the options. No
   Kickstart: the retail discs are signed and boot on the retail ROMs.
2. **Board access, to work without waiting on you:** the MiSTer's address,
   an SSH key for it (MacPPC7300 used `~/.ssh/mister_only`), the MiSTer
   Remote (mrext, port 8182) running on it, and the board's HDMI on your
   capture if you want `kvms.py`. Without it, board tests 1 and 2 (Days 5
   and 8) need about 30 minutes of you each.
3. **Main_MiSTer:** done 2026-10-18 on a new branch `pippin-cdrom` off
   your fork's `master` (00bdff0, which already has MacPPC7300's CD support),
   in the worktree `~/repos/Main_MiSTer-pippin`: `pippin` added to
   `is_mac_scsi_family()` and `is_mac_scsi_optimized()` (commit 0e25569, not
   pushed). It builds with `~/gcc-arm-10.2-2020.11-x86_64-arm-none-linux-gnueabihf`
   on the PATH (`bin/MiSTer`); it goes on the board with the first disc test
   (Day 6-8).
4. **A real Pippin:** if you have one, a few measurements would settle what
   the emulators guess (Taos, Aspen, the PVR); not needed for the plan.

## 9. After the two weeks (in order)

1. Milestone C: the 603's exception vectors (0x1300, 0x1400; no 0x0F00) and
   SRR1 contents.
2. Milestone D: the software TLB reload
   ([prompts/DSPPC603_tlb_reload.md](prompts/DSPPC603_tlb_reload.md)), its
   tests in `cputest/super/super603.py`, the hardware walk kept as an option.
3. The supervisor run on the 6300 through the MkLinux Booter (answers the
   `q603` and `tlb603` questions on real silicon).
4. Taos's flicker convolution for interlaced output on CRTs.
5. The floppy dock (SWIM3 is already there).

## 10. Progress log

**2026-10-18 (Day 1, with parts of Days 3-7).** Branch `pippin`.

- The machine: MacPPC7300's machine RTL imported as `rtl/machine/Pippin_*`
  and changed for the Pippin: Aspen's banked RAM with its sizing windows,
  registers and PCI (Grand Central at device 16); Taos's registers, colour
  table, VRAM and scan-out (`Pippin_taosvideo`: its own timing registers,
  NTSC interlaced as two fields, 16-bit pixels through the table); Athens at
  I2C 29 on its 20 MHz crystal; the save flash (`Pippin_flash`, Am29F010,
  passes its unit bench); the AppleJack on ADB (controller 5); CPU 70 MHz
  (MacPPC7300's PLL), time base 16.5 MHz, no L2.
- The bench: `run_machine.py` runs the whole Pippin in lockstep with
  dingusppc's CPU; its reference memory is Aspen's map (banks, windows, the
  holes as devices) with Taos's VRAM as RAM. Kinka 1.3: Cuda powers the
  machine up, then **23.2 million instructions in lockstep** (memory
  sizing, PCI, Open Firmware, the NanoKernel's SPR probes, into Mac OS),
  until a bench fault (the VRAM was device space to the reference; fixed,
  being rerun).
- The MiSTer top (`BandaiPippin.sv`, from MacPPC7300's): the OSD (ROM, CD on
  slot 4, the save flash on slot 2, RAM 5/13/21 MB, video NTSC/VGA/PAL, the
  AppleJack first), Taos's field to the framework. Quartus Analysis &
  Synthesis passes; no fit yet.
- Main_MiSTer `pippin-cdrom`: the core's name in the Mac SCSI family; builds.
- Lessons: Verilator builds at `-j 3` (an OOM reboot at -j 0 next to a
  Quartus fit); the dingusppc Pippin's logo frame (Kinka 1.3, 300 M
  instructions) is the reference for the first picture.
- **First full build** (2026-10-18 16:04, Quartus 17.0, seed 1): 33,731 ALMs
  (80 %), 340 RAM blocks (61 %), 48 DSP blocks; the CPU's clock 63.14 MHz
  worst case against its 70 MHz (slack about -1 ns, as MacPPC7300's 70 MHz
  builds that run on the board), memory 101.0 MHz. Not yet on the board.
- The reference for discs: dingusppc's Pippin (Kinka 1.3) boots Super
  Marathon to its title screen at 1.4 billion instructions. The bench now
  serves a CD (`--cd FILE.cue`, the Main's own response code).

**2026-10-18 (evening): the first picture.**

- **The Pippin logo in the RTL, pixel for pixel DingusPPC's** (Kinka 1.3,
  5 MB, NTSC interlaced, the frame woven from its two fields): the bench's
  frame after 384 million instructions equals dingusppc's at 260 million,
  cursor included. The scan-out, Taos's colour table, the 16-bit pixels
  and the interlace are right.
- Why later than DingusPPC: the boot chime. Mac OS waits for its sound DMA
  (Grand Central's audio-out channel, polled at 68065E98); the RTL plays it
  in real time (about 2 seconds, some 100 million instructions), dingusppc's
  null sound host finishes it at once. The 301 M frame of the first run was
  simply taken before the logo was drawn (`--vram-dump` showed the frame
  buffer untouched). On the board: about 7.5 s from reset to the logo.
- Super Marathon from the bench's CD (the Main's own CD responses): 807
  blocks read, lockstep identical to 735 million instructions, where the
  core took `dcbz`'s alignment exception (a ROM block move onto a W or I
  page, or with the cache off) and dingusppc does not model it. The bench
  now hands it to the reference; rerunning to the title screen (dingusppc
  shows it at 1.4 billion). DSPPC603's DAR for it is an open 603e question
  (two new `tlb603` sequences; the generator's PTE WIMG bug fixed).

**2026-10-18 (night): ready for the board.**

- The core is **BandaiPippin** (the Quartus project, `_Console/BandaiPippin_<date>.rbf`);
  its OSD name is **Pippin**, so its folders are `games/Pippin`, `saves/Pippin`,
  `config/Pippin.*`. Main_MiSTer `pippin-cdrom` (084ed6a, 557a706; not pushed)
  knows it as `pippin`.
- `syn/mister.py install` sets a MiSTer up: the core, the pippin-cdrom Main as
  `MiSTer_pippin` with MiSTer.ini's `[Pippin] main=MiSTer_pippin` (other cores
  keep the board's Main), the ROMs (Kinka 1.3 as `boot.rom`; 1.2, 1.0, GM Flash
  in the OSD's ROM list) and the discs: Super Marathon as CUE/BIN, Racing Days,
  Macintosh on Pippin and Power Rangers Zeo as CHD.
- CHD: the Main's Mac CD layer reads CHD (data and CD-DA). `verilator/maincd`
  builds the Main's own CD code on the host; `cdcheck` found a CHD with an
  unstored pregap (Racing Days) mounting 150 sectors longer than its CUE, fixed
  in the Main (557a706); all three CHDs now equal their CUE/BIN. The bench's
  slot 4 is served by that same code (`cdhost.h`).
- The build for the board (seed 7, 21:05): 80 % of the ALMs, 340 RAM blocks;
  the CPU's clock 59.7 MHz worst case against 70 (slack -2.47 ns, total -328
  ns; seed 1 of the same source: -2.71, -1242). Worse than the first build's
  63.1 MHz; the worst paths to be looked at. The board will say whether 70 MHz
  holds; if not, the CPU clock comes down for the first test.
