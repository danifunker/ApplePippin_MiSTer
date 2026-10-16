# Resume prompt: DSPPC603 software TLB reload, verified against a real 603

Paste everything below the line into a new Claude Code session started in `/Users/dani/repos/MacPPC7300_MiSTer`.

---

## Goal

Build the PowerPC 603's real TLB reload in the DSPPC603 CPU model and prove it is right by running the same test programs on a real 603 machine and comparing the results bit for bit.

The 603 has no hardware page-table walk. On a TLB miss it raises an exception and a software handler loads the TLB with `tlbld`/`tlbli`. DSPPC604 walks the hashed page table in hardware (`rtl/DSPPC604/DSPPC604_mmu.sv`). DSPPC603 must instead behave exactly like a 603: the same exceptions, SPR values, shadow registers, TLB geometry and replacement, so that the Pippin ROM's own miss handlers (and any other 603 OS's) run unmodified.

## Before you start

1. Run `git status` and `git log -5`. The author may have FPU work in progress. Do not touch `DSPPC604_fpu*`, the FPSCR or anything uncommitted. Work on a new branch (`dsppc603-tlb`). If the tree is dirty in files you need, stop and ask.
2. Read the design rules in `docs/DSPPC604_plan.md`, especially rule 6 (around line 742): "a value that differs between CPU models is a parameter; a behaviour that differs (the 603's software TLB reload) is its own module in that model's version. No `if (model == ...)` inside shared logic." Also read the README section on CPU models (`README.md:175-190`) and how the golden vectors and test wrapper work.
3. If `rtl/DSPPC603/` does not exist yet, ask the author how DSPPC603 should start: a copy of DSPPC604 or a wrapper that instantiates its modules. Don't decide that alone.

## References (local)

The research notes are in `/Users/dani/repos/ApplePippin_MiSTer/docs/`. The downloaded files are in `/Users/dani/repos/ApplePippin_MiSTer/scratch/` (git-ignored); paths below are relative to that folder:
- **Spec, primary:** `pdfs/chips/1997_MPC603EUM_MPC603e_EC603e_Users_Manual_Rev_1.pdf`. Use Chapter 5 (MMU: 603 TLB organization, the "implementation-specific table search" section, the example miss handlers), Chapter 4 (exceptions 0x1000/0x1100/0x1200, the SRR1 bit layout for them, MSR[TGPR]), Chapter 2 (the DMISS/DCMP/HASH1/HASH2/IMISS/ICMP/RPA SPRs, HID0/HID1), and the `tlbld`/`tlbli` instruction pages. Differences between the 603 and the 603e are in Appendix C. The Pippin's CPU is a **603**, not a 603e, so check every detail there.
- **Spec, architecture:** `pdfs/chips/MPCFPE32B_PowerPC_Programming_Environments_for_32-Bit_Microprocessors_Jan97.pdf` (hashed page table, PTE format, R/C bits, `tlbie`, BAT priority).
- **Reference model:** MAME `core-dev/reference-src/mame/src/devices/cpu/powerpc/` (`ppccom.cpp`, `ppc.h`, `PPCCAP_603_MMU`). See `docs/core-dev/README.md` §4 ("Remaining CPU work") for where MAME raises the 603 miss exceptions. Treat MAME as a second opinion, not the spec. Where it disagrees with the manual, note it.
- DingusPPC (`core-dev/reference-src/dingusppc/cpu/ppc/`) does **not** model this (`tlbld`/`tlbli` are no-ops). Don't copy from it.

Write down every fact you take from the manual with its page and section number in a spec file (`docs/DSPPC603_tlb_spec.md`) before writing RTL. The checklist below says what has to be pinned down. Do not trust it either; verify each item.

## Behaviour checklist (verify every item against the manual)

- **TLB geometry:** separate ITLB and DTLB, each 64 entries, 2-way set associative (32 sets), indexed by EA bits. Confirm which bits.
- **Order:** BAT match first. Then TLB lookup. A miss with translation on raises 0x1000 (instruction), 0x1100 (data load) or 0x1200 (data store). Confirm what happens when a store hits an entry whose C bit is clear: it is believed to raise 0x1200 so software can set C.
- **On the exception:**
  - SRR0, and SRR1 bits 0–3 are a copy of CR0.
  - SRR1 also carries KEY, the I/D flag, WAY (which way to replace) and S/L. Confirm the exact bit positions and how WAY is chosen (the per-set LRU).
  - MSR[TGPR] is set, so GPR0–3 refer to the shadow registers.
  - IMISS/DMISS get the missed EA. ICMP/DCMP get the compare word (V, VSID, H=0, API). HASH1/HASH2 get the primary and secondary PTEG addresses computed from SDR1.
  - Confirm every field and how the MSR is otherwise set.
- **`tlbld rB` / `tlbli rB`:** the set comes from rB, the way from SRR1[WAY], the compare word from DCMP/ICMP, and the physical word from RPA. Supervisor only. Confirm what an unprivileged use does.
- **`rfi`:** restores MSR from SRR1, which ends TGPR mode. Confirm how TGPR interacts with `mtmsr` and nested exceptions.
- **`tlbie`:** invalidates both ways of the indexed set in both TLBs. Confirm. Also `tlbsync`/`sync` on the 603.
- **Other 603 differences:**
  - HID0 bits (DOZE/NAP/SLEEP, DPM) and MSR[POW].
  - HID1 (PLL configuration, read-only, if present on the 603).
  - IABR, and the absence of DABR and the performance monitor SPRs.
  - PVR (the Pippin's exact value is unknown; read it on the real machine).
  - Cache size: 8 KB + 8 KB, 2-way.
  - `dcbz` and `dcbi` behaviour.
- **What MAME does differently**, for each item above.

## Implementation

- A separate 603 MMU module (for example `DSPPC603_mmu.sv`) with no hardware walker. Shared logic stays model-free, per rule 6.
- The TLB miss raises a precise exception through the existing exception path. Watch the pipeline cases: a miss on a fetch while an older instruction is still in flight, a miss on the second half of a misaligned access, a miss during a `dcbz`/`lmw`/`stmw` sequence, a store that hits an entry with C clear, and `tlbie` during an outstanding miss.
- Shadow GPR0–3 selected by MSR[TGPR], with no extra mux depth on the critical register-read path if it can be helped. Measure the Fmax effect, because the core is close to closing at 70 MHz.
- Add the SPRs to the known-SPR decode (today `x_spr_of`, `DSPPC604.sv` around line 1977) and add `tlbld`/`tlbli` to decode.
- Keep a parameter or build option for "hardware walk instead" so a hardware-walk build stays possible for comparison.

## Verification

1. **Unit tests in simulation**, following the repo's existing test wrapper and golden-vector style, for every checklist item, including the pipeline edge cases.
2. **Reference-model run:** run the same test programs under MAME's 603. Record where MAME and the RTL disagree and resolve each disagreement with the manual.
3. **Differential testing on real hardware (the decisive step):**
   - Write small bare-metal test programs that install their own handlers at 0x1000/0x1100/0x1200 (and at 0x300/0x400/0x700). The handlers log SRR0, SRR1, the miss SPRs, the TGPR state and the shadow-register contents into a memory buffer, then load the TLB with a known entry and return.
   - Drive access patterns that exercise each checklist item: the same set filled through both ways (to see WAY/LRU), primary and secondary hash, C-bit store, `tlbie` (then show which entries are gone by re-missing), BAT overlap, and the misaligned and string-instruction cases.
   - The same binary must run on (a) the real 603 machine, (b) the RTL in simulation, (c) the FPGA build and (d) MAME. Then diff the logs. The real machine's log is ground truth.
   - **Ask the author** which 603 machine is available (a Pippin, or a 603 Performa/Power Mac 5200/6200/5300/6300; check whether it is a 603 or 603e), how to get supervisor-mode code onto it (boot blocks, a ROM-patching path, a Linux kernel module, a Pippin boot disc via Kickstart, or a serial monitor), and how logs come back (serial port, file on disk, screen). Design the harness around that answer, and keep the test programs portable across all four targets.
4. **System test:** boot the Pippin ROM on DSPPC603 with the real miss path, count TLB-miss exceptions per second, and confirm boot behaviour matches the hardware-walk build.

## Report back with

- The spec file with page citations, and the list of places where MAME and the manual disagree.
- The test programs and the harness instructions for the real machine.
- The diff tables (real 603 vs RTL vs MAME), with every mismatch explained or fixed.
- ALM, RAM block and Fmax change against DSPPC604 at the same settings.
- Anything left open.

Commit on the branch as you go. Do not merge to main or push without asking.
