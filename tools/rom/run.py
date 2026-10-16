#!/usr/bin/env python3
"""Region-map and disassemble an Apple Pippin 4 MB boot ROM (data only;
nothing in the ROM is executed).

    python3 -I tools/rom/run.py <rom> <outdir> [--label NAME] [--detok PATH]
    python3 -I tools/rom/run.py --diff <romA> <romB> <out.md> [--labels A B]
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I drops the script dir on newer Pythons

from pippinrom.analyze import ROMAnalysis   # noqa: E402
from pippinrom.emit import Writer           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--diff', action='store_true')
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--label')
    ap.add_argument('--labels', nargs=2)
    ap.add_argument('--detok')
    a = ap.parse_args()
    if a.diff:
        from pippinrom.diff import write_diff
        ra, rb, out = a.paths
        la, lb = a.labels or (os.path.basename(ra), os.path.basename(rb))
        write_diff(ra, rb, out, la, lb)
        return
    rom, out = a.paths
    data = open(rom, 'rb').read()
    sha1 = hashlib.sha1(data).hexdigest()
    A = ROMAnalysis(data, a.label or os.path.basename(rom))
    w = Writer(out, A, rom, sha1, detok=a.detok)
    w.run()
    cov = A.coverage()
    print('%s: %d regions, unknown %d bytes, files %d' % (A.label, len(A.regions), cov.get('unknown', 0), len(w.written)))


if __name__ == '__main__':
    main()
