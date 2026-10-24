# Resume: the Pippin's CPU at 66 MHz (written 2026-10-24; updated at the hand-off, ~13:00)

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

- **The CR path after change 1** (path 1 of `check66_core_b.txt`, 15.75 ns data path): the
  forwarded `fb_wb` -> `op_b` (fan-out 13) -> the ALU's shift count `sh_n` (fan-out 78) -> the
  barrel shifter (`ShiftRight0`, `rot[24]`) -> `Selector72` (the ALU's result/zero choice) ->
  `int_unit.Selector37` (4 levels: the int unit's per-unit `res_zero`/`res_neg` choice) ->
  `int_unit.cr_out[2]` (EQ) -> `cr~43/44` -> `cr[18]`. That is a record-form shift/rotate by
  a register amount (`slw.`/`srw.`/`sraw.`/`rlwnm.`) whose rB comes forwarded. The int unit
  already finds zero per unit before the result's choice (`DSPPC603_int_unit.sv:157-192`,
  `DSPPC603_alu.sv` `zero`/`neg`); the time is the forward mux, the shifter and the two
  choice levels. Candidate fixes, cheapest first:
  (a) make the register-amount record forms (rot_op SLW/SRW/SRAW/RLWNM with Rc) take a second
      EX cycle: CR0 from the registered result (rare instructions, negligible cost);
  (b) flatten the zero/neg choice: one mux over every unit's flags selected by a decode
      registered in ID, instead of the ALU's `Selector72` then the int unit's case;
  (c) commit CR0 of all record forms a stage later (from `mem_result`), forwarding CR0 to a
      dependent branch: broadest, but touches the branch path; only if (a)+(b) are not enough.
  Check what else lands in `cr` with `syn/check.py core --cpu 603 --mhz 66.667 --report-only
  --to "*cpu|cr[*"` (cell by cell into CR; run it under `flock /tmp/quartus.lock`; a run was
  stopped at the hand-off, nothing was learned from it).

- **Changes 2-6 (afternoon, 2026-10-24)**, each `run_core.py` PASS on the Mac (a run takes ~21 s;
  PASS = `RESULT: PASS`, 82 `pass` lines, no `fail`) and each fitted alone from a detached
  worktree (`git worktree add --detach <scratchpad>/wt_x <commit>`, then check.py from there,
  so the next edit does not leak into a queued fit). The fitter's noise is about ±0.6 ns on a
  family's slack between seeds: judge a change by the path's structure (cell by cell), not by
  one number. Fmax (slow 100 C) went 58.30 -> 60.85 (1) -> 61.60 (2) -> 61.60 (3) -> 63.73 (4).
  - **2 (8a48ab9)** CR0 flat: `int_cr_flat` from each operation's own result chosen by the
    registered `ex_rs` (bit 14 added: a compare), replacing the ALU's `Selector72` and the int
    unit's `Selector37`; `int_cr` kept for a `$fatal` check. Fit c (`check66_core_c.txt`):
    worst -1.233, the CR family gone (-0.449); new worst the FPU's rounding into the
    completion queue's RAM (`den_q`/`k_q -> completion_queue.value`, 1,700 paths: k_q + up ->
    the denormal shift -> e_res -> the range compare -> rnd_result -> fprf's zero class ->
    the RAM's data).
  - **3 (d09267a)** `seq_miss` registered in ID (`ex_seq_miss_q <= id_pred != id_pc+4/8`): the
    32-bit compare was in `ex_fp_elig -> completion_push_ex -> ex_done -> ex_leave` (fan-out
    146; the `Add29 -> d_cached_page`/`fa_mem` families were really this: Add29 = ex_pc+4).
    Fit d: worst -1.235 `ex_dec.frb -> completion_queue RAM` (= `cq_fpr_o[frb]` 32:1 mux ->
    `ex_stall_ops` -> the FPU's simple `resp_valid` -> `ex_done` -> `ex_leave` -> `redir`
    (fan-out 61) -> `completion_head`'s reset -> the RAM's address register).
  - **4 (e8cb621)** the fetch's translation registered in the MMU: `ixl_q <= translate(i_page_q
    ...)`, `ixl_valid_q` (the segment register was the page's, no BAT/SR/TLB/MSR[IR,PR] write at
    its edge), `i_xl_fresh = ixl_valid_q & (ixl_page_q == i_addr[31:12])` in `i_ready`; with
    translation off `ixl` is forced ok. A fetch into a page other than the one translated
    costs one more cycle (one bubble per sequential page crossing too). `$fatal` check against
    the fetch address's own translate(). Fit e: **Fmax 63.73, worst -0.692**
    `dcache.r_addr -> ex_stall_ops`: the data cache's hit (`landed_tag_hit -> hit_w` fan-out
    143 `-> post_take -> d_rvalid -> mem_unit.resp_valid -> mem_leave`) into `wb_valid`'s D,
    which the fitter retimed forward into `ffc_wb -> ex_stall_ops` (the `wb_fden` term).
    Others: `fpu.tc_q -> completion_queue RAM` -0.601 (change 5 covers it), `landed_tag ->
    ex_stall_ops` -0.56, `wb_result -> dar` -0.51, `fq_a_mem_r -> Mux182` -0.47.
  - **5 (770651b + 2cafc33)** the FPU answers from S_DONE's registers always (`in_round = 0`;
    S_ROUND always goes to S_DONE: its early exit to S_IDLE when `resp_ready & ~no_early` lost
    the answer and hung run_core). One cycle more FP latency. Fit f: `check66_core_f.txt`.
  - **6 (0c1fecc + d5f654e)** EX's FP dependency on the queue registered: `ex_fdep[2:0]` (a, b,
    c) from `fdep_of(d, completion_push_ex, ex_leave)`: `cq_fpr_o[fr]`, the pop's clear and
    `fr == ex_dec.frd` found from registers, `redir`/`ex_leave`/the push/the pop only choosing;
    `(|ex_fdep)` in `completion_dependency`; `$fatal` check against the bitmap. (The first
    commit paired the operands' registers with the wrong flags: `'{fra, frb, frc}` indexes a
    at 0 while the flags put a at bit 2; caught by the check.) Fit g: `check66_core_g.txt`.
  - **7 (98a695f)** a shift's zero from `a` under a mask of the count (`rot_zero`: slw zero iff
    `a & (~0 >> n) == 0`, srw/sraw with `~0 << n`, sraw also `~a[31]`); `int_zero_flat` takes it.
    Fit f (change 5 alone) had the rotator path back at -1.572 (1,079 paths: rotator -> 32-bit OR
    -> the 8-term AND-OR). Fit h (7): 61.80 MHz, -1.181 `tag_mem.valid RAM -> fa_mem` (the
    cache's hit, see the hubs below); `mem_room -> fpu.rzero_q` (the FPU's handoff enable,
    `hand_now`, behind `fpu_resp_ready = mem_room & ex_order_ready`), -0.8 `mem_result -> cr`.
  - **8a (dd9d057)** the queue's live pop from the FPU's state (`resp_back = state == S_DONE`):
    the simple operation's `resp_valid` (behind `ex_stall` through its request) fed `cq_live ->
    cq_fpscr_new -> fpscr` (fit g's worst, -0.817; `fo_for_ex` already held `fo_count == 0` but
    synthesis cannot see a simple answer implies an empty FIFO). **8b (7dcbfa4)** `fwd_sel` flat:
    `fs_pop`/`fs_ex`/`fs_mem` one-hot from `mem_take`, `completion_pop`, `fwd_ex_ok`; the
    candidates' `rd_match` from registers (fit g: `decode.Equal77`/`id_insn -> fq_fa_mem` -0.8).
    Fit i: `check66_core_i.txt`.
  - **LATE_ANSWER 1 for the data cache (3431dd2, reverted 461f7c2)**: 48 run_core runs FAIL (the
    parameter is not functional with today's memory unit) and the random programs' CPI goes
    2.20 -> 2.80. Not an option.
  - **9 (35a7aec)** `mo_dep`'s compares registered (`ex_mo_match_q`, 9 bits: a/b/c/fa/fb/fc
    against the older slot's rd, a/b/c against its update rA), from matches against MEM's newer
    slot (what `mo_*` takes at `mem_take`) and the older slot's own, chosen by `mem_take` and
    `id_to_ex`; `mo_valid` and the kills live; `mem_leave` kept out of the D-cone. (In the
    fits `ex_dec.bi` is `ex_dec.ra`: BI and rA are the same instruction bits; Quartus merged
    the registers.) Fit k: `check66_core_k.txt`.
  - **10** the data cache's S_LOOK answer flat around `hit`: `ans_now = hit ? ans_hit : ans_miss`
    with both from the request's registers (`unc` holds `~hit`, so the chain was `hit -> unc ->
    post_take -> ans_now`); the cases still drive the RAM writes and the state; `ans_now_c`
    shadow + `$fatal`. Fit l: `check66_core_l.txt`.
  - Fit i (8a+8b, a bad seed): 58.02, -2.234 (633) `wb_result -> cr`: the rotator path was still
    there (`rlwnm.` needs the rotator and STA sees rotator -> OR -> CR0 whatever rot_op); also
    -2.1 `dcache.r_wide -> fpu.r_lzc.count`. Fit k (9): 61.29, -1.315 `cr -> br_taken -> redir ->
    fpu.state` (the FPU's flush three levels deep, 7 ns after redir), `-> xer` -0.5, `wb_result
    -> cr` down to -0.24. Fit l (10): 61.38, -1.291 `dcache.r_addr -> fpu.ShiftLeft1`, -1.212
    `wb_valid -> cr`. The i-report (`check66_i_to.txt`): `r_wide -> wide_hit -> mem_unit.final_q
    -> mem_payload_take -> fpu_resp_ready -> fpu.back_free -> hand_now -> lz_q/r_q` (fan-out
    166): the FPU's handoff enable behind MEM's room.
  - **11 (fe67723)** register-count record forms (`ALU_ROT & sh_reg & Rc`: slw./srw./sraw./rlwnm.)
    take a second EX cycle (`ex_rot_chk_q` from ID, `rot_held` like `slow_held`, `rot_res_q <=
    int_rot` in the first cycle, CR0's zero/sign from it in the second); the immediate forms
    take CR0 from a second rotator with SH alone (`alu.rot_imm_o`). No forwarded count reaches
    CR0. CPI unchanged (1.52/2.20). Fit m: `check66_core_m.txt`.
  - **12 (344c4a2)** FPU: the back's working registers load under `back_room = S_IDLE | S_DONE`
    (from the state alone; S_DONE answers from `fin_*` since change 5), states and `fin_*` keep
    `back_free`; the flush applied from `flush_q` a cycle late (the pipeline is empty the cycle
    after a redirect; the pipeline's `fo_count == 0` check gated by `~fpu_flush_q`). FP CPI
    unchanged (2.86). Fit n: `check66_core_n.txt`.
  - Fit m (11): 61.27, the CR/rotator families gone from the top 14; the whole top is the FPU
    handoff hub (`dcache.r_* -> final_q -> mem_room -> fpu_resp_ready -> back_free -> r_q`,
    fan-out 180). **Fit n is fit m again**: 344c4a2 carried only the pipeline's `fpu_flush_q`
    (the edit script stopped before writing the unit's file); the FPU half is **93106a5**, fit
    p (`check66_core_p.txt`). **13 (f96662b)** DAR a cycle after the alignment exception from
    `dar_ea_q <= int_sum` (hub C's `fa_mem -> dar`); fit o (`check66_core_o.txt`).
  - **Regression step 2 passed** on 344c4a2 (= changes 2-11 + 13's predecessor): `run66.sh`
    (`run5.sh` to 60 M instructions, still `--cpu-mhz 58.333`), Super Marathon lockstep against
    dingusppc **identical, RESULT: PASS**, 1.93 CPI after Cuda released the CPU.
  - Fit p (12 complete + 13): 61.34, -1.303 `wb_result -> mmu.d_state.D_FAULT/D_WREQ, d_align_q`
    (hub C: the page compare into the MMU's miss/fault transitions), -1.189 `wb_result -> cr`
    **through the immediate-count rotator**: a rotate by an instruction-field count is still a
    barrel shifter for the (late) operand. Fit o: **"Disk is full"** (/tmp is a 7.5 GB tmpfs;
    a dozen worktrees' Quartus builds filled it): remove each worktree once its fit is read;
    the watcher loops stop on `constraint 66.67` *or* `^Error`.
  - **14 (42887f9)** the immediate forms' zero/sign from the mask rotated by the count (`a &
    rotr(m, n) == 0`; srawi `~a[31] &`; rlwimi adds `b & ~m`; the sign a 32:1 choice of a):
    `alu.rot_imm_zero/neg`. Fit q: `check66_core_q.txt`.
  - **15 (f8e2439 + bc94038 + fa0df46)** MMU: a data miss or fault leaves D_IDLE a cycle after
    its lookup from a registered copy of the outcome (`d_xl_seen_q` for `~dxl.ok` only: a
    granted hit is gone the next cycle), and **a fault is granted from that copy too** (it was
    granted in the lookup cycle, so the request vanished before the deferred transition: 9
    runs failed until fa0df46). `dxl.fault` is out of `d_gnt`; the hit's `dxl.ok & dbus_gnt`
    stays. A walk or fault answer starts one cycle later. Fit r: `check66_core_r.txt`.
  - **Fit q (14): 63.38 MHz, worst -0.777, twelve negative families** (`check66_core_q.txt`):
    `wb_valid -> fb_wb -> op_b -> the MMU's compare -> dxl -> d_gnt -> mem_unit.state` (-0.78),
    `dcache.r_kind -> fpu.d_rem` (-0.70: the divider's step enable carried `back_free`),
    `wb_result -> xer` (-0.42), `id_insn -> ex_b` (-0.32), `wb_valid -> cr` (-0.20).
  - **16 (4386197)** the hit's grant from a per-entry ok bit (`d_ok_vec`, `d_ok_hit = |(match &
    ok_vec)`, checked against `dxl.ok`); the FPU divider's `d_*` not updated at the last step
    (dead: the back takes `d_quo_next`/`d_next_b`). Fit s: `check66_core_s.txt`; its run_core
    waits for the Mac's 120 M lockstep boot (`run66b.sh`, `runrep66b.txt`) of fa0df46.
  - Fit r (15): 62.01, -1.126 `wb_result -> xer`: **sraw's carry through the rotator**
    (`rot_ca = a[31] & |(rot & ~mask)`), -0.9 `ex_fa -> op_b` (unexplained; a seed artefact?).
    **Fit s (16): 63.67 MHz, worst -0.706** `id_insn -> decoder -> sequencer -> fwd_sel ->
    fq_fc_mem` (ID's decode in the forwarding selects), then -0.53 `wb_result ->
    mem_unit.state`, -0.47 `mem_unit.state -> dcache.landed_tag_hit`. 16 run_core PASS.
    **The 120 M lockstep boot (run66b, fa0df46): PASS, identical.**
  - **17** sraw's carry from a mask of the count (`a[31] & |(a & ~(~0 << n))`, `|a` for n >= 32).
    Fit t: `check66_core_t.txt`. **One fit at a time from now on (the user, 2026-10-24).**
  - **Fit t (17): 64.55 MHz, worst -0.493**, twelve families all under 0.5 ns; the top is the
    structural grant path (a forwarded operand -> EA -> the MMU's page match -> d_ok_hit -> d_gnt
    -> mem_unit.state, 14.8 ns). The per-change gains are at the seed noise now.
  - **18 (115d132) the whole core at 66.667 MHz on today's architecture**: `pll_0002.v` C66
    variant (M 16 -> VCO 800; C0 /40; C1 /12, 100 MHz through pll_cfg /8 (4/4); C2 /8 (4/4)),
    `BandaiPippin.sv` CPU_MHZ 66 / CPU_HZ 66_666_667. A measurement build (`scratch/
    build66_115d132.log`, slack in `output_files/BandaiPippin.sta.rpt`): how far the whole core
    is and which machine paths the 33 MHz bus must take out, before the split is written.
    The 420 M lockstep boot (`run66c.sh`, a4e697e) was running meanwhile.
  - **The 420 M lockstep boot (run66c, a4e697e = changes 2-17): RESULT: PASS, identical.**
  - **Build 115d132 (the whole core at 66.667, today's architecture)**: CPU clock Fmax 63.12 MHz,
    **setup -0.844 ns, TNS -23** (a few paths); memory clock +0.051; hold +0.24 everywhere;
    `scratch/BandaiPippin_115d132.rbf` (not for the board: setup fails). Only ~0.35 ns worse
    than the CPU alone (fit t -0.49). The families: `scratch/sta66_paths.txt` (quartus_sta -t
    syn/sta_cpu_paths.tcl).
  - **The whole-core families at 66.667 (115d132, `syn/sta_cpu_paths.tcl` -> `scratch/sta66_paths.txt`):
    every failing path is inside DSPPC603** (none in the machine, the memory crossing or video):
    -0.844 (59) `id_insn -> id_ra_q` (ID's decoder -> the sequencer -> `id_leave -> fetch_deliver`
    (fan-out 260) -> the GPR read-address registers' enable; 15.3 ns, 6 of them in the decoder,
    ~6 in routing), -0.82 `id_insn -> gpr_from_sequence`, -0.81 `fq_b_mem_r -> mem_result`, -0.61
    `wb_valid -> dcache.landed_word`, -0.58 `id_insn -> ex_b`, -0.51 `dcache.r_addr -> wb_result`.
    **So the 33 MHz bus split buys nothing for timing** (the machine is not on the failing
    paths; the whole core is ~0.35 ns behind the CPU alone): the recommendation is to drop it
    and judge the CPU work on whole-core builds from here (one build at a time).
  - **19 (61a9c49 + 8f39341)** ID's instruction validity registered at `fetch_deliver`
    (`id_dvalid_q <= fetch_dec.valid & ~fetch_word.isi`: a faulted fetch is the word 0, invalid;
    3 ISI runs caught the first form), out of `id_leave`. Judged on a whole-core build from
    here: `scratch/build66_8f39341.log`, families in `scratch/sta66_paths.txt` (the STA runs at
    the build's end).
  - **Build 8f39341 (19)**: Fmax 61.63, setup -1.225, TNS -66: a worse seed; the families are
    the data cache's state from the forwarded operand -> EA -> the request (`fq_b_upd_r` /
    `wb_result -> dcache.state`, 20+ families), `dcache.state -> itt_spec_h`, and
    **`Pippin_cuda.cpu_reset -> itt_spec_h`** (-1.0: the machine's reset straight into the CPU).
    Whole-core noise ~±0.4 ns between builds. Decided: **20** (a) `cpu_reset` registered on
    entry to the CPU; (b) the memory request's EA from EX's operand registers only (`ex_a +
    ex_b`), a stall while an address operand is still forwarded (1 bubble after a WB forward,
    2 after MEM's); run_core's CPI measures the cost before a build.
  - **20 (a7e0974)** `ea_sum = ex_a + ex_b` is the memory request's EA (the memory unit, the MMU's
    `d_sum_a/b`, the read-ahead), `ea_fwd` stalls an access whose address operand is forwarded;
    `Pippin_system.cpu_reset` `(* preserve, dont_retime *)`. run_core PASS; **CPI: random
    programs 2.20 -> 2.35 (+7 %), 603e vectors 1.52 -> 1.52, FP 2.86 -> 2.90.** Whole-core
    build: `scratch/build66_a7e0974.log`.
- **The three hubs** (fit e's report, `scratch/check66_e_to.txt`, cell by cell): (A) the data
  cache's `hit` (tag RAM Tco 2.5 ns + a 20-bit compare + `hit_w`, fan-out 143) `-> post_take ->
  ans_now -> d_rvalid -> mem_unit.resp_valid -> mem_leave -> wb_valid/mem_valid/mem_own_left_q`
  (13.9 ns into `wb_valid`; the fitter retimes `wb_valid` forward into `ffc_wb -> ex_stall_ops`);
  (B) `ex_stall_ops` (compares and decodes of `ex_dec`) `-> fpu resp_valid (simple) -> ex_done ->
  ex_leave` (fan-out 110) `-> redir (61) / fwd_ex_ok -> fq_*`; (C) a forwarded operand `->
  op_a/op_b -> the MMU's 12-bit low add -> d_cached_match -> dxl -> d_gnt -> mem_unit.state`
  (14.5 ns), and `-> the ALU -> cr/dar` (the load's data: `r_addr -> way_word -> rdata -> rwin ->
  wb_result`, 13.5 ns). Changes 6, 8a, 9 shorten B; 10 shortens A; C is untouched: candidates
  are DAR a cycle later (`dar <= int_sum` under `ex_leave & ex_exc` -> copy from a shadow
  register the next cycle, as mtsr does) and the memory unit's state not deciding on `d_gnt`
  in the request cycle.
- Fitter noise: the same design fits between about 61.5 and 63.7 MHz by seed; a family's
  slack moves ±0.6 ns. When the CPU alone meets 66.67 in several seeds with ~0.5 ns margin,
  go to the bus split and the whole core.

- The remaining known structure after 4: the data cache's hit decision is ~10 ns from its
  address register and feeds, the same cycle, `d_rvalid -> mem_unit.resp_valid -> mem_leave ->
  wb_valid/mem_valid/mo_*` (and `mu_gnt -> mem_unit.state`, `d_gnt`); the forwarding selects
  `fq_*` are chosen by `ex_leave`/`mem_take` (late) in `fwd_sel`; `redir` fans out to 61.

- **For the clock step** (read 2026-10-24 afternoon): `rtl/pll/pll_0002.v` is refclk 50 MHz, M = 14
  (`m_cnt_hi/lo_div` 7/7) -> VCO 700, C0 /35 (`c_cnt_hi/lo_div0` 18/17, odd duty) = 20 MHz, C1
  /12 (6/6; 70: 5/5; 100: 4/3 odd) = the CPU, C2 /7 (4/3 odd) = 100 MHz. For 66.67: M = 16
  (8/8) -> VCO 800, C0 /40 (20/20), C1 /12 (6/6) = 66.667, C2 /8 (4/4) = 100, **a new C3 /24
  (12/12) = 33.333 for the bus** (`number_of_clocks` 4; `rtl/pll.v` exports it; the SDC gets the
  clock); `pll_cfg`'s run-time 100 MHz (`BandaiPippin.sv:222`, `cfg_data`) rewrites C1 to /8.
  The device-bus cut in `Pippin_machine.sv:476-512`: the `p_*` register stage (`present`,
  `dev_take`, `dev_busy`, `dev_ack`, `dev_cnt`) is the boundary; the tick dividers
  (`snd_d`, `us_d`, `scsi_d`, `rtxc_d`, `tb_d`, `via_d`, the VIA's `VIA_HALF`) take `CPU_HZ`:
  on the bus clock they take 33_333_333.

## Next steps (in order)

1. The CR family (fix (a) and/or (b) above). Then the data-MMU page compare from EX's address
   adder (`Add29 -> mmu.d_cached_page`, `-> fa_mem`): the effective address's adder feeding
   the TLB/BAT compare in the same cycle; then the forwarded operands into the memory unit's
   state (`fb_mem`/`mem_result -> mem_unit.state.S_REQ1/S_RSP1`); then
   `mmu.i_page_q -> pc_f`. One change at a time: lint (`make -C verilator lint`),
   `verilator/run_core.py` on the Mac (copy `~/pippin_bench/runcore66a.sh`; PASS = every
   line `pass` and `RESULT: PASS`), a CPU-alone fit (`syn/check.py core --cpu 603 --mhz
   66.667 --paths 40 --detail 1 > scratch/check66_core_<x>.txt` under the flock); record
   Fmax, worst slack and the new families in this file, commit and push each step.
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
