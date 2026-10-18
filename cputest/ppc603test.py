#!/usr/bin/env python3
"""PowerPC 603 CPU test suite, host side: the Mac OS route for a Performa 62xx.

  ppc603test.py vectors  [--cpu 603] [--out ppc603.vec]      write the vector file
  ppc603test.py image    [--app PPC603Test.bin] [--out HD40_512_ppc603.hda]
                                                             an HFS disk image for the BlueSCSI
  ppc603test.py decode   ppc603.res [--vec ppc603.vec] [--name NAME] [--golden FILE.csv]
                                                             results -> runs/results_NAME.csv
  ppc603test.py diff     A.csv B.csv                         two results files, vector by vector
  ppc603test.py selftest                                     the format round trip, no Mac needed

The vector set, the record formats, the CSV format and the decoder's rules
are MacPPC7300's ppctest (imported from --ppctest, default
../../MacPPC7300_MiSTer/ppctest; nothing there is changed). What is new here
is the route: a Mac OS application (macapp/) runs the vectors in user mode
on a Mac with no Open Firmware, reading `ppc603.vec` and writing
`ppc603.res` on the same HFS volume. vec603.py has both file formats.
"""

import argparse
import csv
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
DEFAULT_PPCTEST = os.path.normpath(os.path.join(HERE, "..", "..", "MacPPC7300_MiSTer", "ppctest"))

import vec603  # noqa: E402


def load_ppctest(path):
    if not os.path.isdir(path):
        sys.exit("ppctest not found at %s (use --ppctest)" % path)
    sys.path.insert(0, path)
    global vectors, image, ppctest
    import vectors, image, ppctest  # noqa: E401,F401
    return path


def cmd_vectors(args):
    vs = vectors.build_v4(args.cpu)
    data = vec603.pack_vector_file(vs)
    with open(args.out, "wb") as fh:
        fh.write(data)
    with_exp = sum(1 for v in vs if v.exp is not None)
    print("wrote %s: %d vectors (%d with expected values), %.1f MB, build %08X"
          % (args.out, len(vs), with_exp, len(data) / 1e6, vec603.build_id(vs)))
    srcs = {}
    for v in vs:
        srcs[v.src] = srcs.get(v.src, 0) + 1
    print("  " + ", ".join("%s %d" % kv for kv in srcs.items()))


ENVELOPE = os.path.join(HERE, "envelope", "driver43_96blk.bin")
ENVELOPE_BLOCKS = 96
ENVELOPE_SOURCE = os.path.expanduser("~/quadra800-bench/DONE quadra800-cpu.hda")


def cmd_image(args):
    """A disk image the Mac mounts at boot: the 96-block envelope of the
    Quadra 800 bench disks (driver descriptor, Apple partition map,
    Apple_Driver43) followed by an HFS partition that hfsutils formats and
    fills. Results written on the Mac come back in the same file."""
    import struct as st
    for tool in ("hformat", "hcopy", "humount"):
        if not shutil.which(tool):
            sys.exit("%s not found: install hfsutils" % tool)
    if not os.path.exists(args.vec):
        sys.exit("%s not found: run `ppc603test.py vectors` first" % args.vec)
    if not os.path.exists(ENVELOPE):
        if not os.path.exists(ENVELOPE_SOURCE):
            sys.exit("%s is missing: copy the first 96 blocks of any Mac-initialised .hda there" % ENVELOPE)
        with open(ENVELOPE_SOURCE, "rb") as fh:
            env = fh.read(ENVELOPE_BLOCKS * 512)
        os.makedirs(os.path.dirname(ENVELOPE), exist_ok=True)
        with open(ENVELOPE, "wb") as fh:
            fh.write(env)
    with open(ENVELOPE, "rb") as fh:
        env = bytearray(fh.read(ENVELOPE_BLOCKS * 512))
    total = args.size_mb * 2048
    st.pack_into(">I", env, 4, total)                           # the driver descriptor's block count
    e = bytearray(env[3 * 512:4 * 512])                         # partition 3: the HFS partition
    if e[:2] != b"PM" or b"Apple_HFS" not in bytes(e[48:80]):
        sys.exit("unexpected envelope: partition entry 3 is not Apple_HFS")
    st.pack_into(">I", e, 12, total - ENVELOPE_BLOCKS)              # pmPartBlkCnt
    st.pack_into(">I", e, 84, total - ENVELOPE_BLOCKS)              # pmDataCnt (what hfsutils sizes the volume by)
    env[3 * 512:4 * 512] = e
    with open(args.out, "wb") as fh:
        fh.write(env)
        fh.truncate(total * 512)
    run = lambda *cmd: subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    run("hformat", "-l", args.label, args.out, "1")
    run("hcopy", "-r", args.vec, ":ppc603.vec")
    have_app = args.app and os.path.exists(args.app)
    if have_app:
        run("hcopy", "-m", args.app, ":")          # Retro68's .bin is MacBinary: keeps type APPL
    else:
        print("note: application %s not found; the image carries only the vectors" % args.app)
    for extra in args.extra:
        run("hcopy", "-m" if extra.endswith(".bin") else "-r", extra, ":")
    run("humount")
    print("wrote %s: %d MB, Apple partition map + Driver43 + HFS volume %r with ppc603.vec%s%s" % (
        args.out, args.size_mb, args.label, " and PPC603Test" if have_app else "",
        " + %d extra" % len(args.extra) if args.extra else ""))
    print("BlueSCSI: name it HD<id>.hda (e.g. HD4.hda); results: hmount %s 1; hcopy -r :ppc603.res ." % args.out)


def load_vec_file(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != vec603.VEC_MAGIC:
        sys.exit("%s is not a ppc603 vector file" % path)
    build, nvec = struct.unpack_from(">II", data, vec603.V_BUILD)
    return data, build, nvec


def vec_entry(data, i):
    off = vec603.HDR + i * vec603.ENTRY
    inp = data[off:off + vec603.REC]
    exp = data[off + vec603.REC:off + vec603.ENTRY]
    return inp, exp


def unpack_input(rec):
    (insn, flags, r3, r4, r5, r6, cr, xer, ctr, fpscr,
     f4, f5, f6) = struct.unpack(">2I4I4I3Q", rec)
    return dict(insn=insn, flags=flags, r3=r3, r4=r4, r5=r5, r6=r6, cr=cr, xer=xer,
                ctr=ctr, fpscr=fpscr, f4=f4, f5=f5, f6=f6)


def cmd_decode(args):
    vs = vectors.build_v4(args.cpu)
    names = [v.name for v in vs]
    srcs = [v.src for v in vs]
    with open(args.res, "rb") as fh:
        res = vec603.Results(fh.read())
    vdata, vbuild, nvec = load_vec_file(args.vec)
    if res.build != vbuild:
        sys.exit("results build %08X does not match the vector file's %08X" % (res.build, vbuild))
    vs = vs[:nvec]                     # a file may carry a prefix of the set (selftest)
    names, srcs = names[:nvec], srcs[:nvec]
    if nvec != len(vs) or vec603.build_id(vs) != vbuild:
        sys.exit("the vector file was not built from this vector set (build %08X vs %08X): "
                 "pass the same --cpu / --ppctest as when it was built"
                 % (vbuild, vec603.build_id(vs)))

    IN_FIELDS, OUT_FIELDS = vectors.CSV_IN, vectors.OUT_FIELDS
    fmt = image.fmt
    status = 0
    print("--- Mac OS run: %s (Gestalt cput %04X), machine %d, system %04X"
          % (res.cpu_name(), res.cpu, res.machine, res.sysv))
    print("    vector file build %08X, %d vectors; %d run" % (vbuild, nvec, res.ndone))
    if not res.done:
        print("    NOT FINISHED (status %08X): the run stopped on vector #%X"
              % (res.status, res.ndone))
        status = 1
    n = min(res.ndone, nvec)
    cs = vec603.checksum(res.records, n)
    print("    checksum: on the Mac %08X, of the file %08X, mismatches counted on the Mac %d,"
          " ticks %d" % (res.sum, cs, res.nmiss, res.ticks))
    if res.done and cs != res.sum:
        print("    WARNING: the results do not match the Mac's checksum; the file is corrupt.")
        status = 1

    golden = None
    gpath = args.golden
    if gpath is None and os.path.exists(vectors.GOLDEN_604):
        gpath = vectors.GOLDEN_604
    if gpath:
        golden = ppctest.load_golden(gpath)
    per, by_name, shown, rows = {}, {}, {}, []
    gold = dict(same=0, differ=0, by_name={}, first=[]) if golden else None
    limit = args.show
    for i in range(n):
        inp_rec, exp_rec = vec_entry(vdata, i)
        inp = unpack_input(inp_rec)
        got = vectors.unpack_output(res.record(i))
        exp = vectors.unpack_output(exp_rec) if vs[i].exp is not None else None
        src, name = srcs[i], names[i]
        st3 = per.setdefault(src, [0, 0, 0])
        if exp is None:
            verdict = "recorded"
            st3[2] += 1
        elif got == exp:
            verdict = "match"
            st3[0] += 1
        else:
            verdict = "MISMATCH"
            st3[1] += 1
            by_name[(src, name)] = by_name.get((src, name), 0) + 1
            if shown.get(src, 0) < limit:
                shown[src] = shown.get(src, 0) + 1
                print("  #%05X %-9s insn=%08X [%s]" % (i, name, inp["insn"], src)
                      + "".join(" %s=%s" % (f, fmt(f, inp[f])) for f in IN_FIELDS if inp[f]))
                for f in OUT_FIELDS:
                    if got[f] != exp[f]:
                        print("      %-5s expected %s  got %s" % (f, fmt(f, exp[f]), fmt(f, got[f])))
        row = (["%d" % i, name, src, "%08X" % inp["insn"]]
               + [fmt(f, inp[f]) for f in IN_FIELDS]
               + [fmt(f, got[f]) for f in OUT_FIELDS] + [verdict])
        rows.append(row)
        if gold is not None:
            g = golden.get((name, row[3]) + tuple(row[4:4 + len(IN_FIELDS)]))
            if g is not None:
                if g == tuple(row[4 + len(IN_FIELDS):-1]):
                    gold["same"] += 1
                else:
                    gold["differ"] += 1
                    gold["by_name"][name] = gold["by_name"].get(name, 0) + 1
                    if len(gold["first"]) < limit:
                        gold["first"].append((i, g, row[4 + len(IN_FIELDS):-1]))

    notes = ["Mac OS run: %s, Gestalt cput %04X, machine %d, system %04X"
             % (res.cpu_name(), res.cpu, res.machine, res.sysv)]
    print("    %-14s %7s %7s %7s" % ("source", "match", "DIFFER", "no exp."))
    for src, (m, d, r) in per.items():
        line = "    %-14s %7d %7d %7d" % (src, m, d, r)
        print(line)
        notes.append(line.strip())
    if by_name:
        print("    differing vectors by instruction: " + ", ".join(
            "%s %d" % (k[1], c) for k, c in sorted(by_name.items(), key=lambda kv: -kv[1])[:24]))
    if gold is not None:
        line = ("    against %s: %d vectors in common, %d identical, %d differ"
                % (os.path.basename(gpath), gold["same"] + gold["differ"], gold["same"],
                   gold["differ"]))
        print(line)
        notes.append(line.strip())
        if gold["differ"]:
            print("      by instruction: " + ", ".join(
                "%s %d" % kv for kv in sorted(gold["by_name"].items(), key=lambda kv: -kv[1])[:24]))
            for i, g, mine in gold["first"]:
                print("      #%05X %s" % (i, names[i]))
                for f, a, b in zip(OUT_FIELDS, g, mine):
                    if a != b:
                        print("        %-5s %s: %s  |  here: %s" % (f, os.path.basename(gpath), a, b))
    name = args.name or "%s_%s" % (res.cpu_name(), args.machine or "macos")
    ppctest.save_results(args.out_dir, name, bool(args.name), rows, notes)
    sys.exit(status)


def cmd_diff(args):
    ppctest.cmd_diff(args)


def cmd_selftest(args):
    """Build a small vector file, forge the results a perfect run would write
    (expected records where there are any, zeros elsewhere), and decode."""
    vs = vectors.build_v4(args.cpu)[:2000]
    tmp = tempfile.mkdtemp(prefix="ppc603-")
    vec = os.path.join(tmp, "ppc603.vec")
    with open(vec, "wb") as fh:
        fh.write(vec603.pack_vector_file(vs))
    recs = b"".join(v.pack_expected() for v in vs)
    hdr = bytearray(vec603.HDR)
    hdr[:8] = vec603.RES_MAGIC
    struct.pack_into(">10I", hdr, vec603.R_BUILD, vec603.build_id(vs), len(vs), len(vs),
                     vec603.checksum(recs, len(vs)), 0, 0x103, 42, 0x0755, vec603.RS_DONE, 1234)
    res = os.path.join(tmp, "ppc603.res")
    with open(res, "wb") as fh:
        fh.write(bytes(hdr) + recs)
    a = argparse.Namespace(res=res, vec=vec, cpu=args.cpu, golden=None, show=4,
                           name="selftest", machine=None, out_dir=tmp)
    try:
        cmd_decode(a)
    except SystemExit as e:
        if e.code:
            raise
    with open(os.path.join(tmp, "results_selftest.csv"), newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(vs)
    assert all(r["verdict"] == ("match" if v.exp is not None else "recorded")
               for r, v in zip(rows, vs))
    shutil.rmtree(tmp)
    print("selftest ok: %d vectors round-tripped through the file formats and the decoder"
          % len(vs))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ppctest", default=DEFAULT_PPCTEST, help="MacPPC7300's ppctest directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("vectors"); v.set_defaults(fn=cmd_vectors)
    v.add_argument("--cpu", default="603")
    v.add_argument("--out", default=os.path.join(HERE, "ppc603.vec"))

    im = sub.add_parser("image"); im.set_defaults(fn=cmd_image)
    im.add_argument("--vec", default=os.path.join(HERE, "ppc603.vec"))
    im.add_argument("--app", default=os.path.join(HERE, "macapp", "build", "PPC603Test.bin"))
    im.add_argument("--out", default=os.path.join(HERE, "HD40_512_ppc603.hda"))
    im.add_argument("--label", default="PPC603Test")
    im.add_argument("--size-mb", type=int, default=64)
    im.add_argument("--extra", action="append", default=[], help="more files to put on the volume")

    d = sub.add_parser("decode"); d.set_defaults(fn=cmd_decode)
    d.add_argument("res")
    d.add_argument("--vec", default=os.path.join(HERE, "ppc603.vec"))
    d.add_argument("--cpu", default="603")
    d.add_argument("--name"); d.add_argument("--machine", help="for the file name, e.g. 6200")
    d.add_argument("--golden"); d.add_argument("--out-dir", default=RUNS)
    d.add_argument("--show", type=int, default=4)

    df = sub.add_parser("diff"); df.set_defaults(fn=cmd_diff)
    df.add_argument("a"); df.add_argument("b"); df.add_argument("--show", type=int, default=8)

    s = sub.add_parser("selftest"); s.set_defaults(fn=cmd_selftest)
    s.add_argument("--cpu", default="603")

    args = p.parse_args()
    load_ppctest(args.ppctest)
    args.fn(args)


if __name__ == "__main__":
    main()
