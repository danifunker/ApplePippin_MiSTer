#!/usr/bin/env python3
"""Pack or unpack the ROM disassembly folders as one reproducible .tar.xz archive.

  pack.py pack   [disasm_dir]   disasm/kinka-*/       ->  disasm/disasm.tar.xz
  pack.py unpack [disasm_dir]   disasm/disasm.tar.xz  ->  disasm/kinka-*/

All per-ROM folders go into a single archive so xz can compress the nearly
identical ROM listings against each other (about 7.8 MB, against 12.4 MB as
separate archives). The archive is byte-identical for identical input: sorted
names, mtime 0, uid/gid 0, no user names, and xz -9e. Re-packing unchanged
output therefore leaves git with nothing to commit.
"""
import lzma
import os
import sys
import tarfile

ARCHIVE = "disasm.tar.xz"
FILTERS = [{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}]


def _normalize(ti):
    ti.mtime = 0
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = ""
    ti.mode = 0o755 if ti.isdir() else 0o644
    return ti


def pack(root):
    out = os.path.join(root, ARCHIVE)
    dirs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not dirs:
        sys.exit(f"no disassembly folders in {root}")
    with lzma.open(out + ".tmp", "wb", format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, filters=FILTERS) as xz:
        with tarfile.open(fileobj=xz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for d in dirs:
                for dirpath, dirnames, filenames in os.walk(os.path.join(root, d)):
                    dirnames.sort()
                    rel = os.path.relpath(dirpath, root)
                    tar.add(dirpath, arcname=rel, recursive=False, filter=_normalize)
                    for f in sorted(filenames):
                        tar.add(os.path.join(dirpath, f), arcname=os.path.join(rel, f), filter=_normalize)
    os.replace(out + ".tmp", out)
    print(f"{out}  {os.path.getsize(out) / 1048576:.1f} MB  ({', '.join(dirs)})")


def unpack(root):
    with tarfile.open(os.path.join(root, ARCHIVE), "r:xz") as tar:
        members = tar.getmembers()
        if hasattr(tarfile, "data_filter"):
            tar.extractall(root, filter="data")
        else:  # Python < 3.12 without the backport: allow only plain files and folders inside root
            base = os.path.realpath(root)
            for m in members:
                dest = os.path.realpath(os.path.join(root, m.name))
                if not (m.isfile() or m.isdir()) or os.path.commonpath([base, dest]) != base:
                    sys.exit(f"refusing archive member {m.name!r}")
            tar.extractall(root, members=members)
        tops = sorted({m.name.split("/")[0] for m in members})
    print("unpacked: " + ", ".join(os.path.join(root, t) + "/" for t in tops))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("pack", "unpack"):
        sys.exit(__doc__)
    here = os.path.dirname(os.path.abspath(__file__))
    root = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "..", "..", "disasm")
    {"pack": pack, "unpack": unpack}[sys.argv[1]](os.path.normpath(root))
