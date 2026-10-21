#!/usr/bin/env python3
"""The rolling XOR of a CD image's 512-byte blocks as Pippin_scsidisk folds them (the
trace's kind 18): a Mode 1 raw image (2352 bytes a sector, 2048 of user data at 16)
served as the Main's CD layer serves it, 2048-byte sectors in 512-byte blocks.
    python3 syn/cdxor.py IMAGE.bin LBA...          the XOR of those blocks
    python3 syn/cdxor.py IMAGE.bin --check TRACE.txt   every kind 18 record against the image
"""
import re, sys
def fold(data):
    x = 0
    for b in data:
        x = ((x << 1) | (x >> 31)) & 0xFFFFFFFF
        x ^= b
    return x
img = open(sys.argv[1], 'rb').read()
raw = 2352 if len(img) % 2352 == 0 else 2048
def block(lba):
    sec, off = lba // 4, (lba % 4) * 512
    base = sec * raw + (16 if raw == 2352 else 0)
    return img[base + off:base + off + 512]
if len(sys.argv) > 3 and sys.argv[2] == "--check":
    ok = bad = 0
    for line in open(sys.argv[3]):
        m = re.search(r"block lba (\d+) half (\d) slot (\d) bytes (\d+) xor ([0-9a-f]{8})", line)
        if not m: continue
        lba, n, x = int(m.group(1)), int(m.group(4)), int(m.group(5), 16)
        want = fold(block(lba))
        if x == want and n == 512: ok += 1
        else:
            bad += 1
            if bad <= 12: print("  lba %d: trace %08x (%d bytes), image %08x" % (lba, x, n, want))
    print("blocks %d: %d match, %d differ" % (ok + bad, ok, bad))
else:
    for a in sys.argv[2:]:
        lba = int(a, 0); print("lba %d: %08x" % (lba, fold(block(lba))))
