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

## The decided architecture (the user, 2026-10-24)

**The CPU at 66.67 MHz, the machine on a 33.33 MHz bus**, as a real 603 runs its core at a
multiple of its bus clock. One PLL, VCO 800 MHz: CPU /12 = 66.667, bus /24 = 33.333, memory
/8 = 100, video /40 = 20 (or VCO 1000: /15, /30, /10, /50). CPU and bus outputs from the same
VCO are phase-aligned, so the CPU <-> machine crossing is a synchronous 2:1 handoff (a
request held for a bus cycle, multicycle constraints between the two clocks), not an
asynchronous CDC. Today the machine (Grand Central, Taos, the VIA, SCSI, Cuda, sound: all of
`Pippin_machine`) shares the CPU's clock; moving it to the bus clock takes its logic out of
the 66 MHz budget. The machine's tick dividers already take their clock as a parameter
(`CPU_HZ`/`CPU_HZ_FAST` in `Pippin_machine`): give them the bus clock's rate. The memory
port (`DSPPC603_memcdc` to the 100 MHz SDRAM side) stays where it is, on the CPU side.
The CPU's own slow paths still have to come down to 15 ns: that is the main work.

## Findings so far (2026-10-24, keep this section current)

- **The CPU alone** (`check.py core --cpu 603 --mhz 66.667 --paths 40 --detail 3`, log
  `scratch/check66_core.txt`, before any change): 14,386 ALMs, **Fmax 58.30 MHz, worst slack
  -2.153 ns at 66.67 MHz**. No machine logic in that fit: the gap is DSPPC603's alone, so the
  33 MHz bus cannot close it by itself. Worst families (slack, count, from -> to):
  - -2.153 (458) `ex_dec.frc -> fpscr`; -1.692 (342) `ex_dec.fc.op -> fpscr`; -1.587
    `ex_pc8 -> fpscr`; -1.560 `mem_unit.cp -> fpscr`; -1.521 `ex_dec.unit -> fpscr`; -1.481
    (271) `ex_insn -> fpscr`; -1.472 `dcache.post_v -> fpscr`; -1.334 `comb -> fpscr`;
    -1.298 `fq_c_upd_r -> fpscr`; -1.185 `cq_fpr_o -> fpscr`. Path 1 cell by cell:
    `ex_dec.frc` -> Mux182 (operand decode) -> `completion_push_ex` (fan-out 71) ->
    `always21` -> `fpscr[12]` -> fpscr's register enable: 16.4 ns of data path, ~1/3 routing.
  - -1.670 `ex_dec.frc -> fb_mem`; -1.431 `-> srr1`; -1.376 `-> gpr_from_sequence`;
    -1.329 `-> id_rc_q`/`id_ra_q` (ID's stall/forwarding); -1.251 `-> mmu.d_cached_page`.
  - -1.510 (62) `wb_result -> cr`; -1.205 `mem_result -> cr`; -1.169 `fb_wb -> cr`: the
    condition register's writeback/forwarding.
  - -1.400 (153) `fpu.Mux0 -> completion_queue.value` RAM; -1.205 `fa_mem -> dcache.state`;
    -1.070 `mem_unit.cp -> fpu.ShiftLeft1`.
  So the hubs are **completion_push_ex** (the FP-op-into-the-completion-queue decision, ~25
  families feed FPSCR through it), **ID's stall/forwarding** (`id_ra_q`, `id_rc_q`), and
  **CR's writeback**.
- **Change 1 (1f00327)**: FPSCR's and CR's commit in EX gated by `fp_commit_ex =
  ex_fpu_taken | fp_simple_of(ex_dec.fc.op)` (a register and EX's decode) instead of
  `~completion_push_ex` (an FP op committing in EX was taken earlier or is answered in its
  own cycle; the one leaving into the queue is neither); a `$fatal` check holds them equal.
  `run_core.py` PASS on the Mac (all vectors, exceptions, 1,071,375 random instructions in
  lockstep, the CDC ratios; the check never fired). **Its fit** (`scratch/check66_core_b.txt`):
  **Fmax 58.30 -> 60.85 MHz, worst -2.153 -> -1.433 ns**; every FPSCR family gone. New worst:
  - -1.433 (233) `fb_wb -> cr`, -1.109 (115) `wb_result -> cr`, -1.051 (205) `mem_result ->
    cr`, -0.955 `fb_mem -> cr`, -0.942 `ex_dec.ic.sh_reg -> cr`: the forwarded operands into
    EX's compare into CR;
  - -1.111 (39) `Add29 -> mmu.d_cached_page`, -0.874 `Add29 -> fa_mem`, -0.781 `ex_pc8 ->
    mmu.d_cached_page`: EX's address adder into the data MMU's page compare;
  - -1.013 (71) `fb_mem -> mem_unit.state.S_RSP1`, -0.972 (185) `mem_result -> mem_unit.state`,
    -0.961 `-> S_REQ1`: forwarded operands into the memory unit's state machine;
  - -0.807 (92) `mmu.i_page_q -> pc_f`: the instruction MMU into the fetch PC.
- **The 33 MHz bus cut** (from reading `rtl/machine/Pippin_system.sv`): `Pippin_machine` is
  not only the I/O chips: the CPU's memory port goes through it (CPU `c_*` -> machine ->
  `m_*` -> `Pippin_l2` -> `DSPPC603_memcdc` -> SDRAM at 100 MHz), with snooping and Grand
  Central's DMA arbitration (`dq` state machine). Clocking all of it at 33 MHz would halve the
  CPU's memory path. **Cut at the machine's device bus instead**: the `p_*` request (already
  a register stage: `p_sel`, `p_dev`, `p_a`, `p_we`, `p_be`, `p_wd`) and `dev_rdata`/`dev_ack`
  back; the devices behind it (Grand Central with VIA/Cuda/MESH/SWIM3/ESCC/DBDMA/AWACS, Taos,
  the flash, Aspen's registers, PCI config, boot ROM/debug) on the bus clock; the address
  decode, RAM routing, snoop and the L2 stay at 66.67. Crossing the other way: Grand
  Central's DMA requests (`gdm_*`) into the arbiter, interrupts (`ext_irq`), `tb_tick`,
  Cuda's `cpu_reset`. The VRAM path (`v_*` -> `Pippin_vramwc` -> `vcdc`) stays CPU-side.
- Method notes: watchers with `pgrep -f 'syn/check.py'` match their own shell; poll the log
  for `constraint 66.67 MHz` instead. Other sessions (Sun-3, IBMRS6K7248) queue on
  `/tmp/quartus.lock` too: a fit may wait 20-40 min.

## Next steps (in order)

1. Read `scratch/check66_core_b.txt`: how much change 1 won; the new worst families.
2. Next hubs: whatever still feeds `completion_push_ex` (its own inputs: `fpu_ready`,
   `completion_count`, `ex_fp_elig`'s decode terms, `mem_fault`); then `id_ra_q`/`id_rc_q`
   (ID's hazard/forwarding compare against EX's destination: precompute in ID, register);
   then CR's writeback (`wb_result -> cr`). One change at a time: lint, `run_core.py` on the
   Mac, a CPU-alone fit; log the slack here.
3. When the CPU alone meets 66.67 with ~0.5 ns margin: the bus split and the PLL (below),
   then whole-core fits.

## Plan

1. Measure: the CPU alone at 66.667 MHz (`check.py core --cpu 603 --mhz 66.667 --paths 40
   --detail 2`) and a whole-core fit with `CPU_MHZ` 66 to list the failing families.
2. Shorten the worst families in DSPPC603 without changing behaviour (pipeline registers
   where the 603e's timing allows one more cycle, precomputed compares, splitting the
   cr/MSR/TLB-valid and cache-tag paths). Each change: lint, the CPU benches, then a fit.
3. The clocks: the PLL at VCO 800 with the CPU 66.667, the bus 33.333, memory 100, video 20
   (keep 58.333 as a fallback build); the machine on the bus clock behind a 2:1 synchronous
   bridge; `CPU_HZ` 66_666_667, the machine's dividers at 33_333_333; `TB_HZ` (the 603's time
   base runs at bus/4: 8.333 MHz for a 33.333 MHz bus; check what the ROM's timebase
   calibration expects) and the timer derivations. Bench first (the machine bench needs the
   two clocks too).
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
