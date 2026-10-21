#!/usr/bin/env python3
"""The CPU's capture (the trace's kind 19 records, DSPPC603 PERF) as one stream: each
instruction's PC, word, the last data access the cache took (EA, r/w) and the word's
PowerPC disassembly (Retro68's powerpc-apple-macos-objdump, the words laid end to end).
    python3 syn/capview.py TRACE.txt [FIRST [COUNT]]
"""
import os, re, struct, subprocess, sys, tempfile
OBJDUMP = os.path.expanduser("~/repos/Retro68-build/toolchain/bin/powerpc-apple-macos-objdump")
f = sys.argv[1]; first = int(sys.argv[2]) if len(sys.argv) > 2 else 0; count = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
ins = []
for line in open(f):
    m = re.search(r" cap +(\d+)  ([0-9a-f]{8}) ([0-9a-f]{8}) ea ([0-9a-f]{8}) ([rw]) \| ([0-9a-f]{8}) ([0-9a-f]{8}) ea ([0-9a-f]{8}) ([rw])", line)
    if not m: continue
    k = int(m.group(1))
    ins.append((2 * k, int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16), m.group(5)))
    ins.append((2 * k + 1, int(m.group(6), 16), int(m.group(7), 16), int(m.group(8), 16), m.group(9)))
ins.sort()
if not ins: sys.exit("no capture records in %s" % f)
blob = b"".join(struct.pack(">I", w) for _, _, w, _, _ in ins)
tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False); tmp.write(blob); tmp.close()
out = subprocess.run([OBJDUMP, "-b", "binary", "-EB", "-m", "powerpc:common", "-D", tmp.name], capture_output=True, text=True).stdout
os.unlink(tmp.name)
dis = {}
for l in out.splitlines():
    m = re.match(r"\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} ){4}\s*(.*)$", l)
    if m: dis[int(m.group(1), 16) // 4] = m.group(2).strip()
last_ea = None
for n, pc, w, ea, rw in ins[first:first + count]:
    acc = "" if (ea, rw) == last_ea else "  <- %s %08x" % ("st" if rw == "w" else "ld", ea)
    last_ea = (ea, rw)
    print("%4d %08x %08x  %-32s%s" % (n, pc, w, dis.get(n, ""), acc))
