# Resume: the Pippin's CPU at 66 MHz (written 2026-10-24)

Resume the Bandai Pippin MiSTer core's work with one goal: **close timing with the CPU
(DSPPC603) and the machine at 66 MHz** (the console's own clock; today 58.333 MHz), then
prove it on the board. Everything else on the core is done for now and committed on `main`
(see `RESUME_pippin_board.md` for the whole history and `README.md` for what the core does).

## Rules the user set (follow them)

- **Work on your own**: decide and run builds, bench runs and board tests without asking;
  report results. Everything on `main`, committed and pushed (the Mac pulls from GitHub).
  No side branches (`align603` stays as it is).
- **Quartus here (Linux), Verilator on the Mac** (`ssh dani-dev.local`, tools under
  `zsh -lc`, `VJOBS=6`; bench runs in `~/pippin_bench/`). **One simulation at a time per box.**
- **Every Quartus flow under `flock /tmp/quartus.lock ...`** (other sessions share it). A full
  compile is ~25 min; slack in `output_files/BandaiPippin.sta.rpt`. **Commit before every
  build**; keep each rbf as `scratch/BandaiPippin_<commit>.rbf`.
- **Board** (.92, MiSTerss1, shared with other Claude sessions): ask them by SendMessage,
  take `/tmp/board.lock` on the MiSTer (`set -o noclobber`), remove it after. **Load cores
  only through the OSD** with misterkvms-cli (keys and screenshots; never `load-core`, mrext
  or MiSTer_cmd). Copy rbfs with `syn/mister.py put-core`.
- **Releases are date-stamped** (`releases/BandaiPippin_YYYYMMDD.rbf`), **no git tags**, and
  **no GitHub release until the user says**. Don't modify MacPPC7300; report Main_MiSTer or
  MacPPC7300 changes to the user.
- If misterkvms recordings come back with `audio_seconds: 0`, it's the capture, not the core:
  tell the user.
- Shell pitfall: `pkill -f`/`pgrep -f` match your own command line; kill by PID.

## Where things stand

- `BandaiPippin.sv:60` `CPU_MHZ = 58` (58.333 MHz = the PLL's 700 MHz VCO / 12). `rtl/pll.v`
  and `rtl/pll/pll_0002.v` know 58, 70 (/10) and 100 (/7), the 100 MHz switch done at run
  time through `pll_cfg` (`spd_pll`, `cpu_fast`). The memory clock is 100 MHz (/7), video
  20 MHz (/35). **66 MHz is not reachable from a 700 MHz VCO**: 66.667 MHz needs e.g. an
  800 MHz VCO (/12; memory /8, video /40) or 1000 MHz (/15, /10, /50); exactly 66.000 needs
  660 MHz (/10, but then 100 and 20 MHz are not integer). The time base (`TB_HZ 16500000`,
  66/4) and the machine's timers take `CPU_HZ` / `CPU_HZ_FAST` as parameters
  (`Pippin_system`, `Pippin_machine`: VIA, SCSI, Cuda, sound ticks), so they follow the clock.
- **Timing at 58.333 MHz is already thin**: the last builds met it by +0.094 to +0.315 ns
  depending on the fitter seed (`BandaiPippin.qsf` SEED, now 2). 66.667 MHz (15.0 ns) needs
  about **2.2 ns** more from the CPU's longest paths (17.14 ns at 58.333).
- Known slow paths, all inside DSPPC603 (CPU clock = `counter[1]`):
  - build 37 (70 MHz attempt / seed 7): `ex_b -> cr`, `msr -> TLB valid` (DSPPC603's EX
    operand into the condition register; the MSR into the MMU's TLB valid check);
  - build 47 (58.333, seed 3): from the data cache's `tag_mem[1][0].valid` RAM write-enable
    register;
  - the CPU alone (`docs/DSPPC603_notes.md`, "Size and speed"): Fmax 60.8 MHz slow 100 C,
    -1.28 ns at 66 MHz; slowest families: the data cache's request address into the FPU's
    normalising shift, the FPSCR's commit from the FP operand fields, the instruction
    cache's tag RAM into EX's operand.
  - The 100 MHz memory clock is fine since 68219cb (Pippin_sdram's 8-bit timer); the CPU <->
    memory crossing is `DSPPC603_memcdc` (asynchronous groups in `BandaiPippin.sdc`).
- Tools: `python3 syn/check.py core --cpu 603 --mhz 66 --paths 40 [--detail 2]` fits the CPU
  alone (fast loop); `quartus_sta -t` with a `report_timing -to_clock ... -npaths N` script
  for the whole core (example in the 2026-10-24 session: paths to `counter[1]`).
  `scratch/seedsweep.sh SEED...` fits several seeds and keeps the first that passes.
- Regression, in this order:
  1. the CPU benches on the Mac: `verilator/run_core.py` (lockstep random programs against
     dingusppc) and `cputest/` (the 603 suite, `docs/prompts/DSPPC603_build.md`);
  2. the machine bench, lockstep boot (`verilator/run_machine.py`, the `run5.sh` template in
     `RESUME_pippin_board.md`, with `--cpu-mhz` and `-GCPU_HZ` set to the new clock);
  3. on .92 (build with TRACE 0): Macintosh on Pippin to the Finder, Super Marathon, Racing
     Days (CD audio), Power Rangers Zeo; Eject + Game disc; a save reaching the SD card;
     three cold core loads in a row (build 37 had one black boot of three at negative slack).

## Plan

1. Measure: the CPU alone at 66.667 MHz (`check.py core --cpu 603 --mhz 66.667 --paths 40
   --detail 2`) and a whole-core fit with `CPU_MHZ` 66 to list the failing families.
2. Shorten the worst families in DSPPC603 without changing behaviour (pipeline registers
   where the 603e's timing allows one more cycle, precomputed compares, splitting the
   cr/MSR/TLB-valid and cache-tag paths). Each change: lint, the CPU benches, then a fit.
3. Add the 66.667 MHz PLL setting (a VCO that gives 100 and 20 MHz too; keep 58.333 as a
   fallback `CPU_MHZ` value), `CPU_HZ` 66_666_667, check `TB_HZ` (the 603's time base runs
   at bus/4: 16.667 MHz for a 66.667 MHz bus) and the timer derivations.
4. Whole-core builds and seed sweeps until setup and hold pass on every clock with margin.
5. The regression above, then update `README.md` (Known limits: CPU speed), the release notes
   and `RESUME_pippin_board.md`; a new date-stamped rbf in `releases/` (not published).

## Loose ends (not CPU work)

- `releases/BandaiPippin_20261024.rbf` is build 50 (4beb0ce): the hard disk entry was still
  under Advanced. The source (86622a2) has it on the first page; the next build replaces the
  rbf (the user: no rebuild just for that).
- `s7_boot.png` and `s7_rom_70s.png` in the repo root are untracked old screenshots: ask the
  user whether to keep them.
- A second Eject during the insert-disc animation is not seen by the ROM (Insert disc covers
  it).
