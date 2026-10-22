#!/usr/bin/env python3
"""The CPU's capture (the trace's kind 19 records, DSPPC603 PERF) as one stream: each
instruction's PC, word, the last data access the cache took (EA, r/w) and the word's
PowerPC disassembly (Retro68's powerpc-apple-macos-objdump, the words laid end to end).
    python3 syn/capview.py TRACE.txt [FIRST [COUNT]]
Since 2026-10-21 20:40 the record's second word is the data of the last access
answered (a load's value, a store's first word as merged), not the instruction: with
--rom ROM (Kinka 1.3) the word is read back from the ROM (PCs 68xxxxxx are the 68k
emulator's image, the ROM at +0x300000; FFxxxxxx the ROM itself) and the data is
printed after the access (`= value`, whenever it changes).
"""
import os, re, struct, subprocess, sys, tempfile
OBJDUMP = os.path.expanduser("~/repos/Retro68-build/toolchain/bin/powerpc-apple-macos-objdump")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
rom = None
if "--rom" in sys.argv:
    rom = open(sys.argv[sys.argv.index("--rom") + 1], "rb").read()
    args = [a for a in args if a != sys.argv[sys.argv.index("--rom") + 1]]
f = args[0]; first = int(args[1]) if len(args) > 1 else 0; count = int(args[2]) if len(args) > 2 else 100000
def rom_word(pc):
    if rom is None: return None
    if 0x68000000 <= pc < 0x68100000: o = pc - 0x68000000 + 0x300000
    elif pc >= 0xFFC00000: o = pc - 0xFFC00000
    else: return None
    return struct.unpack(">I", rom[o:o + 4])[0]
ins = []
for line in open(f):
    m = re.search(r" cap +(\d+)  ([0-9a-f]{8}) ([0-9a-f]{8}) ea ([0-9a-f]{8}) ([rw]) \| ([0-9a-f]{8}) ([0-9a-f]{8}) ea ([0-9a-f]{8}) ([rw])", line)
    if not m: continue
    k = int(m.group(1))
    ins.append((2 * k, int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16), m.group(5)))
    ins.append((2 * k + 1, int(m.group(6), 16), int(m.group(7), 16), int(m.group(8), 16), m.group(9)))
ins.sort()
if not ins: sys.exit("no capture records in %s" % f)
# (n, pc, word, ea, rw, data): the word from the ROM when the record carries data
if rom is not None:
    ins = [(n, pc, rom_word(pc) or 0, ea, rw, w) for n, pc, w, ea, rw in ins]
else:
    ins = [(n, pc, w, ea, rw, None) for n, pc, w, ea, rw in ins]
blob = b"".join(struct.pack(">I", w) for _, _, w, _, _, _ in ins)
tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False); tmp.write(blob); tmp.close()
out = subprocess.run([OBJDUMP, "-b", "binary", "-EB", "-m", "powerpc:common", "-D", tmp.name], capture_output=True, text=True).stdout
os.unlink(tmp.name)
dis = {}
for l in out.splitlines():
    m = re.match(r"\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} ){4}\s*(.*)$", l)
    if m: dis[int(m.group(1), 16) // 4] = m.group(2).strip()
last_ea = None; last_data = None
for n, pc, w, ea, rw, data in ins[first:first + count]:
    acc = "" if (ea, rw) == last_ea else "  <- %s %08x" % ("st" if rw == "w" else "ld", ea)
    last_ea = (ea, rw)
    if data is not None and data != last_data:
        acc += "  = %08x" % data
        last_data = data
    print("%4d %08x %08x  %-32s%s" % (n, pc, w, dis.get(n, ""), acc))
