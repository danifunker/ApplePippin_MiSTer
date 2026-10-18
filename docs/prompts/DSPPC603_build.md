# Resume prompt: build DSPPC603, the Pippin's CPU, from DSPPC604

Paste everything below the line into a new Claude Code session started in
`/home/dani/repos/MacPPC7300_MiSTer` (the CPU lives there; the Pippin repo is
`/home/dani/repos/ApplePippin_MiSTer`, "the Pippin repo" below).

---

## Goal

Create `DSPPC603`: the 32-bit PowerPC 603-class CPU model for the Apple/Bandai
Pippin core, derived from the working `DSPPC604` in this repo, and prove it
against the real-hardware data recorded on 2026-10-18 from a PowerPC 603e
(Performa 6300CD). The Pippin has a plain 603 at 66 MHz; the 603e is the same
design with larger caches, so the 603e data is the reference for everything
except the handful of 603/603e differences listed below, which come from the
manual.

Work in milestones (section 6). Milestone A and B are the deliverable of this
session; C and D follow in the same order. Do not start the software TLB
reload (D) until A to C pass.

## 1. Before you start

1. `git status`, `git log -5`, `git branch -a`. The author works on the
   `fpu-pipe2` branch. On 2026-10-16 the user said to base work on the
   second-to-last commit of that day (`a53caf1`, "Docs: the
   loads-as-queue-entries enhancement written up in full"), not the tip,
   because the tip was unverified. **Ask the user which commit to base on
   now**; there may be newer verified commits. Branch from it as `dsppc603`.
   Do not touch uncommitted work; if the tree is dirty in files you need,
   stop and ask.
2. Read `README.md` (sections "CPU", "What counts as correct", "CPU models",
   and the test-bench commands), `docs/DSPPC604_plan.md` (all of "Rules that
   keep the pipeline from growing special cases", especially rule 6:
   *"Model differences are data or whole modules. A value that differs
   between CPU models (PVR, an estimate table, TLB size) is a parameter. A
   behaviour that differs (the 603's software TLB reload) is its own module
   in that model's version. No `if (model == ...)` inside shared logic."*),
   and the plan's section on CPU models (each model gets its own named
   version; files carry the model name: `DSPPC603_*`).
3. Read in the Pippin repo: `docs/implementation_plan.md` (Phases 2 and 8),
   `docs/prompts/DSPPC603_tlb_reload.md` (the reload checklist, for
   milestone D), `cputest/README.md` (how the 603e data was made and what
   differs), and `cputest/runs/results_603e_6300_run1.txt`.
4. **Ask the user** how DSPPC603 should be structured before writing RTL: a
   copy of the DSPPC604 tree (`rtl/DSPPC603/`) or a wrapper that
   instantiates DSPPC604's modules with parameters and swaps in 603
   modules. Rule 6 favours parameters plus whole modules; the shared
   execute units (`DSPPC604_fpu`, `_int_unit`, `_alu`, `_mul`, `_div`) are
   meant to be reused by name. Propose the file list and get a yes.

## 2. References

Local, all read-only:

- **The 603e User's Manual** (primary spec):
  `ApplePippin_MiSTer/scratch/pdfs/chips/1997_MPC603EUM_MPC603e_EC603e_Users_Manual_Rev_1.pdf`.
  `scratch/` is git-ignored; if it is missing, `scratch.zip` at the Pippin
  repo root unpacks to it (extract outside the repo and point at it). Use
  `pdftotext -layout` and search. Chapters: 1 (overview, 603/603e
  differences), 2 (registers: HID0, HID1, IABR, the miss SPRs), 4
  (exceptions, SRR1 layouts), 5 (MMU, TLB, the example miss handlers), 6
  (instruction timing), Appendix C (603 vs 603e). The user said: the Pippin
  is a 603, not a 603e, so check Appendix C for every item.
- **PowerPC architecture**:
  `scratch/pdfs/chips/MPCFPE32B_PowerPC_Programming_Environments_for_32-Bit_Microprocessors_Jan97.pdf`.
- **Real-hardware data** (the oracle): the Pippin repo's
  `cputest/runs/results_603e_6300_run1.csv` and `_run2.csv` (identical),
  79,624 single-instruction vectors in ppctest's results format, and the
  `.txt` summaries. The 604 reference is `ppctest/runs/results_604_run2.csv`
  here (7600) and the 7300 run named in README.md.
- **Emulator second opinions**: MAME's 603 (`~/repos/mame/src/devices/cpu/powerpc/`,
  `PPCCAP_603_MMU`), with the quirks listed in `cputest/README.md`
  (no DSI on the 603 model: every data fault is a TLB miss; `tlbie` per
  page; random way on `tlbld`; writable iff C set). DingusPPC
  (`ApplePippin_MiSTer/scratch/core-dev/reference-src/dingusppc/cpu/ppc/`)
  does not model the reload at all.
- **Supervisor-mode test programs**, already written and proven under MAME:
  `ApplePippin_MiSTer/cputest/super/super603.py` (the `tlb603` sequences,
  handlers, log format; `--groups`, `mame`). They have not yet run on real
  hardware (the 6300 needs a boot-loader route first; deferred). Their MAME
  results are `cputest/runs/sresults_603_mame_basic.csv` and
  `tlb_603_mame_*.csv`: mechanism checks, not data.

## 3. What a 603 is, against DSPPC604 (verify each in the manual, cite page)

Parameters (rule 6: data):

| Item | 604 (as built) | 603 | 603e |
|---|---|---|---|
| PVR | 0x0004xxxx | 0x0003xxxx (the Pippin's low half is unknown; MAME uses 0x00030000, QEMU 0x00030100) | 0x0006xxxx (the 6300 reported Gestalt `cput` 0106; read PVR when the supervisor run happens) |
| L1 caches | 16 KB + 16 KB, 4-way | 8 KB + 8 KB, 2-way, 32-byte lines | 16 KB + 16 KB, 4-way, 32-byte lines |
| TLBs | hardware table walk, unified reload | ITLB 64 entries 2-way + DTLB 64 entries 2-way, **software reload** (ch. 5) | same as 603 |
| Time base / DEC clock | as the 7300 machine feeds it | bus clock / 4 (16.5 MHz at 66 MHz) | same |
| Optional FP instructions | `fsqrt`/`fsqrts` present | `fsqrt`/`fsqrts` **illegal** (program exception); `fres`, `frsqrte`, `fsel`, `stfiwx` present (the estimate tables are the 603's own: compare against the golden `model-rsqrte`/`model-sweep` rows, which matched the 604 values on the 603e) | same |
| SPRs | PMCs, MMCR0/1, SIA/SDA, DABR, EAR | **none of those** (expect illegal/privileged per the manual); adds DMISS 976, DCMP 977, HASH1 978, HASH2 979, IMISS 980, ICMP 981, RPA 982, HID0 1008, HID1 1009 (read-only PLL configuration), IABR 1010 | same |
| Instructions | `tlbia` absent on both | adds `tlbld` (31/978) and `tlbli` (31/1010), supervisor-only; `tlbie`, `tlbsync`, `sync`, `eieio`, `dcbz`, `dcbi` per manual ch. 2 | same |
| MSR | | adds TGPR (bit 17, 0x20000) selecting the shadow GPR0-3; POW with HID0 DOZE/NAP/SLEEP | same |
| HID0 | 604 bit set | 603 bit set (ch. 2, table 2-x: EMCP, EBA, EBD, SBCLK, ECLK, PAR, DOZE, NAP, SLEEP, DPM, RISEG, ICE, DCE, ILOCK, DLOCK, ICFI, DCFI, FBIOB, NOOPTI); 603e adds IFEM and drops RISEG (App. C) | see left |
| Exception vectors | 604 set | adds 0x1000/0x1100/0x1200 (the TLB misses), 0x1300 (IABR), 0x1400 (SMI); no 0x0F00 performance monitor | same |

Behaviours (rule 6: whole modules in the 603 version):

- **Software TLB reload** (milestone D): the whole MMU is different; the
  checklist, SRR1 layout, shadow-register rules and the test programs are
  in `docs/prompts/DSPPC603_tlb_reload.md` (Pippin repo) and
  `cputest/super/super603.py`. Keep DSPPC604's hardware walk available as
  a build option, because the Pippin boots that way in DingusPPC.
- **Undefined integer results**, measured on the 603e (all four `divw`
  forms and all four `divwu` forms, with and without `.`/`o`): divide by
  zero returns `00000000` when the dividend has bit 31 clear and
  `FFFFFFFF` when it is set, for signed and unsigned alike;
  `0x80000000 / 0xFFFFFFFF` returns `80000000`. The 604 returns other
  values (README.md "Results the architecture leaves undefined follow the
  real chip"). Examples: `results_603e_6300_run1.csv` rows 286-308 and
  346-357 against the same rows of `results_604_run2.csv`.
- **Single-precision FP instructions with operands not representable in
  single precision** (`fmuls`, `fmadds`, `fmsubs`, `fnmadds`, `fnmsubs`,
  about 500 vectors across `dingus-fp`, `gen-fma`, `gen-fp-binary`,
  `model*`): the architecture leaves the result undefined, and the 603e
  differs from the 604. Example, row 6865: `fmuls` of 0x3FD0000000000000
  (0.25) by 0x3FD6666666666666 (0.35, not single-representable): the 604
  gives 0x3FB6666660000000 with FPSCR 82024000 (FX, XX, FI set); the 603e
  gives the same bits with FPSCR 00004000 (no inexact at all), and in
  round-toward-plus-infinity (row 6867) the 604 gives ...80000000 and the
  603e still ...60000000. Hypothesis to test against all the rows: the
  603e first converts such operands to single precision (truncating), then
  computes exactly in single, so the product of 0x3EB33333 and 0.25 is
  exact. Characterise this from the CSV before implementing it; it goes in
  a 603-specific operand stage, not in the shared FPU.
- **`stfs` of a double below the single-precision range** (83 vectors,
  `model-mem`): architecturally undefined; the 603e stores a pattern the
  model did not predict (row 0x127D5: f4 0xB690000000000000 stored as
  0xB4800000; 0x369FFFFFFFFFFFFF as 0x34FFFFFF). Derive the rule from the
  83 rows (it looks like the exponent is biased without being clamped).
- **FPSCR with exception enables set** (`model-enable`, 198 rows, FE0/FE1
  were 0 under Mac OS): the 603e's FPSCR after `fmadds.`-family operations
  differs from the software model. Compare row by row; likely the same
  single-precision operand rule plus the FEX/VX summary bits.
- Everything else (37,036 of the 37,336 vectors shared with the 604 run,
  all of `gen-carry`, `gen-rotate`, `gen-fcmp`, `gen-fsel`, `gen-fp-unary`,
  `model-rsqrte`, `model-sweep`) is identical to the 604: the shared units
  already produce it.

## 4. Test tooling

- `python verilator/run.py --csv <results.csv>`: replays a results-format
  CSV through the execute units (README.md, "Golden vectors"). Copy the
  603e CSV into `ppctest/runs/` and run it; today it will report the 855
  differences above as failures. Add a model selector so the bench
  instantiates DSPPC603's units; the goal of milestone B is zero failures
  on the 603e CSV and no regressions on the 604 CSVs with DSPPC604.
- `python verilator/run_core.py`: runs the vectors as programs through the
  whole pipeline (integer and FP halves) and the random lockstep programs
  against dingusppc. Extend its CPU choice the same way.
- The 7300 ROM boot in lockstep (README.md, "The ROM in simulation") stays
  the regression for DSPPC604; DSPPC603 has no ROM test until the Pippin
  machine exists (Pippin repo, implementation plan Phase 3).
- `cputest/ppc603test.py` (Pippin repo) decodes further hardware runs;
  `cputest/DAY1.md` describes how a run is made on the 6300.

## 5. Facts about the real machine

Performa 6300CD: 603e, Gestalt `cput` 0106, machine id 42, System 7.5.5,
no Open Firmware. Two full runs of the 79,624 vectors were byte-identical.
The supervisor-mode programs cannot run from Mac OS or from boot blocks
(both are user mode on this machine; measured 2026-10-18); the route via
Apple's MkLinux Booter is documented in `cputest/README.md` section 3 and
is deferred until milestone D needs it.

## 6. Milestones

**A. The model exists.** DSPPC603 builds and runs the same golden vectors
as DSPPC604 through the shared units, with the parameters of section 3
applied: PVR, cache geometry, the SPR set (new ones as storage, removed
ones illegal), `tlbld`/`tlbli` decoded as no-ops for now, `fsqrt`/`fsqrts`
illegal, HID0/HID1 with the 603 bit layout, IABR present, MSR[TGPR] stored,
time base at bus/4. Hardware page-table walk kept. Done when the 604
vectors still pass on DSPPC604 and the same set runs on DSPPC603.

**B. The 603e data passes bit for bit.** `run.py --csv` on
`results_603e_6300_run1.csv` reports 0 differences with DSPPC603: the
undefined divides, the single-precision operand rule, the `stfs` rule and
the enable cases implemented as 603 data or 603 modules per rule 6. Record
each rule with the rows that established it in a new
`docs/DSPPC603_notes.md`.

**C. Exceptions and SPRs per the manual.** Vectors 0x1300 and 0x1400,
SRR1 contents for each exception kind, the privileged/illegal map of the
removed SPRs and instructions. The MAME `sresults_603_mame_basic.csv`
shows the mechanism; the manual is the spec; the real-hardware run comes
later.

**D. Software TLB reload.** Follow `DSPPC603_tlb_reload.md`. Keep the
hardware-walk build; compare the two on the Pippin ROM when the machine
exists.

**E. Report.** ALM, block RAM and Fmax of DSPPC603 against DSPPC604 at the
same settings (README.md keeps such tables); Fmax must not fall below
DSPPC604's, since the Pippin needs 66 MHz.

## 7. Report back with

- The branch, the file list, and which commit it is based on.
- The 603 parameter table with manual page citations for every row.
- `docs/DSPPC603_notes.md`: the measured rules (divides, single operands,
  `stfs`, enables) with the rows behind them, and anything in the 603e data
  you could not explain.
- Bench output: 604 CSVs on DSPPC604 (unchanged), 603e CSV on DSPPC603 (0
  differences), the random programs.
- The resource and Fmax table.
- Open questions for the user, in one list.

Commit on the branch as you go. Do not merge or push without asking.

