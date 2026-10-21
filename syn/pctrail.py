#!/usr/bin/env python3
"""The 68k's trail through a decoded trace (syn/mister.py trace --file): from the SWIM3
mask write, each CPU sample's load address (at the emulator's opcode fetch it is the
68k PC + 2) labelled by the ROM routine it falls in (Kinka 1.3: the Time Manager, the
floppy driver), with the interrupt events, the VIA's T2 writes and the SWIM3 polls.
    python3 syn/pctrail.py TRACE.txt [RECORDS_AFTER] [RECORDS_BEFORE]
"""
import re, sys
RANGES = [
    (0xFFC3B3EA, 0xFFC3B432, "TM PrimeTime entry"), (0xFFC3B432, 0xFFC3B486, "TM PrimeTime insert"),
    (0xFFC3B486, 0xFFC3B4A0, "TM walk"), (0xFFC3B4A0, 0xFFC3B4B0, "TM PrimeTime end"),
    (0xFFC3B4B0, 0xFFC3B4D8, "TM dispatch"), (0xFFC3B4D8, 0xFFC3B552, "TM reload"),
    (0xFFC3B552, 0xFFC3B57C, "TM trampolines"), (0xFFC3B57C, 0xFFC3B630, "TM misc"),
    (0xFFC3B630, 0xFFC3B6BC, "TM timer read"), (0xFFC3B6BC, 0xFFC3B6C2, "TM"), (0xFFC3B6C2, 0xFFC3B6CC, "TM trampoline +14"),
    (0xFFC3B366, 0xFFC3B3EA, "TM InsTime"),
    (0xFFCF5C4E, 0xFFCF5D64, "drv init"), (0xFFCF668E, 0xFFCF6750, "drv poll loop"),
    (0xFFCF7B8C, 0xFFCF7BA2, "drv prime"), (0xFFCF7BA2, 0xFFCF7BC2, "drv task fired"),
    (0xFFCF7BC2, 0xFFCF7BDC, "drv wait/stash"), (0xFFCF7BDC, 0xFFCF7BDE, "drv DEBUGGER"),
    (0xFFCF7BDE, 0xFFCF7BF2, "drv cancel task"),
    (0xFFCF79A0, 0xFFCF7B8C, "drv chip/drive"), (0xFFCF5A00, 0xFFCF9000, "drv other"),
]
def label(ea):
    for lo, hi, name in RANGES:
        if lo <= ea < hi: return name
    if 0xFFC00000 <= ea < 0xFFFFFFFF: return "ROM"
    if ea < 0x02000000: return "RAM"
    return ""
f = sys.argv[1]; after = int(sys.argv[2]) if len(sys.argv) > 2 else 600; before = int(sys.argv[3]) if len(sys.argv) > 3 else 30
lines = open(f).read().splitlines()
start = next((k for k, l in enumerate(lines) if "GC int mask    w 00a01f90" in l), None)
if start is None: sys.exit("no SWIM3 mask write in %s" % f)
for l in lines[max(0, start - before):start + after]:
    m = re.search(r"^\s*(\d+) cpu PC (\w+) ins \w+ MSR \w+ last exc (\w+) at (\w+) ld ea (\w+)", l)
    if m:
        ea = int(m.group(5), 16)
        print("%s   %s ea %s  %s" % (m.group(1), m.group(2), m.group(5), label(ea))); continue
    if "INT ev" in l or " VIA T2CH       w" in l or "SWIM3 hshk/set r" in l or "GC int mask" in l or "GC int clear" in l:
        l = re.sub(r"\s+\(be \w\)$", "", l); l = l.replace(" | VIA IFR", " IFR").replace("events ", "ev ").replace("lines ", "ln ")
        print(l[:110])
