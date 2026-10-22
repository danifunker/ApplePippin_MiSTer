# DSPPC603: what a 603 does that DSPPC604 does not

DSPPC603 (`rtl/DSPPC603/`) is the Pippin's CPU: a copy of DSPPC604 (from
MacPPC7300 21ba191 plus the little-endian patch, see
[cpu_import.md](cpu_import.md)), every file renamed `DSPPC603_*`, then
changed where a 603 differs. This file records each difference and what
established it: the manual for the documented ones, the real-hardware run
for the undefined ones.

The hardware data is `cputest/runs/results_603e_6300_run1.csv` (79,624
single-instruction vectors from a Performa 6300CD's 603e; run 2 is
byte-identical). The Pippin has a plain 603; a 603e is the same core with
larger caches and the differences of the 603e manual's Appendix C, none of
which touches the results below. Row numbers are the CSV's `index` column.

## Rules measured on the 603e

### 1. Undefined divides (132 rows)

The architecture leaves the quotient undefined for a zero divisor and for
`0x80000000 / -1`. The 603e, in all eight forms of each (`divw`, `divw.`,
`divwo`, `divwo.`, and the same for `divwu`):

| Case | 603e quotient | 604 quotient |
|---|---|---|
| `divw` by zero, dividend >= 0 | `00000000` | dividend << 4 \| `F` |
| `divw` by zero, dividend < 0 | `FFFFFFFF` | dividend << 4 \| `0` |
| `divwu` by zero, dividend < `80000000` | `00000000` | dividend << 4 \| `F` |
| `divwu` by zero, dividend >= `80000000` | **`00000001`** | dividend << 4 \| `F` |
| `divw` `80000000 / FFFFFFFF` | `80000000` | `00000001` |

That is bit 31 of the dividend, sign-extended for `divw`, zero-extended
for `divwu`; the overflow case gives the dividend back. OV and SO are set
in the `o` forms; CR0 is the signed compare of the delivered quotient (so
`divwu.` of a negative dividend by zero reports GT for the 1).

Note: the build prompt expected `FFFFFFFF` for `divwu` too; the data says
`00000001` (rows 31959, 31972, 31985, 31998, 32050 and the same five in
each of the other three `divwu` forms). Signed examples: rows 286-308 and
346-357.

Where: `DSPPC603_div.sv` (`a_lo_q` and the `too_big` quotient).

### 2. frC of a single-precision multiply is rounded to 25 bits (630 rows)

`fmuls`, `fmadds`, `fmsubs`, `fnmadds`, `fnmsubs` (with and without `.`):
when frC is not representable in single precision, the 603e's result and
FPSCR (FR, FI, XX, FX, and through them FEX and the enabled-exception
behaviour) differ from the 604 in 630 rows: 263 `fmuls`, 93 `fmadds`, 86
`fmsubs`, 99 `fnmadds`, 89 `fnmsubs`; by source `model` 209,
`model-enable` 198, `gen-fma` 132, `model-ni0` 30, `model-ni` 25,
`gen-fp-binary` 26, `dingus-fp` 10. All 198 `model-enable` rows the build
prompt listed separately are this rule; there is no separate enable rule.

**The rule.** The multiplier uses frC's significand (normalised, a
denormal frC included) rounded to 25 significant bits, a half rounded up
in magnitude: the top 25 bits plus the 26th. frA (all 53 bits) and the
addend frB (all 53 bits) are used as they are. The product and sum are
then exact and rounded once to single precision, as for any other
operation, with the FPSCR from that rounding. This is what a multiplier
that takes the top 26 bits of frC through radix-4 Booth recoding (13
digits, the 26th bit entering as the last digit's carry) does on its
single-precision pass.

**How it was found** (scripts kept outside the repository; the rule is in
`verilator/fpmodel.py`, `c_operand`):

| Hypothesis | of the 630 still differ | of the 14,010 matching rows now differ |
|---|---|---|
| none (the 604 model) | 630 | 0 |
| frA and frC truncated to single (the prompt's guess) | 2,980 (whole set) | |
| frC truncated to 24 ... 53 bits, frA any width (best: 26) | 325 | ~1 % |
| frC rounded to nearest even, 25 bits | 17 | 14 (of 1,500 sampled) |
| **frC rounded half up, 25 bits** | **0** | **0** |
| frC rounded half up, 24 or 26 bits | 176 / 299 | 640 / 80 |

The rows separating the last two rules are the 249 with frC's dropped
part exactly half (frC's low 28 bits `8000000`): e.g. row 58751 (`fmuls`
round toward minus infinity, frC `D7AFE5B348000000`) and row 58733
(`fnmsubs`, frC `60477AF8C8000000`). Rows behind the rule's shape:
6865/6867 (the prompt's example: `fmuls` 0.25 x 0.35, exact in single,
FPSCR without XX), 30495 (`fnmsubs` with frB = frC = 1 + 2^-52: the 603e
gives +2^-52, so the addend keeps all its bits while frC lost its low
ones), 41526 (`fnmadds`, round toward minus infinity).

Where: `DSPPC603_fpu.sv`, the multiply stage: frC's high partial-product
field (bits 52-27) is kept, the two products with the low field (bits
26-0) are replaced by frA shifted by 27 when bit 27 is set, else nothing.
No adder is added in front of the DSP blocks.

### 3. `stfs` below the single range (378 rows, 93 differ from the 604)

The architecture leaves `stfs` of a double whose exponent field is below
874 undefined. The 604 stores a signed zero there. The 603e:

- exponent 874 ... 896: denormalised, as the 604 (the architecture's rule);
- exponent 873 and below, a double denormal included: the bits as for a
  normal number, `WORD[0:1] = FRS[0:1]`, `WORD[2:31] = FRS[5:34]`, with a
  double denormal's exponent taken as 1 (bit `FRS[11]` read as 1). A zero
  stays a signed zero.

Examples: row 75733 (`B690000000000000` stores `B4800000`), 75734
(`369FFFFFFFFFFFFF` stores `34FFFFFF`), 75764 (double denormal
`000FFFFFFFFFFFFF` stores `00FFFFFF`), 75815 (exponent 194). All 378
`stfs`/`stfsx`/`stfsu` rows match; 93 of them differ from the 604's rule.

Where: `DSPPC603_pkg.sv`, `fp_double_to_single`; `fpmodel.double_to_single`.

### 4. Everything else

The rest of the run (the integer set, `gen-carry`, `gen-rotate`,
`gen-fcmp`, `gen-fsel`, `gen-fp-unary`, `fres`, `frsqrte`, the loads, the
other stores, the XER and FPSCR instructions) matches DSPPC604's units
and model unchanged. In particular the 603e's `fres` and `frsqrte`
estimates are the 604's (1,773 and 2,467 rows).

## Differences from the manual

Pages are the 603e User's Manual (MPC603EUM Rev. 1, 1997) page labels; TS
is the PowerPC 603 Technical Summary (1994).

| Item | DSPPC604 | DSPPC603 | Source |
|---|---|---|---|
| PVR | `00040303` | `00030100` (parameter; the Pippin's revision is unknown, 603 = version 3) | UM C-16 (C.2: "The PVR value for the 603 is 0x0003") |
| Caches | 4 ways of 128 (I: 512) sets | 2 ways of 128 sets, 8 KB each (`CACHE_WAYS`, `IC_IDXW`, `DC_IDXW`) | UM C-13 (C.1.5), C-1 (C.1) |
| HID1 | (not on the 604) | absent: mfspr/mtspr 1009 illegal | UM C-16 (C.2), C-1 |
| SPRs removed | MMCR0 952, PMC1 953, PMC2 954, SIA 955, SDA 959, DABR 1013, PIR 1023 | illegal | TS p. 15 (Figure 2) |
| SPRs added | | DMISS 976, DCMP 977, IMISS 980, ICMP 981, RPA 982 read/write; HASH1 978, HASH2 979 read-only (mtspr illegal); storage only until milestone D | UM 2-9, 2-10 (2.1.2.2-2.1.2.5) |
| HID0 | every bit kept but ICFI/DCFI | the 603's bits only (`HID0_MASK = BFF8F011`: EMCP, EBA, EBD, SBCLK, EICE, ECLK, PAR, DOZE, NAP, SLEEP, DPM, RISEG, ICE, DCE, ILOCK, DLOCK, FBIOB, NOOPTI; not the 603e's IFEM, ABE) | UM 2-8 (Table 2-2) |
| MSR | `0005FF77` (with PM) | `0007FF73`: POW, TGPR, ILE, EE ... LE, no PM; TGPR cleared by rfi and by every exception but the TLB misses | UM 4-12, 4-13 (Table 4-5), 4-17, 4-18 (Table 4-7) |
| fsqrt, fsqrts, tlbia | not decoded (illegal) | the same | UM B-1 (Table B-1), 2-18 |
| tlbld, tlbli | | decoded, supervisor-level, no-ops until milestone D | UM 2-18, A-8 (opcodes 31/978, 31/1010), A-45 (supervisor-level) |
| Time base, DEC | `tb_tick` from the machine | the same port; the Pippin machine must pulse it every 4 bus clocks | UM 2-5, 2-7, 1-15 |
| Exception vectors 0x1000-0x1400 | | milestone C | UM 4-4, 4-5 (Exceptions and Conditions) |
| Alignment: a string operation crossing 4 KB | not word-aligned and crossing 4 KB (or 256 MB): alignment exception (604 UM 2.3.4.3) | none: performed in pieces, a DSI on the second page restarts it (2026-10-18; Super Marathon's boot diverged from dingusppc at 773 M instructions on the 68K emulator's `stswx` of 20 bytes at 003ABFEE) | UM 2-31 (2.3.4.3.6), 4-26 (4.5.6), 4-28 (4.5.6.1.1) |
| Alignment: a plain load or store crossing a page under page translation | none (the 604 crosses in hardware) | **since 2026-10-22 (`CROSS_ALIGN = 1`)**: an alignment exception for MSR[DR] = 1 and no BAT hit when a halfword's EA ends in FFF, a word's in FFD-FFF, a double's (word-aligned here) in FFC; decided in MEM by the MMU from the memory unit's `dbus_cross` (the first word, not a string's) and the translation's new `bat` bit, before any byte moves; DAR the EA, DSISR as the other alignment cases. Through a BAT, with translation off, lmw/stmw and the strings: in pieces as before. dingusppc does not take it: the machine bench hands it to the reference as dcbz's (`core_main.cpp`); `mmutest` checks it | UM 4-28 (4.5.6.1.1, Table 4-14) |

Open in the manual: 4-30 names `eciwx`/`ecowx` among the unimplemented
optional instructions, but Table B-1 (B-1), the complete list, does not;
DSPPC603 keeps them as DSPPC604 has them (a DSI unless EAR[E]).

## The PVR in the Pippin's ROM

The Kinka 1.0 ROM (`disasm/kinka-1.0`, the dev ROM the same) reads PVR in
21 places: `ppc_exception_table.s` (6), `nanokernel.s` (8), `hwinit/text.s`
(2), `openfirmware/of_native.s` (7, one of them Forth's `<pvr1@>`). Every
one but two looks at the version half only: `srwi 16` then a compare with
1 (601), 3 (603), 4 (604), 6 or 7 (603e), or `andis. 0xFFFE` to set the 601
apart. The two exceptions keep the whole word as data: the NanoKernel
stores it at 0xF80 of its globals (`nanokernel.s:280`, FFF103D4) and hands
it to software from there (FFF13A3C, its emulation of a supervisor-register
read); Open Firmware's `<pvr1@>` returns it. So no ROM behaviour depends
on the revision: any `0003xxxx` boots the same; only software that prints
the revision would show a difference.

The reset code at FFF03000 sets HID0 per version; for a 603 or 603e
(FFF03048) it ORs in EMCP, ECLK, NAP, DPM, ICE and DCE (`8250C000`), every
bit inside DSPPC603's `HID0_MASK`.

## Not explained, or not measured

Each of these is assumed in DSPPC603 and has a supervisor-mode sequence in
`cputest/super/super603.py` waiting for a real 603 or 603e (the 6300 needs
the MkLinux Booter route, `cputest/README.md` section 3):

| Assumption in DSPPC603 | Sequence(s) |
|---|---|
| user-mode `mfspr 1023` (PIR, absent) is illegal, as 1009 on the 604 | `sprsweep` (every number, both modes) |
| `mfspr` 268/269 work as on the 604, in user mode too | `sprsweep`, `probe tb-user` |
| `mtspr` to HASH1/HASH2 is illegal | `q603 mtspr-hash1`, `mtspr-hash2` |
| IMISS, ICMP, DMISS, DCMP, RPA keep every bit written | `q603 mtspr-imiss`, `mtspr-icmp`; `tlb603 mtspr-dmiss`, `mtspr-rpa` |
| HID0 keeps the defined bits only (`BFF8F011`) | `q603 hid0-reserved` |
| MSR keeps `0007FF73` (no reserved bits, no PM) | `msr` (every bit), `q603 mtmsr-00010000`, `mtmsr-tgpr` |
| the revision half of PVR (no ROM behaviour depends on it, above) | `probe mfmsr` |
| `dcbz`'s alignment exception (a W or I page, or HID0[DCE] off / [DLOCK] on): DSISR as the 604's (the RT field 8); DAR the line's address on a W/I page (decided in MEM from the MMU's address) but the unaligned EA with the cache off (decided in EX). Mac OS's NanoKernel emulates `dcbz` in its handler; neither dingusppc nor MAME takes the exception | `tlb603 dcbz-wt`, `dcbz-ci` (EA 0x14 into its line) |
## How it is checked

```
python3 verilator/run.py                  # DSPPC603 against the 603e run
python3 verilator/run_core.py             # DSPPC603's pipeline tests
python3 verilator/run.py --cpu 604        # DSPPC604 against the 604 run
python3 verilator/run_core.py --cpu 604
python3 verilator/fpmodel.py --cpu 603 check   # the software model, 603 mode
```

2026-10-18, milestones A and B:

- `run.py` (DSPPC603, `results_603e_6300_run1.csv`): 11,524 integer and
  64,013 floating-point vectors pass, 132 undefined divides identical, 0
  differ. The 3,955 others (loads, stores, the XER and FPSCR
  instructions) need the pipeline and run in `run_core.py`.
- `run_core.py` (DSPPC603): PASS, 82 runs: the 603e's integer vectors as
  a program (137,332 instructions; every load and store row) with wait
  states and snoops, its floating-point vectors (758,417 instructions;
  every `stfs` row), the random FP programs against `fpmodel.py --cpu
  603`, every directed test (with the 603's SPR and `tlbld`/`tlbli` checks
  in `exctest`), 1,071,375 random instructions in lockstep with dingusppc
  3f070249 started with the 603's PVR, the overlap mixes, the clock
  crossing.
- `fpmodel.py --cpu 603 check`: 64,013 modelled, 0 differ.
- DSPPC604 unchanged: `run.py --cpu 604` 11,444 + 25,598 vectors and 132
  divides, `run_core.py --cpu 604` PASS.

The lockstep reference is dingusppc, which models neither the 603's
undefined results nor its SPR set: the random programs do not use the
removed SPRs, and undefined divides are taken from the core (as for the
604). With a 603 the reference's `rfi` is made to clear MSR[PM].

## Size and speed (milestone E, first measurement)

`python3 syn/check.py core --cpu 603|604 --mhz 66 --paths 15`: the CPU
alone (pipeline, FPU, MMU, both caches; the wrapper registers the memory
port; each top's default parameters, so `PERF = 1`, and DSPPC604's
64 KB instruction cache), Quartus 17.0 Lite, 5CSEBA6U23I7, seed 1,
2026-10-18:

| CPU | ALMs | Registers | RAM blocks | DSP | Fmax slow 100 C | Fmax slow -40 C | slack at 66 MHz |
|---|---|---|---|---|---|---|---|
| DSPPC604 | 15,594 (37 %) | 13,780 | 175 | 7 | 57.55 MHz | 58.48 MHz | -2.223 ns |
| DSPPC603 | 14,895 (36 %) | 13,365 | 107 | 7 | 60.84 MHz | 61.54 MHz | -1.284 ns |

DSPPC603 is no slower than DSPPC604 (the milestone's condition); its
smaller caches give back 68 RAM blocks and 700 ALMs. Its slowest families:
the data cache's request address into the FPU's normalising shift, the
FPSCR's commit from the FP operand fields, the instruction cache's tag RAM
into EX's operand. The frC rounding (the partial-product mux) is not among
them. The figure swings 2-3 MHz between fits; MacPPC7300 runs DSPPC604
on the board at 70 MHz with -1.3 to -2.6 ns of slack on this same model.
