#!/usr/bin/env python3
"""The Time Manager's view of a decoded trace (syn/mister.py trace --file): from the
SWIM3 mask write (the floppy driver's init), the VIA's reads and writes, Grand
Central's clears and mask writes, the interrupt events (kind 17), the SWIM3's status
reads and the CPU's samples (PC, last exception, load address), one line each.
    python3 syn/tmview.py TRACE.txt [RECORDS_AFTER] [RECORDS_BEFORE]
"""
import re, sys
f = sys.argv[1]; after = int(sys.argv[2]) if len(sys.argv) > 2 else 400; before = int(sys.argv[3]) if len(sys.argv) > 3 else 40
lines = open(f).read().splitlines()
start = next((k for k, l in enumerate(lines) if "GC int mask    w 00a01f90" in l), None)
if start is None: sys.exit("no SWIM3 mask write in %s" % f)
for l in lines[max(0, start - before):start + after]:
    if "kind 15" in l or "perf part" in l or "ADB cmd" in l: continue
    m = re.search(r"^\s*(\d+) cpu PC (\w+) ins \w+ MSR \w+ last exc (\w+) at (\w+) ld ea (\w+)", l)
    if m:
        print("%s   cpu %s exc %s@%s ea %s" % (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5))); continue
    if " VIA " in l or " GC int " in l or "INT ev" in l or "SWIM3 hshk/set r" in l or "SWIM3 phase    w 20" in l or "INT mask" in l:
        l = re.sub(r"\s+\(be \w\)$", "", l)
        l = l.replace(" | VIA IFR", " IFR").replace("events ", "ev ").replace("lines ", "ln ")
        print(l[:118])
