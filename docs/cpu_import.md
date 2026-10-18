# The CPU imported from MacPPC7300

The Pippin core carries its own copy of the CPU, as IBMRS6K7248 does: CPU
work found here is done in this copy and sent back to MacPPC7300 as a
patch (the rule set on 2026-10-17).

| What | From | Commit |
|---|---|---|
| `rtl/DSPPC604/` (all files) | `MacPPC7300_MiSTer` `rtl/DSPPC604/` | 21ba191 (master, 2026-10-16: the fpu-pipe2 merge) |
| `verilator/` Makefile, run.py, run_core.py, vector_dut.sv, sim_main.cpp, core_main.cpp, cdc_main.cpp, fpmodel.py, progs.py, perf.py, ref/ | `MacPPC7300_MiSTer` `verilator/` | 21ba191 |
| `ppctest/runs/results_604_run2.csv` (the 7600's 604 run; run1 is byte-identical and not copied) | `MacPPC7300_MiSTer` `ppctest/runs/` | 21ba191 |

Patches applied on top, in order:

1. `0001-DSPPC604-little-endian-mode.patch` from IBMRS6K7248
   (`docs/cpu_patches/` there; `LE_MODE` parameter, default 0).

`rtl/DSPPC603/` is a copy of `rtl/DSPPC604/` after those patches, every
file and module renamed `DSPPC603_*`, then changed for the 603: see
[DSPPC603_notes.md](DSPPC603_notes.md).

The import was checked before anything changed: `verilator/run.py` on
`results_604_run2.csv`, 11,444 integer and 25,598 floating-point vectors,
all pass; 132 undefined divides identical to the 604.
