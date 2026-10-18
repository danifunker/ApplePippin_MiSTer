# Changes that could go back into MacPPC7300

The Pippin core carries its own copy of MacPPC7300's CPU, machine and benches
([cpu_import.md](cpu_import.md): imported at MacPPC7300 21ba191). This file
tracks every change made here that MacPPC7300 might want too. **Nothing here
has been applied to MacPPC7300**: the user decides, item by item.

Each entry gives where it is in this repository (the commit), what it fixes or
adds, whether it applies to MacPPC7300 as it is, and how it was checked.
Newest last.

## Status at a glance

| # | Item | Kind | Applies to MacPPC7300? |
|---|---|---|---|
| 1 | Little-endian mode (IBMRS6K7248's patch 0001) | CPU feature | Yes; its own resume prompt exists there (`RESUME_le_mode.md`, untracked) |
| 2 | The user LED's flicker | top level | Yes, the same one line |
| 3 | Verilator 5.028: `SYMRSVDWORD` on DSPPC604.sv's `set` | bench build | Yes, on the Linux machine (Verilator 5.028) |
| 4 | Verilator builds at `-j 3`, not `-j 0` | bench build | Yes, on the 14 GB Linux machine |
| 5 | The vector bench fails on a differing undefined divide | bench | Optional |
| 6 | The lockstep bench: SPR set per CPU model; stores to the ROM | bench | Optional (no 7300 ROM path hits them) |
| 7 | The lockstep reference: RAM in pieces, its own RAM for video memory | bench | Latent in MacPPC7300 (see the note) |
| 8 | `Pippin_nvsave`'s image size a parameter | machine | Optional (only the 8 KB NVRAM there) |
| 9 | Bench scripts' Windows paths and cache directories | bench | Yes, for the Linux machine |
| 10 | The L2 cache | (none made) | See the note |
| 11 | Quartus 17: a net declared with a typedef | (603 only) | No: only in DSPPC603's changed cache |
| 12 | The lockstep bench: `dcbz`'s alignment exception handed to the reference | bench | Latent (no divergence seen there) |
| 13 | ppctest's supervisor PTEs: WIMG shifted twice (`super603.py`'s copy fixed) | test generator | Check MacPPC7300's own PTE helpers |

## The items

### 1. Little-endian mode (MSR[LE]) for DSPPC604

- Here: commit 1a45083, `docs/cpu_patches/0001-DSPPC604-little-endian-mode.patch`
  applied unchanged to `rtl/DSPPC604/DSPPC604.sv`, and carried into DSPPC603.
- What: IBMRS6K7248's patch, behind `LE_MODE` (default 0: the CPU exactly as
  before, MSR[LE] kept and ignored). With `LE_MODE = 1`, the 604's address
  munging and its alignment exceptions in LE mode.
- MacPPC7300: it applies cleanly to 21ba191 (checked here). MacPPC7300's
  checkout already has `RESUME_le_mode.md` (untracked) with the procedure.
- Checked here: `run.py --cpu 604` (11,444 + 25,598 vectors, 132 divides) and
  `run_core.py --cpu 604` (82 runs, 1,071,506 random instructions in
  lockstep): PASS, the cycle counts as before the patch.

### 2. The user LED flickers at about 35 Hz

- Here: commit 5bba4ad (`ApplePippin.sv`, "THE LED").
- What: `MacPPC7300.sv` drives `LED_USER` from `retired[20]`, bit 20 of the
  instructions retired: the CPU's heartbeat, a toggle every 2^20
  instructions, about 35 times a second at 70 MHz ("the LEDs going wild",
  the user, 2026-10-18). Here it follows the disk LED instead:
  `wire led_user = disk_led_s[1];`, dark unless a block is moving.
- MacPPC7300: the same one line in `MacPPC7300.sv` (the `retired` counter
  can stay: nothing else uses it, Quartus removes it).
- Checked: Quartus Analysis & Synthesis here; not yet on the board.

### 3. Verilator 5.028 refuses DSPPC604.sv's `logic [31:0] set`

- Here: commit 112b3b1 (`verilator/Makefile`: `-Wno-SYMRSVDWORD` in `WARN`).
- What: Verilator 5.028 (the Linux machine's) flags the symbol `set` as a C++
  reserved word and stops the pipeline bench's build; 5.020 accepted it.
  IBMRS6K7248 suppressed it the same way.
- MacPPC7300: needed to build `core_tb` and `machine_tb` on the Linux
  machine. (Renaming the signal in DSPPC604.sv would also do.)

### 4. Verilator's parallel C++ compiles ran the machine out of memory

- Here: commit 5887106 (`verilator/Makefile`: `VJOBS ?= 3`, `--build -j $(VJOBS)`).
- What: `-j 0` compiles on every core; each of the machine model's C++ files
  takes about 2 GB, and next to a Quartus fit the 14 GB Linux machine ran
  out of memory and rebooted (2026-10-18 13:31).
- MacPPC7300: the same Makefile line, if it is built on that machine.

### 5. The vector bench ignores a differing undefined divide

- Here: commit 112b3b1 (`verilator/sim_main.cpp`: `bad` includes `undef.fail`).
- What: `run.py` reported undefined divides apart and did not fail on them;
  here a difference fails the run (DSPPC603 had to match the 603e's).
- MacPPC7300: optional (DSPPC604 matches all 132 today).

### 6. The lockstep bench: the SPRs the CPU has; stores to the ROM

- Here: commits eae51f3 and 3b13aa2 (`verilator/core_main.cpp`).
- What: (a) the list of SPRs for which the bench makes dingusppc take the
  core's program exception is now per CPU model (`CPU_MODEL`; the 604's list
  unchanged); (b) a store to the ROM's range is not recorded as a device
  access (the Pippin's ROM stores to FFF00000 as it starts; dingusppc drops
  it, and the bench's device queue went out of step).
- MacPPC7300: (b) is harmless there and protects against a ROM that does
  the same; (a) changes nothing for the 604.

### 7. The lockstep reference's memory: in pieces, and video memory as RAM

- Here: commits 3b13aa2 and 93f1c08 (`verilator/ref/dingus_ref.{h,cpp}`:
  `ref_init_map`, `ref_add_ram`, `ref_add_mirror`, `ref_add_ram_own`;
  `core_main.cpp`).
- What: the reference could only have one RAM region at 0, everything else
  being device space answered with the core's values. The Pippin needed
  Aspen's banks and mirror windows, and its video memory as RAM: Mac OS
  keeps data in the Pippin's VRAM through the data cache, and the core's
  cached device lines that the bench replays to the reference went stale
  once the cache wrote into them (a divergence at 23,171,064 instructions,
  `lbzx` of F00A0AFC).
- MacPPC7300: latent. Control's VRAM is device space to the reference
  there too; Mac OS on the 7300 maps it cache-inhibited (no divergence in
  450 million instructions), but a program that caches it would hit the
  same fault. `ref_add_ram_own(0x90000000, 4 MB)` (the VRAM window) would
  close it.

### 8. The NVRAM saver's image size

- Here: commit 93f1c08 (`rtl/machine/Pippin_nvsave.sv`: `ABITS`, 13 by
  default, 17 for the Pippin's 128 KB flash).
- MacPPC7300: optional; with the default the module is unchanged.

### 9. The bench scripts' paths

- Here: commits 112b3b1 and 915c833.
- What: `run.py` and `run_core.py` lost their WSL branches here and take
  `--cpu`; builds go to `~/.cache/applepippin/`; `verilator/ref/Makefile`
  and `verilator/machref/Makefile` default to the Linux checkout of
  dingusppc (`~/.cache/applepippin/dingusppc`, 3f070249, cloned from
  github.com/dingusdev/dingusppc) instead of `/mnt/c/Temp/mistercore/...`.
- MacPPC7300: if it is built on the Linux machine, its scripts need the same
  (`DINGUS=` and the build directory); the `--cpu` option is the Pippin's.

### 10. The L2 cache

- No change was made to `MacPPC7300_l2` here. The Pippin has no L2 (its top
  sets `L2_KB = 0`, MacPPC7300's own option, which builds none).
- MacPPC7300's open L2 item is its own: the timing path of the data cache's
  write-back into the L2's write register (its `RESUME_speed.md`, item 1).
- (If "the L2" meant something else, it belongs here once named.)

### 11. Quartus 17 and `wire <typedef> name = ...`

- Here: commit 111f673 (`rtl/DSPPC603/DSPPC603_cache.sv`).
- What: Quartus 17.0 refuses a net declared with a typedef type
  (`wire way_t wsel = ...`); a variable and an `assign` instead. The line
  exists only in DSPPC603's cache (its ways a parameter); DSPPC604's cache
  has `wire [1:0] wsel`.
- MacPPC7300: nothing to do.

### 12. The lockstep bench and `dcbz`'s alignment exception

- Here: `verilator/core_main.cpp` (machine bench), 2026-10-18.
- What: the core takes an alignment exception at `dcbz` on a write-through
  or cache-inhibited page, or with the data cache off (the 603e's and the
  604's rule); dingusppc zeroes the line instead. Super Marathon's boot
  diverged there at 735,041,248 instructions (`dcbz` at FFD6B770, a ROM
  block move). The bench now makes the reference take the exception with
  the core's SRR1, DAR and DSISR, as it already does for the cache
  instructions' DSIs.
- MacPPC7300: latent; Mac OS on the 7300 has not hit it in its runs. The
  block is under `PIPPIN_MACHINE` here (it reads the machine's CPU
  signals); MacPPC7300's machine bench would need its own hierarchy names.

### 13. The supervisor tier's PTEs set R instead of I

- Here: `cputest/super/super603.py`, `pte()`: `wimg` was shifted left 3
  although `PTE_I` (0x20) and the sequences' values are already the WIMG
  field in place, so "cache-inhibited" PTEs set R (0x100) with WIMG 0, and
  `guarded` (0x28) set R and W. Fixed here; the `tlb603` group's MAME run
  shows the PTEs as meant (00120022 for an I page).
- MacPPC7300: only if its own ppctest builds PTEs the same way (the helper
  here is the Pippin's; `svectors.py` there was not changed).

## Not for MacPPC7300

The 603's own changes (`rtl/DSPPC603/`: the measured undefined results, the
SPR set, the caches; [DSPPC603_notes.md](DSPPC603_notes.md)) and the Pippin's
machine (Aspen, Taos, the flash, the AppleJack, the Aspen PCI mode of
`Pippin_pcicfg`) are the Pippin's alone.
