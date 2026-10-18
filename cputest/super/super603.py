#!/usr/bin/env python3
"""Supervisor-mode CPU tests for the PowerPC 603, with no firmware underneath.

  super603.py build  [--base 0x100000] [--groups all|basic|sweep|tlb] [--out super603.bin]
  super603.py mame   [the same options] [--rompath DIR]      build, run under MAME's Pippin, decode
  super603.py decode RESULT.bin [--name NAME] [the same build options]
  super603.py list   [--groups ...]

What it is: ppctest's second stage (MacPPC7300_MiSTer/ppctest/stage2.py)
without Open Firmware. The program is a position-independent blob that is
loaded at `--base` (64 KB aligned) with the sequence records appended to it;
it is entered in supervisor mode at its first word, with translation off or
an identity mapping. It owns the exception vectors while it runs, replays
each sequence under the MSR its record names, records registers and up to
five exceptions per sequence into the record in place, and ends with a
header saying so and a branch to itself. Nothing is printed and no disk is
touched: whoever loaded it (MAME's debugger, a simulator, a boot loader)
reads the records back out of memory.

The sequences are svectors.py's (probe, spr, bat, msr, rfi, exc, lmw, and the
opcode and SPR sweeps), run on any PowerPC, plus a new `tlb603` group: the
603's software TLB reload. For those the program owns a 64 KB page table,
maps a test page through it, and installs handlers at 0x1000/0x1100/0x1200
that log IMISS/DMISS, ICMP/DCMP, HASH1/HASH2, SRR1, the shadow GPRs and the
PTE they load, reload the TLB with tlbli/tlbld, and return. A separate
512-byte log per such sequence holds what the handlers saw (layout below).

Targets: MAME's `pippin` (a 603; `mame` does it all), the MiSTer core's
Verilator bench (load the blob, run, dump), QEMU's 603 model, and the real
Performa 62xx once a way to run supervisor code there exists (README.md).
Everything that the real machine answers is the reference; the emulators
only check the mechanism.
"""

import argparse
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "..", "runs")
DEFAULT_PPCTEST = os.path.normpath(os.path.join(HERE, "..", "..", "..", "MacPPC7300_MiSTer", "ppctest"))


def load_ppctest(path):
    if not os.path.isdir(path):
        sys.exit("ppctest not found at %s (use --ppctest)" % path)
    sys.path.insert(0, path)
    import ppcasm, layout, svectors  # noqa: E401
    # this module's own names win over ppctest's (layout.py's header offsets, MAGIC)
    globals().update({k: v for k, v in vars(ppcasm).items() if not k.startswith("_") and k not in globals()})
    globals().update({k: v for k, v in vars(layout).items() if not k.startswith("_") and k not in globals()})
    globals()["svectors"] = svectors
    from svectors import SVector, lhz, tw, twi, lwarx, stwcx, dcbz, dcbi, tlbie, mftb, b_rel  # noqa
    globals().update(dict(SVector=SVector, lhz=lhz, tlbie=tlbie, dcbz=dcbz, mftb=mftb))
    from stage2 import (DSISR, DAR, DEC, SDR1, SRR0, SRR1, SPRG0, IBAT0U, DBAT0U, MMCR0, IABR, DABR,
                        mfsr, mtsr, rfi, lmw, stmw, oris, slw, and_, subfic, ba_word)
    globals().update(dict(DSISR=DSISR, DAR=DAR, DEC=DEC, SDR1=SDR1, SRR0=SRR0, SRR1=SRR1, SPRG0=SPRG0,
                          IBAT0U=IBAT0U, DBAT0U=DBAT0U, MMCR0=MMCR0, IABR=IABR, DABR=DABR,
                          mfsr=mfsr, mtsr=mtsr, rfi=rfi, lmw=lmw, stmw=stmw, oris=oris, slw=slw,
                          and_=and_, subfic=subfic, ba_word=ba_word))


# --- the program's memory, offsets from its base (64 KB aligned) ---------------
CODE_MAX = 0x6000
S_CTX = 0x6000               # LR, r1, r2, r13..r31
S_SAVE = 0x6080              # SR0..15, DBAT0-2, IBAT0-2, SPRG0-3, DEC, SDR1, MMCR0, PMC1, PMC2
SV_SR, SV_DBAT, SV_IBAT, SV_SPRG, SV_DEC, SV_SDR1, SV_PM = 0, 64, 88, 112, 128, 132, 136
S_ZERO = 0x6180
S_FLAGS, S_NEXC, S_SLOTADDR, S_ENDADDR, S_NTLB, S_MSR0 = 0x61A0, 0x61A4, 0x61A8, 0x61AC, 0x61B0, 0x61B4
S_SCRATCH = 0x6400           # 256 bytes, the first 64 recorded
S_SCRATCH_SIZE = 256
S_DRAINOUT = 0x6800
S_OUT = 0x7000               # the output record is built here, then copied over the input
S_LOWSAVE = 0x7100           # copy of LOW_SAVE_START..LOW_SAVE_END (0x2F00 bytes, to 0xA000)
PT = 0x10000                 # the page table: 64 KB, HTABMASK 0
PT_SIZE = 0x10000
PAGE_A = 0x20000             # test pages (physical), 4 KB each
PAGE_B = 0x21000
HDR = 0x22000                # the header (below)
TLBLOG = 0x23000             # N_TLB_MAX logs of TLBLOG_SIZE
TLBLOG_SIZE = 512
N_TLB_MAX = 64
RECS = 0x30000               # the sequence records, SREC each, overwritten in place
SIZE_FIXED = RECS

# header words
H_MAGIC, H_NSEQ, H_RECOFF, H_TLBOFF, H_NTLBMAX, H_DONE = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14
H_PVR, H_MSR0, H_NEXC, H_SUM, H_NRUN, H_NTLB, H_HID0, H_BASE = 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34
MAGIC = 0x53363033           # 'S603'
DONE = 0x444F4E45

# a TLB log (TLBLOG_SIZE bytes): what the 0x1000/0x1100/0x1200 handlers saw
TL_NMISS, TL_SEQ = 0x00, 0x04
TL_PTES = 0x10               # up to 5 PTEs as the page table holds them afterwards (hi, lo)
TL_PAGE = 0x50               # the first 16 words of page A afterwards
TL_ENTRY, TL_ENTRY_SIZE, TL_ENTRY_MAX = 0x100, 52, 4
# an entry: vec, srr0, srr1, miss, cmp, hash1, hash2, rpa (0: not found), pte address, tgpr0..3
TL_FIELDS = ("vec", "srr0", "srr1", "miss", "cmp", "hash1", "hash2", "rpa", "pte", "tg0", "tg1", "tg2", "tg3")

MAME_SKIP = ("eciwx",)       # MAME's 603 aborts on these instead of trapping
SF_TLB = 0x100               # a tlb603 sequence: scratch words = PTE list, page table set up
SS_TLB_NOTFOUND = 8          # status flag: a miss handler found no PTE; sequence abandoned

MSR_SAFE = 0x3030            # FP | ME | IR | DR
MSR_REAL = 0x3000
MSR_USER = MSR_SAFE | 0x4000
MSR_KEEP_OFF = 0x00050041    # POW, ILE, IP, LE
MSR_ME = 0x1000
BAT3U_BOTH = 0x1FFF          # 256 MB at 0, supervisor and user
BAT3L_CI_RW = 0x22
DBAT3U, DBAT3L, IBAT3U, IBAT3L = 542, 543, 534, 535
IMISS, ICMP, DMISS, DCMP, HASH1, HASH2, RPA = 980, 981, 976, 977, 978, 979, 982
HID0, HID1 = 1008, 1009
MMCR1, PMC1, PMC2, PMC3, PMC4 = 956, 953, 954, 957, 958

# low memory: the mailbox and the vectors, absolute addresses (RA = 0)
MB = 0x2000
MB_R3 = MB
MB_R0, MB_CR, MB_XER, MB_CTR, MB_LR, MB_SC_SRR1 = MB + 0x28, MB + 0x2C, MB + 0x30, MB + 0x34, MB + 0x38, MB + 0x3C
MB_COUNT, MB_FLAGS, MB_END, MB_RECOVER, MB_BASE = MB + 0x40, MB + 0x44, MB + 0x48, MB + 0x4C, MB + 0x50
MB_TLB, MB_TG, MB_VEC, MB_MISS, MB_CMP, MB_CTRSAVE, MB_ENTRY = (MB + 0x54, MB + 0x58, MB + 0x68, MB + 0x6C,
                                                              MB + 0x70, MB + 0x74, MB + 0x78)
MB_TLBSEQ = MB + 0x7C        # 1 while a tlb603 sequence runs (the page table is ours)
MB_EXC = MB + 0x80           # S_EXC_LIMIT records of 24 bytes
MB_SIZE = 0x100
LOW_SAVE_START, LOW_SAVE_END = 0x100, 0x3000
LOW_LINES = (LOW_SAVE_END - LOW_SAVE_START) // 32
VECTORS = list(range(0x200, 0x1800, 0x100))
TLB_VECTORS = (0x1000, 0x1100, 0x1200)
STEP_MASK = sum(1 << (v >> 8) for v in (0x300, 0x600, 0x700, 0x800, 0xA00, 0xB00, 0xE00, 0x1300))
LEAVE_MASK = (1 << 2) | (1 << 4)
SLOT_WORDS = 40

CPU_750, CPU_604, CPU_PMC34, CPU_603 = 1, 2, 4, 8
PVR_750, PVR_604, PVR_603 = (8,), (4, 9, 10), (3, 6, 7)

# the test segment and pages the tlb603 sequences use
SEG = 1                      # segment register 1: EAs 0x10000000..0x1FFFFFFF, under no BAT
VSID = 0x00123
EA_A = 0x10000000            # maps to PAGE_A (set 0 of the TLB)
EA_B = 0x10001000            # maps to PAGE_B (set 1)
EA_A2 = 0x10020000           # same TLB set as EA_A (EA bits 15-19 equal), other page
EA_A3 = 0x10040000           # a third page in that set
TEST_EAS = (EA_A, EA_B, EA_A2, EA_A3, 0x00100000)
PTE_I = 0x20                 # WIMG = cache-inhibited


# --- encoders ---------------------------------------------------------------
def tlbld(rb):               return x_form(31, 0, 0, rb, 978)
def tlbli(rb):               return x_form(31, 0, 0, rb, 1010)
def lhz_(rt, d, ra):         return d_form(40, rt, ra, d & 0xFFFF)
def sth(rs, d, ra):          return d_form(44, rs, ra, d & 0xFFFF)
def dcbst(ra, rb):           return x_form(31, 0, ra, rb, 54)
def addr(a, reg, off):
    """reg = base + off, for offsets beyond addi's reach."""
    hi, lo = (off + 0x8000) >> 16, off & 0xFFFF
    if lo >= 0x8000:
        lo -= 0x10000
    a.emit(addis(reg, 20, hi), addi(reg, reg, lo))


# --- the tlb603 sequences -----------------------------------------------------
def pte(ea, pa, h=0, wimg=PTE_I, pp=2, r=0, c=0, vsid=VSID):
    api = (ea >> 22) & 0x3F
    hi = 0x80000000 | (vsid << 7) | (h << 6) | api
    lo = (pa & 0xFFFFF000) | (r << 8) | (c << 7) | (wimg << 3) | pp
    return hi, lo


def pteg_offset(ea, h=0, vsid=VSID):
    hash_ = (vsid & 0x7FFFF) ^ ((ea >> 12) & 0xFFFF)
    if h:
        hash_ = ~hash_
    return (hash_ & 0x3FF) << 6                # HTABMASK 0: 1024 PTEGs of 64 bytes


def pte_list(base, entries):
    """Scratch words for a tlb603 sequence: count, then (offset in the page
    table, hi, lo) per PTE; entries are (ea, page_offset_from_base, way, kw)."""
    words = [len(entries)]
    for ea, page, way, kw in entries:
        h = kw.get("h", 0)
        hi, lo = pte(ea, base + page, **kw)
        words += [pteg_offset(ea, h) + 8 * way, hi, lo]
    if len(words) > 16:
        raise ValueError("too many PTEs")
    return words + [0] * (16 - len(words))


def tlb_sequences(base):
    """Each runs with SR1 = VSID set by its own first instructions."""
    vs = []
    ea = lambda reg, e: [lis(reg, e >> 16), ori(reg, reg, e & 0xFFFF)]

    def add(name, code, ptes, **kw):
        vs.append(SVector(name, "tlb603", code, flags=SF_TLB | kw.pop("flags", 0),
                          scratch=pte_list(base, ptes), **kw))

    A = [(EA_A, PAGE_A, 0, {})]
    add("null", [], A)                                   # the set-up alone: no miss expected
    add("load", ea(9, EA_A) + [lwz(3, 0, 9), lwz(4, 4, 9)], A)
    add("load-user", ea(9, EA_A) + [lwz(3, 0, 9), lwz(4, 4, 9)], A, msr=MSR_USER)
    add("store", ea(9, EA_A) + [stw(3, 8, 9), lwz(4, 8, 9)], A, r=[0x5757, 0, 0, 0, 0, 0])
    add("load-then-store", ea(9, EA_A) + [lwz(3, 0, 9), stw(3, 8, 9), lwz(4, 8, 9)], A)
    add("store-c-set", ea(9, EA_A) + [stw(3, 8, 9), lwz(4, 8, 9)], [(EA_A, PAGE_A, 0, dict(c=1))],
        r=[0x5757, 0, 0, 0, 0, 0])
    add("store-readonly", ea(9, EA_A) + [lwz(4, 0, 9), stw(3, 8, 9), lwz(5, 8, 9)],
        [(EA_A, PAGE_A, 0, dict(pp=3))], r=[0x5757, 0, 0, 0, 0, 0])
    add("load-secondary", ea(9, EA_A) + [lwz(3, 0, 9), lwz(4, 4, 9)], [(EA_A, PAGE_A, 0, dict(h=1))])
    add("load-way1", ea(9, EA_A) + [lwz(3, 0, 9), lwz(4, 4, 9)], [(EA_A, PAGE_A, 7, {})])
    add("not-found", ea(9, EA_A) + [lwz(3, 0, 9), addi(5, 5, 1)], [])
    add("wrong-vsid", ea(9, EA_A) + [lwz(3, 0, 9), addi(5, 5, 1)], [(EA_A, PAGE_A, 0, dict(vsid=VSID + 1))])
    add("two-pages", ea(9, EA_A) + ea(10, EA_B) + [lwz(3, 0, 9), lwz(4, 0, 10), lwz(5, 4, 9), lwz(6, 4, 10)],
        [(EA_A, PAGE_A, 0, {}), (EA_B, PAGE_B, 0, {})])
    # three pages in one TLB set: the third evicts one; SRR1[WAY] says which
    set3 = [(EA_A, PAGE_A, 0, {}), (EA_A2, PAGE_B, 0, {}), (EA_A3, PAGE_A, 0, {})]
    add("same-set-2", ea(9, EA_A) + ea(10, EA_A2) + [lwz(3, 0, 9), lwz(4, 0, 10), lwz(5, 4, 9), lwz(6, 4, 10)], set3)
    add("same-set-3", ea(9, EA_A) + ea(10, EA_A2) + ea(11, EA_A3)
        + [lwz(3, 0, 9), lwz(4, 0, 10), lwz(5, 0, 11), lwz(6, 4, 9), lwz(7, 4, 10), lwz(8, 4, 11)], set3)
    add("same-set-lru", ea(9, EA_A) + ea(10, EA_A2) + ea(11, EA_A3)
        + [lwz(3, 0, 9), lwz(4, 0, 10), lwz(5, 4, 9), lwz(6, 0, 11), lwz(7, 8, 9), lwz(8, 4, 10)], set3)
    add("tlbie", ea(9, EA_A) + [lwz(3, 0, 9), tlbie(9), sync(), lwz(4, 4, 9)], A)
    add("tlbie-other-set", ea(9, EA_A) + ea(10, EA_B) + [lwz(3, 0, 9), tlbie(10), sync(), lwz(4, 4, 9)], A)
    add("fetch", ea(9, EA_B) + [mtlr(9), bclr_l(), addi(5, 5, 1)], [(EA_B, PAGE_B, 0, {})])
    add("fetch-user", ea(9, EA_B) + [mtlr(9), bclr_l(), addi(5, 5, 1)], [(EA_B, PAGE_B, 0, {})], msr=MSR_USER)
    add("fetch-not-found", ea(9, EA_B) + [mtlr(9), bclr_l(), addi(5, 5, 1)], [])
    add("fetch-then-load", ea(9, EA_B) + [mtlr(9), bclr_l(), lwz(3, 4, 9)], [(EA_B, PAGE_B, 0, {})])
    add("misaligned-in-page", ea(9, EA_A) + [lwz(3, 2, 9), lhz_(4, 1, 9)], A)
    add("cross-page", ea(9, EA_A) + [lwz(3, 0xFFE, 9), lwz(4, 0xFFC, 9)],
        [(EA_A, PAGE_A, 0, {}), (EA_B, PAGE_B, 0, {})])
    add("lmw-cross", ea(9, EA_A) + [lmw(28, 0xFF8, 9), mr(3, 28), mr(4, 29), mr(5, 30), mr(6, 31)],
        [(EA_A, PAGE_A, 0, {}), (EA_B, PAGE_B, 0, {})])
    add("dcbz-cacheable", ea(9, EA_A) + [dcbz(0, 9), lwz(3, 0, 9), lwz(4, 28, 9), lwz(5, 32, 9)],
        [(EA_A, PAGE_A, 0, dict(wimg=0))])
    add("load-cacheable", ea(9, EA_A) + [lwz(3, 0, 9), stw(4, 4, 9), lwz(5, 4, 9), dcbf(0, 9), sync()],
        [(EA_A, PAGE_A, 0, dict(wimg=0))], r=[0, 0x4444, 0, 0, 0, 0])
    add("guarded", ea(9, EA_A) + [lwz(3, 0, 9), lwz(4, 4, 9)], [(EA_A, PAGE_A, 0, dict(wimg=0x28))])
    add("user-key", ea(9, EA_A) + [lwz(3, 0, 9), addi(5, 5, 1)], [(EA_A, PAGE_A, 0, dict(pp=0))], msr=MSR_USER)
    add("super-pp0", ea(9, EA_A) + [lwz(3, 0, 9), stw(3, 8, 9), lwz(4, 8, 9)], [(EA_A, PAGE_A, 0, dict(pp=0))])
    add("bat-wins", [lis(9, 0x0010), lwz(3, 0, 9), addi(5, 5, 1)], [(0x00100000, PAGE_A, 0, {})])
    add("mfspr-miss-sprs", [mfspr(3, IMISS), mfspr(4, ICMP), mfspr(5, DMISS), mfspr(6, DCMP),
                            mfspr(7, HASH1), mfspr(8, HASH2), mfspr(9, RPA)], [])
    add("mtspr-rpa", [mfspr(3, RPA), mtspr(RPA, 4), mfspr(5, RPA), mtspr(RPA, 6), mfspr(7, RPA), mtspr(RPA, 3)],
        [], r=[0, 0xFFFFFFFF, 0, 0xA5A5A5A5, 0, 0])
    add("mtspr-dmiss", [mfspr(3, DMISS), mtspr(DMISS, 4), mfspr(5, DMISS), mtspr(DCMP, 6), mfspr(7, DCMP)],
        [], r=[0, 0xFFFFFFFF, 0, 0xA5A5A5A5, 0, 0])
    add("tlbld-user", [tlbld(4), addi(5, 5, 1)], [], msr=MSR_USER)
    add("tlbli-user", [tlbli(4), addi(5, 5, 1)], [], msr=MSR_USER)
    add("hid0", [mfspr(3, HID0), mfspr(4, HID1), mfspr(5, IABR)], [])
    add("dec-tb", [mfspr(3, DEC), mftb(4, 268), mfspr(5, DEC), mftb(6, 268)] + [nop()] * 16
        + [mfspr(7, DEC), mftb(8, 268)], [])
    return vs


def bclr_l():
    return (19 << 26) | (20 << 21) | (16 << 1) | 1       # blrl


# HID0 bits the 603e manual (Table 2-2) calls reserved, or the 603e's only
# (IFEM, ABE): 1, 13-15 (15 is NHR), 22-26, 28-30. Setting or clearing them
# touches neither the caches nor the power modes.
HID0_RESERVED = 0x400703EE


def q603_sequences():
    """What DSPPC603 assumed without a measurement (docs/DSPPC603_notes.md,
    "Not explained, or not measured"); the SPR sweep and the probe group
    answer the rest (mfspr of every number in both modes, the whole PVR)."""
    vs = []

    def add(name, code, **kw):
        vs.append(SVector(name, "q603", code, **kw))

    pat = [0, 0xFFFFFFFF, 0, 0xA5A5A5A5, 0, 0]
    # the table search registers written and read back; HASH1 and HASH2 are
    # read-only in the manual: does mtspr to them trap, or do nothing?
    for spr, name in ((IMISS, "IMISS"), (ICMP, "ICMP"), (HASH1, "HASH1"), (HASH2, "HASH2")):
        add("mtspr-" + name.lower(), [mfspr(3, spr), mtspr(spr, 4), isync(), mfspr(5, spr),
                                      mtspr(spr, 6), isync(), mfspr(7, spr), mtspr(spr, 3), isync()], r=pat)
    # HID0's reserved bits: which stay set, which stay clear (r5: after
    # setting them all, r8: after clearing them all; r3 the value before)
    add("hid0-reserved", [mfspr(3, HID0), or_(4, 3, 6), sync(), mtspr(HID0, 4), isync(), mfspr(5, HID0),
                          and_(4, 3, 7), sync(), mtspr(HID0, 4), isync(), mfspr(8, HID0),
                          sync(), mtspr(HID0, 3), isync()],
        r=[0, 0, 0, HID0_RESERVED, (~HID0_RESERVED) & 0xFFFFFFFF, 0])
    # MSR[ILE] kept by mtmsr (svectors' MSR group leaves bit 15 out)
    add("mtmsr-00010000", [mfmsr(3), mtmsr(4), isync(), mfmsr(5), mtmsr(3), isync()],
        r=[0, MSR_SAFE | 0x10000, 0, 0, 0, 0])
    # MSR[TGPR] by mtmsr: kept? and does it remap GPR0-3 at once? Nothing
    # below r4 is used while it may be on (svectors' mtmsr-00020000 restores
    # the MSR from r3, which TGPR would remap: left out for this group)
    add("mtmsr-tgpr", [mfmsr(6), mtmsr(4), isync(), mfmsr(5), addi(3, 0, 0x777), addi(7, 3, 0),
                       mtmsr(6), isync()],
        r=[0x3333, MSR_SAFE | 0x20000, 0, 0, 0, 0])
    return vs


def build_set(base, groups, skip=(), skip_groups=()):
    """skip: sequence names left out (instructions an emulator aborts on)."""
    vs = []
    if groups in ("all", "basic", "sweep"):
        for v in svectors.build_set():
            if (v.group in ("sweep", "sprsweep")) != (groups == "sweep") and groups != "all":
                continue
            vs.append(v)
    if groups in ("all", "basic", "tlb"):
        vs += tlb_sequences(base)
    if groups in ("all", "basic", "q603"):
        vs += q603_sequences()
        # replaced by q603's mtmsr-tgpr: with TGPR on, a real 603 reads the
        # shadow r3 when svectors' version restores the MSR from r3
        skip = tuple(skip) + ("mtmsr-00020000",)
    return [v for v in vs if v.name not in skip and v.group not in skip_groups]


# --- the program ----------------------------------------------------------------
def build_program():
    a = Asm(base_reg=20)
    e = a.emit

    def flush_lines(start_reg, nlines, icbi_too=False):
        e(li(0, nlines), mtctr(0))
        lbl = "fl%d" % a.pos
        a.label(lbl)
        e(dcbf(0, start_reg))
        if icbi_too:
            e(icbi(0, start_reg))
        e(addi(start_reg, start_reg, 32))
        a.bdnz(lbl)
        e(sync())

    def flush_big(off, nlines, icbi_too=False):
        """flush nlines from base + off (any offset), in runs of 0x7FFF."""
        addr(a, 9, off)
        while nlines:
            n = min(nlines, 0x7FFF)
            flush_lines(9, n, icbi_too)
            nlines -= n

    # ---- entry: r20 = our base; supervisor state ours -------------------------------
    a.bl("here")
    a.label("here")
    e(mflr(20), addi(20, 20, -4))
    e(mfmsr(9), stw(9, S_MSR0, 20))
    e(li(9, MSR_REAL), mtmsr(9), isync())
    e(mr(9, 20))
    flush_lines(9, CODE_MAX // 32, icbi_too=True)
    e(isync())
    e(li(0, 0))
    for spr in (DBAT0U, DBAT0U + 2, DBAT0U + 4, DBAT3U, IBAT0U, IBAT0U + 2, IBAT0U + 4, IBAT3U):
        e(mtspr(spr, 0))
    e(isync())
    e(li(9, BAT3U_BOTH), li(10, BAT3L_CI_RW))
    e(mtspr(DBAT3L, 10), mtspr(DBAT3U, 9), mtspr(IBAT3L, 10), mtspr(IBAT3U, 9), isync())
    e(li(9, MSR_SAFE), mtmsr(9), isync())
    e(li(18, 0), li(19, 0), li(29, 0), li(0, 0))
    e(stw(0, S_FLAGS, 20), stw(0, S_NEXC, 20), stw(0, S_NTLB, 20))
    addr(a, 21, HDR)
    a.li32(0, MAGIC); e(stw(0, H_MAGIC, 21), stw(20, H_BASE, 21), li(0, 0), stw(0, H_DONE, 21))
    e(lwz(0, S_MSR0, 20), stw(0, H_MSR0, 21))

    e(mfspr(8, PVR), stw(8, H_PVR, 21), srwi(8, 8, 16), li(23, 0))
    for fam in PVR_750:
        e(cmpwi(8, fam)); a.beq("is750")
    for fam in PVR_604:
        e(cmpwi(8, fam)); a.beq("is604")
    for fam in PVR_603:
        e(cmpwi(8, fam)); a.beq("is603")
    a.b("cpu_ok")
    a.label("is750"); e(li(23, CPU_750 | CPU_PMC34)); a.b("cpu_ok")
    a.label("is603"); e(li(23, CPU_603)); a.b("cpu_ok")
    a.label("is604")
    e(li(23, CPU_604), cmpwi(8, 4))
    a.beq("cpu_ok")
    e(li(23, CPU_604 | CPU_PMC34))
    a.label("cpu_ok")
    e(mfspr(9, HID0), stw(9, H_HID0, 21))
    for i in range(16):
        e(mfsr(9, i), stw(9, S_SAVE + SV_SR + 4 * i, 20))
    for i in range(6):
        e(mfspr(9, DBAT0U + i), stw(9, S_SAVE + SV_DBAT + 4 * i, 20))
        e(mfspr(9, IBAT0U + i), stw(9, S_SAVE + SV_IBAT + 4 * i, 20))
    for i in range(4):
        e(mfspr(9, SPRG0 + i), stw(9, S_SAVE + SV_SPRG + 4 * i, 20))
    e(mfspr(9, DEC), stw(9, S_SAVE + SV_DEC, 20), mfspr(9, SDR1), stw(9, S_SAVE + SV_SDR1, 20))
    e(andi_(9, 23, CPU_604 | CPU_750))
    a.beq("no_pm_save")
    for i, spr in enumerate((MMCR0, PMC1, PMC2)):
        e(mfspr(9, spr), stw(9, S_SAVE + SV_PM + 4 * i, 20))
    a.label("no_pm_save")
    e(li(0, 0), stw(0, S_ZERO, 20), stw(0, S_ZERO + 4, 20), lfd(0, S_ZERO, 20), mtfsf(0xFF, 0))

    # ---- the sequences, in place ------------------------------------------------------
    e(lwz(22, H_NSEQ, 21))
    addr(a, 31, RECS)
    a.bl("low_prepare")
    a.label("one")
    e(cmpwi(22, 0))
    a.ble("finish")
    e(addi(30, 20, S_OUT))
    a.bl("run_one")
    e(li(9, SREC // 4), mtctr(9), mr(8, 30), mr(10, 31))
    a.label("ck")
    e(lwz(0, 0, 8), rotlwi(19, 19, 1), add(19, 19, 0), stw(0, 0, 10), addi(8, 8, 4), addi(10, 10, 4))
    a.bdnz("ck")
    e(addi(29, 29, 1), addi(31, 31, SREC), addi(22, 22, -1))
    a.b("one")

    a.label("finish")
    a.la(31, "drain_rec"); e(addi(30, 20, S_DRAINOUT))
    a.bl("run_one")
    a.bl("low_restore")
    e(stw(29, H_NRUN, 21), stw(19, H_SUM, 21), lwz(0, S_NEXC, 20), stw(0, H_NEXC, 21))
    e(lwz(0, S_NTLB, 20), stw(0, H_NTLB, 21))
    e(andi_(9, 23, CPU_604 | CPU_750))
    a.beq("no_pm_restore")
    for i, spr in enumerate((PMC1, PMC2, MMCR0)):
        e(lwz(9, S_SAVE + SV_PM + 4 * ((i + 1) % 3), 20), mtspr(spr, 9))
    a.label("no_pm_restore")
    a.li32(0, DONE); e(stw(0, H_DONE, 21), sync())
    a.label("done")
    a.b("done")

    # ---- one sequence (r31 input record, r30 output record) ---------------------------
    a.label("run_one")
    e(mflr(0), stw(0, S_CTX, 20))
    e(lwz(8, SI_FLAGS, 31), andi_(9, 8, SF_ONLY_750))
    a.beq("chk604")
    e(andi_(9, 23, CPU_750))
    a.beq("skip")
    a.label("chk604")
    e(andi_(9, 8, SF_ONLY_604))
    a.beq("run")
    e(andi_(9, 23, CPU_604))
    a.beq("skip")
    a.label("run")
    e(li(0, 0), stw(0, MB_COUNT, 0), stw(0, MB_FLAGS, 0), stw(0, MB_SC_SRR1, 0), stw(0, MB_TLB, 0))
    e(stw(0, MB_ENTRY, 0), stw(0, MB_TLBSEQ, 0))
    e(li(9, MB_EXC), li(10, S_EXC_LIMIT * 6), mtctr(10))
    a.label("mb_z")
    e(stw(0, 0, 9), addi(9, 9, 4))
    a.bdnz("mb_z")
    a.la(9, "recover"); e(stw(9, MB_RECOVER, 0), stw(20, MB_BASE, 0))
    e(lwz(10, SI_NCODE, 31), cmplwi(10, S_CODE_MAX))
    a.ble("n_code_ok")
    e(li(10, S_CODE_MAX))
    a.label("n_code_ok")
    a.la(11, "slot"); e(stw(11, S_SLOTADDR, 20), addi(12, 31, SI_CODE), cmpwi(10, 0))
    a.beq("no_code")
    e(mtctr(10))
    a.label("cp_code")
    e(lwz(0, 0, 12), stw(0, 0, 11), addi(12, 12, 4), addi(11, 11, 4))
    a.bdnz("cp_code")
    a.label("no_code")
    e(stw(11, S_ENDADDR, 20), addi(0, 11, 4), stw(0, MB_END, 0))
    a.li32(0, sc()); e(stw(0, 0, 11))
    e(subfic(9, 10, SLOT_WORDS - 1), cmpwi(9, 0))
    a.beq("filled")
    e(mtctr(9), li(12, -4))
    a.label("fill")
    e(addi(11, 11, 4), rlwinm(0, 12, 0, 6, 29), oris(0, 0, 0x4800), stw(0, 0, 11), addi(12, 12, -4))
    a.bdnz("fill")
    a.label("filled")
    a.la(9, "slot")
    flush_lines(9, SLOT_WORDS * 4 // 32 + 1, icbi_too=True)
    e(isync())
    e(addi(9, 20, S_SCRATCH), li(0, 0), li(10, S_SCRATCH_SIZE // 4), mtctr(10))
    a.label("sc_z")
    e(stw(0, 0, 9), addi(9, 9, 4))
    a.bdnz("sc_z")
    e(addi(9, 20, S_SCRATCH), addi(12, 31, SI_SCRATCH), li(10, 16), mtctr(10))
    a.label("sc_cp")
    e(lwz(0, 0, 12), stw(0, 0, 9), addi(12, 12, 4), addi(9, 9, 4))
    a.bdnz("sc_cp")
    e(addi(9, 20, S_SCRATCH))
    flush_lines(9, S_SCRATCH_SIZE // 32)
    # a tlb603 sequence: the TLBs emptied, the page table and test pages prepared
    e(lwz(8, SI_FLAGS, 31), andi_(9, 8, SF_TLB))
    a.beq("no_tlb_prep")
    a.bl("tlb_prepare")
    a.label("no_tlb_prep")
    e(stw(1, S_CTX + 4, 20), stw(2, S_CTX + 8, 20), stmw(13, S_CTX + 12, 20))
    e(lwz(0, SI_FLAGS, 31))
    e(lwz(4, SI_R3 + 4, 31), andi_(10, 0, SF_R4_SCRATCH))
    a.beq("r4_ok")
    e(addi(10, 20, S_SCRATCH), add(4, 4, 10))
    a.label("r4_ok")
    e(lwz(9, SI_CTR, 31), andi_(10, 0, SF_CTR_END))
    a.beq("ctr_ok")
    e(lwz(9, S_ENDADDR, 20))
    a.label("ctr_ok")
    e(mtctr(9), lwz(9, S_ENDADDR, 20), mtlr(9))
    e(lwz(12, SI_MSR, 31)); a.li32(10, ~MSR_KEEP_OFF & 0xFFFFFFFF)
    e(and_(12, 12, 10), ori(12, 12, MSR_ME))
    e(mtspr(SRR1, 12), lwz(9, S_ENDADDR, 20), andi_(11, 12, 0x4000))
    a.bne("enter_user")
    e(mtspr(SRR0, 9))

    def load_regs():
        e(lwz(9, SI_CR, 31), mtcrf(0xFF, 9), lwz(9, SI_XER, 31), mtxer(9))
        e(lwz(3, SI_R3, 31), lwz(5, SI_R3 + 8, 31), lwz(6, SI_R3 + 12, 31))
        e(lwz(7, SI_R3 + 16, 31), lwz(8, SI_R3 + 20, 31))
        e(mr(0, 12), li(9, 0), li(10, 0), li(11, 0), li(12, 0))

    load_regs()
    e(mtmsr(0), isync())
    while a.pos % 32:
        e(nop())
    a.label("slot")
    for _ in range(SLOT_WORDS):
        e(nop())
    a.label("enter_user")
    a.la(9, "slot"); e(mtspr(SRR0, 9))
    load_regs()
    e(rfi())

    # ---- back from the handler: real mode, nothing in the registers ---------------------
    a.label("recover")
    e(li(0, 0), mtspr(DBAT3U, 0), mtspr(IBAT3U, 0), isync())
    e(li(9, BAT3U_BOTH), li(10, BAT3L_CI_RW))
    e(mtspr(DBAT3L, 10), mtspr(DBAT3U, 9), mtspr(IBAT3L, 10), mtspr(IBAT3U, 9), isync())
    e(li(0, MSR_SAFE), mtmsr(0), isync())
    e(lwz(20, MB_BASE, 0))
    e(li(9, MB))
    flush_lines(9, MB_SIZE // 32)
    e(addi(9, 20, S_SCRATCH))
    flush_lines(9, S_SCRATCH_SIZE // 32)
    e(lwz(1, S_CTX + 4, 20), lwz(2, S_CTX + 8, 20), lmw(13, S_CTX + 12, 20))
    for i in range(16):
        e(lwz(9, S_SAVE + SV_SR + 4 * i, 20), mtsr(i, 9))
    e(isync())
    for i in range(6):
        e(lwz(9, S_SAVE + SV_DBAT + 4 * i, 20), mtspr(DBAT0U + i, 9))
        e(lwz(9, S_SAVE + SV_IBAT + 4 * i, 20), mtspr(IBAT0U + i, 9))
    e(isync())
    for i in range(4):
        e(lwz(9, S_SAVE + SV_SPRG + 4 * i, 20), mtspr(SPRG0 + i, 9))
    e(lwz(9, S_SAVE + SV_SDR1, 20), mtspr(SDR1, 9))
    a.li32(9, 0x7FFFFFFF); e(mtspr(DEC, 9))
    e(li(0, 0), mtspr(IABR, 0), mtxer(0))
    e(andi_(9, 23, CPU_604 | CPU_750))
    a.beq("no_pm_clear")
    a.li32(9, 0x80000000); e(mtspr(MMCR0, 9))
    e(mtspr(PMC1, 0), mtspr(PMC2, 0), andi_(9, 23, CPU_PMC34))
    a.beq("no_pmc34")
    e(mtspr(MMCR1, 0), mtspr(PMC3, 0), mtspr(PMC4, 0))
    a.label("no_pmc34")
    e(andi_(9, 23, CPU_750))
    a.beq("no_pm_clear")
    e(mtspr(DABR, 0))
    a.label("no_pm_clear")
    e(lfd(0, S_ZERO, 20), mtfsf(0xFF, 0))
    # the record
    e(lwz(9, MB_FLAGS, 0), lwz(10, MB_COUNT, 0), slwi(10, 10, 8), or_(9, 9, 10))
    e(ori(9, 9, SS_RAN), stw(9, SO_STATUS, 30), lwz(9, MB_SC_SRR1, 0), stw(9, SO_MSR, 30))
    e(lwz(9, MB_COUNT, 0), lwz(10, S_NEXC, 20), add(10, 10, 9), stw(10, S_NEXC, 20))
    for i in range(10):
        e(lwz(9, MB_R3 + 4 * i, 0), stw(9, SO_R3 + 4 * i, 30))
    for i in range(4):
        e(lwz(9, MB_CR + 4 * i, 0), stw(9, SO_CR + 4 * i, 30))
    for i in range(16):
        e(lwz(9, S_SCRATCH + 4 * i, 20), stw(9, SO_SCRATCH + 4 * i, 30))
    e(li(9, MB_EXC), addi(10, 30, SO_EXC), li(11, SO_EXC_MAX * SO_EXC_SIZE // 4), mtctr(11))
    a.label("cp_exc")
    e(lwz(0, 0, 9), stw(0, 0, 10), addi(9, 9, 4), addi(10, 10, 4))
    a.bdnz("cp_exc")
    e(lwz(9, S_SLOTADDR, 20), stw(9, SO_SLOT, 30), addi(9, 20, S_SCRATCH), stw(9, SO_SCRATCHADDR, 30))
    # a tlb603 sequence: the page table and page A as left, into its log
    e(lwz(8, SI_FLAGS, 31), andi_(9, 8, SF_TLB))
    a.beq("one_done")
    a.bl("tlb_after")
    a.b("one_done")
    a.label("skip")
    e(li(0, 0), mr(9, 30), li(10, SREC // 4), mtctr(10))
    a.label("sk_z")
    e(stw(0, 0, 9), addi(9, 9, 4))
    a.bdnz("sk_z")
    e(li(0, SS_SKIPPED), stw(0, SO_STATUS, 30))
    a.label("one_done")
    e(lwz(0, S_CTX, 20), mtlr(0), blr())

    # ---- tlb603: before the sequence ------------------------------------------------------
    # The TLBs are emptied (tlbie over the 32 sets), the page table zeroed and the
    # record's PTEs written into it, the test pages filled, SDR1 pointed at the
    # table, and a log claimed (MB_TLB) if any are left. Uses r0, r9-r12, CTR.
    a.label("tlb_prepare")
    e(mflr(14))
    e(li(9, 0), li(10, 32), mtctr(10))
    a.label("tp_inv")
    e(tlbie(9), addi(9, 9, 0x1000))
    a.bdnz("tp_inv")
    # (a 603 invalidates the whole set; MAME's model only the page named, so the
    # test pages are named too)
    for ea_ in TEST_EAS:
        a.li32(9, ea_); e(tlbie(9))
    e(sync())
    e(li(9, 0), ori(9, 9, VSID), mtsr(SEG, 9), isync())
    addr(a, 9, PT); e(li(0, 0), li(10, PT_SIZE // 32), mtctr(10))
    a.label("tp_z")
    for k in range(8):
        e(stw(0, 4 * k, 9))
    e(addi(9, 9, 32))
    a.bdnz("tp_z")
    addr(a, 9, PAGE_A); a.li32(10, 0xA0000000); e(li(11, 2048), mtctr(11))
    a.label("tp_fill")
    e(stw(10, 0, 9), addi(10, 10, 1), addi(9, 9, 4))
    a.bdnz("tp_fill")
    addr(a, 9, PAGE_B); a.li32(10, blr()); e(stw(10, 0, 9))     # page B begins with blr
    e(lwz(10, S_SCRATCH, 20), cmpwi(10, 0), addi(11, 20, S_SCRATCH + 4))
    a.beq("tp_no_pte")
    e(mtctr(10))
    addr(a, 12, PT)
    a.label("tp_pte")
    e(lwz(9, 0, 11), add(9, 9, 12), lwz(0, 4, 11), stw(0, 0, 9), lwz(0, 8, 11), stw(0, 4, 9), addi(11, 11, 12))
    a.bdnz("tp_pte")
    a.label("tp_no_pte")
    e(sync())
    addr(a, 9, PT); e(mtspr(SDR1, 9), isync())
    # the log
    e(lwz(10, S_NTLB, 20), cmplwi(10, N_TLB_MAX))
    a.bge("tp_nolog")
    e(mulli(9, 10, TLBLOG_SIZE))
    addr(a, 11, TLBLOG); e(add(9, 9, 11), addi(10, 10, 1), stw(10, S_NTLB, 20))
    e(mr(11, 9), li(0, 0), li(10, TLBLOG_SIZE // 4), mtctr(10))
    a.label("tp_lz")
    e(stw(0, 0, 11), addi(11, 11, 4))
    a.bdnz("tp_lz")
    e(stw(29, TL_SEQ, 9), stw(9, MB_TLB, 0))
    a.label("tp_nolog")
    e(li(0, 1), stw(0, MB_TLBSEQ, 0))
    e(sync(), mtlr(14), blr())

    # ---- tlb603: after the sequence --------------------------------------------------------
    a.label("tlb_after")
    e(mflr(14))
    flush_big(PT, PT_SIZE // 32)
    e(lwz(9, MB_TLB, 0), cmpwi(9, 0))
    a.beq("ta_done")
    e(lwz(10, S_SCRATCH, 20), cmpwi(10, 0), addi(11, 20, S_SCRATCH + 4), addi(12, 9, TL_PTES))
    a.beq("ta_no_pte")
    e(cmpwi(10, 5))
    a.ble("ta_n_ok")
    e(li(10, 5))
    a.label("ta_n_ok")
    e(mtctr(10))
    addr(a, 8, PT)
    a.label("ta_pte")
    e(lwz(10, 0, 11), add(10, 10, 8), lwz(0, 0, 10), stw(0, 0, 12), lwz(0, 4, 10), stw(0, 4, 12))
    e(addi(11, 11, 12), addi(12, 12, 8))
    a.bdnz("ta_pte")
    a.label("ta_no_pte")
    addr(a, 8, PAGE_A)
    for k in range(16):
        e(lwz(0, 4 * k, 8), stw(0, TL_PAGE + 4 * k, 9))
    a.label("ta_done")
    e(sync(), mtlr(14), blr())

    # ---- the generic exception handler: real mode, r3 = vector ------------------------------
    def flush_mailbox():
        for i in range(MB_SIZE // 32):
            e(li(4, MB + 32 * i), dcbf(0, 4))
        e(sync())

    a.label("handler")
    for n in range(4, 10):
        e(stw(n, MB_R3 + 4 * (n - 3), 0))
    e(mfcr(4), stw(4, MB_CR, 0), mfspr(5, SRR0), mfspr(6, SRR1), lwz(7, MB_END, 0))
    e(cmpwi(3, 0xC00))
    a.bne("h_exc")
    e(cmpw(5, 7))
    a.bne("h_exc")
    e(stw(6, MB_SC_SRR1, 0))
    a.b("h_dump")
    a.label("h_exc")
    e(lwz(8, MB_COUNT, 0), cmplwi(8, S_EXC_LIMIT))
    a.bge("h_abandon")
    e(mulli(9, 8, SO_EXC_SIZE), addi(9, 9, MB_EXC))
    e(stw(3, 0, 9), stw(5, 4, 9), stw(6, 8, 9))
    e(mfspr(4, DAR), stw(4, 12, 9), mfspr(4, DSISR), stw(4, 16, 9), mfmsr(4), stw(4, 20, 9))
    e(addi(8, 8, 1), stw(8, MB_COUNT, 0), cmplwi(8, S_EXC_LIMIT))
    a.bge("h_abandon")
    e(srwi(4, 3, 8), li(9, 1), slw(9, 9, 4), andi_(4, 9, LEAVE_MASK))
    a.bne("h_abandon")
    a.li32(4, STEP_MASK); e(and_(4, 9, 4, rc=1))
    a.beq("h_ret")
    e(addi(5, 5, 4))
    a.label("h_ret")
    e(mtspr(SRR0, 5))
    flush_mailbox()
    e(lwz(4, MB_CR, 0), mtcrf(0xFF, 4))
    for n in range(4, 10):
        e(lwz(n, MB_R3 + 4 * (n - 3), 0))
    e(lwz(3, MB_R3, 0), rfi())
    a.label("h_abandon")
    e(lwz(4, MB_FLAGS, 0), ori(4, 4, SS_RECOVERED), stw(4, MB_FLAGS, 0), stw(6, MB_SC_SRR1, 0))
    a.label("h_dump")
    e(stw(0, MB_R0, 0), stw(10, MB_R3 + 28, 0), stw(11, MB_R3 + 32, 0), stw(12, MB_R3 + 36, 0))
    e(mfxer(4), stw(4, MB_XER, 0), mfctr(4), stw(4, MB_CTR, 0), mflr(4), stw(4, MB_LR, 0))
    flush_mailbox()
    e(lwz(4, MB_RECOVER, 0), mtspr(SRR0, 4), li(4, MSR_REAL), mtspr(SRR1, 4), rfi())

    # ---- the 603 TLB miss handlers: real mode, MSR[TGPR] set, r0-r3 are the shadows ----------
    # Entered from a stub that saved the shadow r3 at MB_TG+12 and put the vector in
    # r3. Logs, searches the primary then the secondary PTEG as the 603 manual's
    # example handlers do, sets R (and C on a store miss) in the PTE, loads it
    # with tlbli/tlbld and returns. A miss with no PTE abandons the sequence.
    a.label("tlb_handler")
    e(stw(0, MB_TG, 0), stw(1, MB_TG + 4, 0), stw(2, MB_TG + 8, 0), stw(3, MB_VEC, 0))
    e(mfctr(0), stw(0, MB_CTRSAVE, 0))
    e(cmpwi(3, 0x1000))
    a.beq("th_i")
    e(mfspr(1, DMISS), mfspr(2, DCMP))
    a.b("th_c")
    a.label("th_i")
    e(mfspr(1, IMISS), mfspr(2, ICMP))
    a.label("th_c")
    e(stw(1, MB_MISS, 0), stw(2, MB_CMP, 0), li(0, 0), stw(0, MB_ENTRY, 0))
    # a miss outside a tlb603 sequence (a real 603: an access under no BAT; MAME:
    # also every BAT protection fault, which it never reports as a DSI) has no
    # page table of ours to search: it is recorded like any other exception,
    # with DMISS/IMISS in the DAR column and DCMP/ICMP in DSISR's, and the
    # sequence is abandoned
    e(lwz(2, MB_TLBSEQ, 0), cmpwi(2, 0))
    a.bne("th_ours")
    e(lwz(2, MB_COUNT, 0), cmplwi(2, S_EXC_LIMIT))
    a.bge("th_foreign_done")
    e(mulli(1, 2, SO_EXC_SIZE), addi(1, 1, MB_EXC))
    e(stw(3, 0, 1), mfspr(0, SRR0), stw(0, 4, 1), mfspr(0, SRR1), stw(0, 8, 1))
    e(lwz(0, MB_MISS, 0), stw(0, 12, 1), lwz(0, MB_CMP, 0), stw(0, 16, 1), mfmsr(0), stw(0, 20, 1))
    e(addi(2, 2, 1), stw(2, MB_COUNT, 0))
    a.label("th_foreign_done")
    e(lwz(0, MB_CTRSAVE, 0), mtctr(0))
    e(lwz(1, MB_FLAGS, 0), ori(1, 1, SS_RECOVERED), stw(1, MB_FLAGS, 0))
    e(mfspr(1, SRR1), stw(1, MB_SC_SRR1, 0))
    for i in range(MB_SIZE // 32):
        e(li(1, MB + 32 * i), dcbf(0, 1))
    e(sync())
    e(lwz(1, MB_RECOVER, 0), mtspr(SRR0, 1), li(1, MSR_REAL), mtspr(SRR1, 1), rfi())
    a.label("th_ours")
    e(lwz(2, MB_TLB, 0), cmpwi(2, 0))
    a.beq("th_nolog")
    e(lwz(1, TL_NMISS, 2), addi(0, 1, 1), stw(0, TL_NMISS, 2), cmplwi(1, TL_ENTRY_MAX))
    a.bge("th_nolog")
    e(mulli(1, 1, TL_ENTRY_SIZE), add(2, 2, 1), addi(2, 2, TL_ENTRY), stw(2, MB_ENTRY, 0))
    e(stw(3, 0, 2), mfspr(1, SRR0), stw(1, 4, 2), mfspr(1, SRR1), stw(1, 8, 2))
    e(lwz(1, MB_MISS, 0), stw(1, 12, 2), lwz(1, MB_CMP, 0), stw(1, 16, 2))
    e(mfspr(1, HASH1), stw(1, 20, 2), mfspr(1, HASH2), stw(1, 24, 2))
    for k in range(4):
        e(lwz(1, MB_TG + 4 * k, 0), stw(1, 36 + 4 * k, 2))
    a.label("th_nolog")
    # the search: r2 = PTE address, r3 = compare word, r1 = the word read
    e(mfspr(2, HASH1), lwz(3, MB_CMP, 0), li(0, 8), mtctr(0))
    a.label("th_l1")
    e(lwz(1, 0, 2), cmpw(1, 3))
    a.beq("th_found")
    e(addi(2, 2, 8))
    a.bdnz("th_l1")
    e(mfspr(2, HASH2), ori(3, 3, 0x40), li(0, 8), mtctr(0))
    a.label("th_l2")
    e(lwz(1, 0, 2), cmpw(1, 3))
    a.beq("th_found")
    e(addi(2, 2, 8))
    a.bdnz("th_l2")
    # not found: the sequence is abandoned (its registers are not recorded)
    e(lwz(0, MB_CTRSAVE, 0), mtctr(0))
    e(lwz(1, MB_FLAGS, 0), ori(1, 1, SS_RECOVERED | SS_TLB_NOTFOUND), stw(1, MB_FLAGS, 0))
    e(mfspr(1, SRR1), stw(1, MB_SC_SRR1, 0))
    for i in range(MB_SIZE // 32):
        e(li(1, MB + 32 * i), dcbf(0, 1))
    e(sync())
    e(lwz(1, MB_RECOVER, 0), mtspr(SRR0, 1), li(1, MSR_REAL), mtspr(SRR1, 1), rfi())
    a.label("th_found")
    e(lwz(1, 4, 2), lwz(3, MB_VEC, 0), cmpwi(3, 0x1200))
    a.bne("th_r")
    e(ori(1, 1, 0x180))                            # R and C
    a.b("th_rc")
    a.label("th_r")
    e(ori(1, 1, 0x100))                            # R
    a.label("th_rc")
    e(stw(1, 4, 2), mtspr(RPA, 1))
    e(lwz(3, MB_ENTRY, 0), cmpwi(3, 0))
    a.beq("th_nolog2")
    e(stw(1, 28, 3), stw(2, 32, 3))
    a.label("th_nolog2")
    e(lwz(0, MB_CTRSAVE, 0), mtctr(0), lwz(1, MB_MISS, 0), lwz(3, MB_VEC, 0), cmpwi(3, 0x1000))
    a.beq("th_li")
    e(tlbld(1), rfi())
    a.label("th_li")
    e(tlbli(1), rfi())

    # ---- the exception vectors: ours while the sequences run -------------------------------
    a.label("low_prepare")
    e(mflr(14), li(9, LOW_SAVE_START))
    flush_lines(9, LOW_LINES)
    e(li(9, LOW_SAVE_START), addi(10, 20, S_LOWSAVE), li(11, (LOW_SAVE_END - LOW_SAVE_START) // 4))
    e(mtctr(11))
    a.label("lp_save")
    e(lwz(0, 0, 9), stw(0, 0, 10), addi(9, 9, 4), addi(10, 10, 4))
    a.bdnz("lp_save")
    # stub: stw r3, MB_R3(0); li r3, vector; ba handler
    a.la(11, "handler"); e(rlwinm(11, 11, 0, 6, 29), oris(11, 11, 0x4800), ori(11, 11, 2))
    a.li32(12, stw(3, MB_R3, 0))
    e(li(9, VECTORS[0]), li(10, len(VECTORS)), mtctr(10))
    a.label("lp_stub")
    e(stw(12, 0, 9), addis(0, 9, 0x3860), stw(0, 4, 9), stw(11, 8, 9), addi(9, 9, 0x100))
    a.bdnz("lp_stub")
    # the TLB miss stubs: stw r3, MB_TG+12(0); li r3, vector; ba tlb_handler
    a.la(11, "tlb_handler"); e(rlwinm(11, 11, 0, 6, 29), oris(11, 11, 0x4800), ori(11, 11, 2))
    a.li32(12, stw(3, MB_TG + 12, 0))
    for v in TLB_VECTORS:
        e(li(9, v), stw(12, 0, 9), addis(0, 9, 0x3860), stw(0, 4, 9), stw(11, 8, 9))
    e(li(9, LOW_SAVE_START))
    flush_lines(9, LOW_LINES, icbi_too=True)
    e(isync(), mtlr(14), blr())

    a.label("low_restore")
    e(mflr(14), li(9, LOW_SAVE_START))
    flush_lines(9, LOW_LINES)
    e(li(9, LOW_SAVE_START), addi(10, 20, S_LOWSAVE), li(11, (LOW_SAVE_END - LOW_SAVE_START) // 4))
    e(mtctr(11))
    a.label("lr_copy")
    e(lwz(0, 0, 10), stw(0, 0, 9), addi(9, 9, 4), addi(10, 10, 4))
    a.bdnz("lr_copy")
    e(li(9, LOW_SAVE_START))
    flush_lines(9, LOW_LINES, icbi_too=True)
    e(isync(), mtlr(14), blr())

    # ---- data -------------------------------------------------------------------------------
    while a.pos % 32:
        e(nop())
    a.label("drain_rec")
    drain = [mfmsr(3), ori(4, 3, 0x8000), mtmsr(4), isync(), nop(), nop(), nop(), nop(),
             mtmsr(3), isync()]
    rec = [0] * (SREC // 4)
    rec[SI_MSR // 4], rec[SI_NCODE // 4] = MSR_SAFE, len(drain)
    rec[SI_CODE // 4:SI_CODE // 4 + len(drain)] = drain
    e(*rec)

    blob = a.assemble()
    if len(blob) > CODE_MAX:
        raise ValueError("program is %d bytes, limit %d" % (len(blob), CODE_MAX))
    global LABELS
    LABELS = dict(a.labels)
    return blob


def build_image(base, groups, skip=(), skip_groups=()):
    """The blob to load at base: program, zeroed RAM, header, logs, records."""
    vs = build_set(base, groups, skip, skip_groups)
    img = bytearray(RECS + len(vs) * SREC)
    prog = build_program()
    img[:len(prog)] = prog
    struct.pack_into(">5I", img, HDR + H_MAGIC, MAGIC, len(vs), RECS, TLBLOG, N_TLB_MAX)
    for i, v in enumerate(vs):
        img[RECS + i * SREC:RECS + (i + 1) * SREC] = v.pack()
    return bytes(img), vs, len(prog)


def tlb_seq_indexes(vs):
    return [i for i, v in enumerate(vs) if v.flags & SF_TLB]


# --- decoding ---------------------------------------------------------------------
def decode(data, vs, base, name, out_dir, verbose=True):
    import csv
    hdr = data[HDR:HDR + 0x100]
    w = lambda off: struct.unpack_from(">I", hdr, off)[0]
    if w(H_MAGIC) != MAGIC:
        sys.exit("no header at base + %X: the program did not run, or the dump is not from its base" % HDR)
    done = w(H_DONE) == DONE
    pvr, nrun, nexc, ntlb, hid0, msr0, hsum = w(H_PVR), w(H_NRUN), w(H_NEXC), w(H_NTLB), w(H_HID0), w(H_MSR0), w(H_SUM)
    status = 0
    print("--- super603 run: PVR %08X, HID0 %08X, entry MSR %08X, base %08X" % (pvr, hid0, msr0, w(H_BASE)))
    if not done:
        nrun = 0
        for i in range(len(vs)):                       # records are written in place as they run
            if struct.unpack_from(">I", data, RECS + i * SREC)[0] & 0xFF:
                nrun = i + 1
        print("    NOT FINISHED: %d of %d sequences ran; the last was #%d %s"
              % (nrun, len(vs), nrun - 1, vs[nrun - 1].name if nrun else "-"))
        if nrun < len(vs):
            print("    stuck on #%d %s (%s): %s" % (nrun, vs[nrun].name, vs[nrun].group,
                                                    " ".join("%08X" % w for w in vs[nrun].code)))
        status = 1
    else:
        print("    %d sequences ran, %d exceptions, checksum %08X, %d TLB logs" % (nrun, nexc, hsum, ntlb))
    rows, per, by_vec = [], {}, {}
    tlb_rows = []
    tlb_idx = tlb_seq_indexes(vs)
    for i, sv in enumerate(vs[:nrun]):
        rec = data[RECS + i * SREC:RECS + (i + 1) * SREC]
        inp = sv.pack()
        inp = svectors.unpack_input(inp)
        out = svectors.unpack_output(rec)
        st = per.setdefault(sv.group, [0, 0, 0, 0])
        if out["status"] & SS_SKIPPED:
            st[3] += 1
        else:
            st[0] += 1
            st[1] += out["nexc"] > 0
            st[2] += bool(out["status"] & SS_RECOVERED)
        for x in out["exc"]:
            by_vec[x["vec"]] = by_vec.get(x["vec"], 0) + 1
        row = svectors.csv_row(i, sv, inp, out)
        if out["status"] & SS_TLB_NOTFOUND:
            row[15] = "ABANDONED(no PTE)"
        rows.append(row)
    print("    %-10s %7s %7s %9s %7s" % ("group", "ran", "w/exc", "abandoned", "skipped"))
    for g, (n, x, ab, sk) in per.items():
        print("    %-10s %7d %7d %9d %7d" % (g, n, x, ab, sk))
    print("    exceptions by vector: " + ", ".join("%04X %d" % kv for kv in sorted(by_vec.items())))
    # the TLB logs
    tl_cols = (["index", "name", "nmiss"] + ["pte%d_%s" % (k, f) for k in range(5) for f in ("hi", "lo")]
               + ["pageA"] + ["m%d_%s" % (k, f) for k in range(TL_ENTRY_MAX) for f in TL_FIELDS])
    for k, i in enumerate(tlb_idx[:ntlb]):
        if i >= nrun:
            break
        log = data[TLBLOG + k * TLBLOG_SIZE:TLBLOG + (k + 1) * TLBLOG_SIZE]
        nmiss, seq = struct.unpack_from(">2I", log, 0)
        ptes = struct.unpack_from(">10I", log, TL_PTES)
        page = struct.unpack_from(">16I", log, TL_PAGE)
        row = [str(i), vs[i].name, str(nmiss)] + ["%08X" % x for x in ptes] + [" ".join("%08X" % x for x in page)]
        ents = []
        for m in range(min(nmiss, TL_ENTRY_MAX)):
            vals = struct.unpack_from(">13I", log, TL_ENTRY + m * TL_ENTRY_SIZE)
            ents.append(dict(zip(TL_FIELDS, vals)))
            row += ["%08X" % x for x in vals]
        row += [""] * (13 * (TL_ENTRY_MAX - len(ents)))
        tlb_rows.append(row)
        if verbose:
            print("  tlb603 %-18s misses %d  srr1 %s  ways %s  pte after %s" % (
                vs[i].name, nmiss, " ".join("%08X" % x["srr1"] for x in ents),
                " ".join(str((x["srr1"] >> 17) & 1) for x in ents),
                " ".join("%08X" % x for x in ptes[:2])))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "sresults_%s.csv" % name)
    with open(path, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(svectors.CSV_COLUMNS)
        wr.writerows(rows)
    print("    written %s" % path)
    if tlb_rows:
        tpath = os.path.join(out_dir, "tlb_%s.csv" % name)
        with open(tpath, "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(tl_cols)
            wr.writerows(tlb_rows)
        print("    written %s" % tpath)
    return status


# --- commands ---------------------------------------------------------------------
def cmd_build(args):
    img, vs, plen = build_image(args.base, args.groups, args.skip, args.skip_groups)
    with open(args.out, "wb") as fh:
        fh.write(img)
    groups = {}
    for v in vs:
        groups[v.group] = groups.get(v.group, 0) + 1
    print("wrote %s: load at %08X, %d bytes (program %d), %d sequences: %s" % (
        args.out, args.base, len(img), plen, len(vs), ", ".join("%s %d" % kv for kv in groups.items())))
    print("entry %08X; done when word %08X == 'DONE'; results %08X..%08X" % (
        args.base, args.base + HDR + H_DONE, args.base + HDR, args.base + len(img)))


def cmd_list(args):
    for i, v in enumerate(build_set(args.base, args.groups, args.skip, args.skip_groups)):
        print("%5d %-10s %-20s msr=%08X flags=%03X %s" % (
            i, v.group, v.name, v.msr, v.flags, " ".join("%08X" % w for w in v.code)))


def cmd_decode(args):
    vs = build_set(args.base, args.groups, args.skip, args.skip_groups)
    with open(args.result, "rb") as fh:
        data = fh.read()
    sys.exit(decode(data, vs, args.base, args.name, args.out_dir))


LUA = r"""
-- super603: load the blob into RAM, run it from its first word, dump when done
local base, size, done_addr, blob, dump = BASE, SIZE, DONE_ADDR, "BLOB", "DUMP"
local cpu = manager.machine.devices[":maincpu"]
local mem = cpu.spaces["program"]
local f = assert(io.open(blob, "rb"))
local data = f:read("a")
f:close()
local function load()
    for i = 0, #data - 4, 4 do
        mem:write_u32(base + i, (string.unpack(">I4", data, i + 1)))
    end
    print(string.format("super603: loaded %d bytes at %08X", #data, base))
end
-- the reset vector (FFF00100, ROM offset 300100) becomes an absolute branch to
-- the program, and the machine is reset once: the ROM never runs again
local rom = manager.machine.memory.regions[":bootrom"]
rom:write_u32(0x300100, 0x48000002 | base)
if not _G.super603_started then
    _G.super603_started = true
    load()
    _G.super603_sub1 = emu.add_machine_reset_notifier(load)     -- subscriptions die if collected
    manager.machine:soft_reset()
    if "TRACE" ~= "" then
        _G.super603_sub2 = emu.add_machine_reset_notifier(function()
            local ok, err = pcall(function()
                local dbg = manager.machine.debugger
                if dbg == nil then error("no debugger (needs -debug)") end
                if "TRACE_START" == "" then
                    dbg:command("trace TRACE,maincpu,noloop")
                else
                    dbg:command("bpset TRACE_START,,{trace TRACE,maincpu,noloop}")
                end
                for stop in string.gmatch("TRACE_STOP", "[^,]+") do
                    dbg:command("bpset " .. stop .. ",,{trace off}")
                end
            end)
            print("super603: tracing to TRACE: " .. tostring(ok) .. " " .. tostring(err))
        end)
    end
end
local finished = false
local function save()
    local out = assert(io.open(dump, "wb"))
    for i = 0, size - 4, 4 do
        out:write(string.pack(">I4", mem:read_u32(base + i)))
    end
    out:close()
    out = assert(io.open(dump .. ".low", "wb"))
    for i = 0, 0x3000 - 4, 4 do
        out:write(string.pack(">I4", mem:read_u32(i)))
    end
    out:close()
    print(string.format("super603: dump written; pc %08X msr %08X r20 %08X r22 %08X r29 %08X r31 %08X",
          cpu.state["PC"].value, cpu.state["MSR"].value, cpu.state["R20"].value, cpu.state["R22"].value,
          cpu.state["R29"].value, cpu.state["R31"].value))
end
local ticks = 0
local function check()
    if finished then return end
    ticks = ticks + 1
    if "TRACE_START" ~= "" and manager.machine.debugger ~= nil then
        manager.machine.debugger:command("trace off")     -- a trace started by its breakpoint lasts a frame
    end
    if ticks % 50 == 0 then
        save()
    end
    if mem:read_u32(done_addr) == 0x444F4E45 then
        finished = true
        save()
        print("super603: done")
        manager.machine:exit()
    end
end
emu.register_periodic(check)
"""


def cmd_mame(args):
    """Run the blob in MAME's Pippin (a 603 at 66 MHz) through a Lua script:
    it is written into RAM and PC set to it as the machine starts, and the
    memory is dumped when the header says DONE. The Pippin ROM runs only
    for the instant before the script takes over."""
    args.skip = tuple(args.skip) + MAME_SKIP
    img, vs, plen = build_image(args.base, args.groups, args.skip, args.skip_groups)
    tmp = tempfile.mkdtemp(prefix="super603-")
    blob = os.path.join(tmp, "super603.bin")
    dump = os.path.join(tmp, "result.bin")
    with open(blob, "wb") as fh:
        fh.write(img)
    lua = (LUA.replace("BASE", "0x%X" % args.base).replace("SIZE", "0x%X" % len(img))
           .replace("DONE_ADDR", "0x%X" % (args.base + HDR + H_DONE)).replace("BLOB", blob).replace("DUMP", dump)
           .replace("TRACE_START", "0x%X" % (args.base + LABELS[args.trace_start]) if args.trace_start else "")
           .replace("TRACE_STOP", ",".join("0x%X" % (args.base + LABELS[l]) for l in args.trace_stop.split(",")))
           .replace("TRACE", args.trace or ""))
    spath = os.path.join(tmp, "run.lua")
    with open(spath, "w") as fh:
        fh.write(lua)
    cmd = [args.mame, "pippin", "-bios", args.bios, "-rompath", args.rompath, "-autoboot_script", spath,
           "-autoboot_delay", "0", "-nothrottle", "-video", "none", "-sound", "none", "-skip_gameinfo",
           "-seconds_to_run", str(args.seconds), "-nvram_directory", tmp, "-cfg_directory", tmp]
    if args.trace:
        cmd += ["-debug", "-debugger", "none"]
    print("running: " + " ".join(cmd))
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("super603:"):
            print("  " + line)
    if not os.path.exists(dump):
        print(r.stdout[-3000:])
        sys.exit("MAME produced no dump (the program did not reach its end within %d emulated seconds)"
                 % args.seconds)
    with open(dump, "rb") as fh:
        data = fh.read()
    if args.keep:
        print("dump kept at %s" % dump)
    sys.exit(decode(data, vs, args.base, args.name or "603_mame_pippin", args.out_dir))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ppctest", default=DEFAULT_PPCTEST)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--base", type=lambda s: int(s, 0), default=0x100000, help="load address, 64 KB aligned")
        sp.add_argument("--groups", default="basic", choices=("all", "basic", "sweep", "tlb", "q603"),
                        help="basic: everything but the opcode/SPR sweeps (default)")
        sp.add_argument("--skip", default="", type=lambda s: tuple(x for x in s.split(",") if x),
                        help="sequence names to leave out, comma-separated (mame: %s)" % ",".join(MAME_SKIP))
        sp.add_argument("--skip-groups", default="", type=lambda s: tuple(x for x in s.split(",") if x),
                        help="groups to leave out, comma-separated")

    b = sub.add_parser("build"); b.set_defaults(fn=cmd_build); common(b)
    b.add_argument("--out", default=os.path.join(HERE, "super603.bin"))
    ls = sub.add_parser("list"); ls.set_defaults(fn=cmd_list); common(ls)
    d = sub.add_parser("decode"); d.set_defaults(fn=cmd_decode); common(d)
    d.add_argument("result"); d.add_argument("--name", default="603_run"); d.add_argument("--out-dir", default=RUNS)
    m = sub.add_parser("mame"); m.set_defaults(fn=cmd_mame); common(m)
    m.add_argument("--mame", default="mame"); m.add_argument("--rompath", default=os.path.expanduser("~/mame/roms"))
    m.add_argument("--bios", default="pre"); m.add_argument("--seconds", type=int, default=120)
    m.add_argument("--name"); m.add_argument("--out-dir", default=RUNS)
    m.add_argument("--keep", action="store_true", help="say where the memory dump is")
    m.add_argument("--trace", help="write an instruction trace to this file, from the start until")
    m.add_argument("--trace-start", help="start the trace at this label of the program instead")
    m.add_argument("--trace-stop", default="recover", help="stop it at these labels (comma-separated)")

    args = p.parse_args()
    if args.base & 0xFFFF:
        sys.exit("--base must be 64 KB aligned")
    load_ppctest(args.ppctest)
    args.fn(args)


if __name__ == "__main__":
    main()
