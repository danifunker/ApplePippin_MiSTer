#!/usr/bin/env python3
"""Build the supervisor-mode probe disk, and read its answer.

  build_probe.py build  [--out HD5_probe.hda] [--size-mb 32]
  build_probe.py read   HD5_probe.hda

The disk is the 040 bench's envelope (Apple partition map + Apple_Driver43,
../envelope/driver43_96blk.bin) with an HFS partition that carries a
64 KB /Results file and probe_boot.s as its boot blocks. Booting the Mac
from it (hold nothing; make it the only bootable disk, or the first one,
or select it with the startup-disk control panel beforehand) runs the
probe; `read` prints the record. See probe_boot.s for what the words mean.
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENVELOPE = os.path.join(HERE, "..", "envelope", "driver43_96blk.bin")
ENVELOPE_BLOCKS = 96
RETRO68 = os.environ.get("RETRO68", os.path.expanduser("~/repos/Retro68-build/toolchain"))
AS = os.path.join(RETRO68, "bin", "m68k-apple-macos-as")
OBJCOPY = os.path.join(RETRO68, "bin", "m68k-apple-macos-objcopy")
SIG = b"PPC603PROBE RESULTS FILE: the boot block writes its record over this line\n"


def run(*cmd, **kw):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, **kw)


def assemble(build):
    os.makedirs(build, exist_ok=True)
    obj, raw = os.path.join(build, "probe_boot.o"), os.path.join(build, "probe_boot.bin")
    run(AS, "-m68020", "-o", obj, os.path.join(HERE, "probe_boot.s"))
    run(OBJCOPY, "-O", "binary", "-j", ".text", obj, raw)
    with open(raw, "rb") as fh:
        code = fh.read()
    if len(code) > 1024:
        sys.exit("boot block is %d bytes, limit 1024" % len(code))
    return code.ljust(1024, b"\0")


def cmd_build(args):
    for tool in ("hformat", "hcopy", "humount"):
        if not shutil.which(tool):
            sys.exit("%s not found: install hfsutils" % tool)
    if not os.path.exists(AS):
        sys.exit("%s not found: build Retro68's 68k toolchain (or set RETRO68)" % AS)
    code = assemble(os.path.join(HERE, "build"))
    with open(ENVELOPE, "rb") as fh:
        env = bytearray(fh.read(ENVELOPE_BLOCKS * 512))
    total = args.size_mb * 2048
    struct.pack_into(">I", env, 4, total)
    e = bytearray(env[3 * 512:4 * 512])
    struct.pack_into(">I", e, 12, total - ENVELOPE_BLOCKS)          # pmPartBlkCnt
    struct.pack_into(">I", e, 84, total - ENVELOPE_BLOCKS)          # pmDataCnt
    env[3 * 512:4 * 512] = e
    with open(args.out, "wb") as fh:
        fh.write(env)
        fh.truncate(total * 512)
    run("hformat", "-l", "PPC603Probe", args.out, "1")
    results = os.path.join(HERE, "build", "Results")
    with open(results, "wb") as fh:
        fh.write(SIG.ljust(65536, b"\0"))
    run("hcopy", "-r", results, ":Results")
    run("humount")
    # where did the file land? its first block is the record's home
    with open(args.out, "rb") as fh:
        img = bytearray(fh.read())
    part = ENVELOPE_BLOCKS * 512
    pos = img.find(SIG, part)
    if pos < 0 or (pos - part) % 512:
        sys.exit("cannot locate /Results in the partition")
    resoff = pos - part
    marker = code.find(b"RESOFF__")
    code = bytearray(code)
    struct.pack_into(">I", code, marker + 8, resoff)
    img[part:part + 1024] = code
    with open(args.out, "wb") as fh:
        fh.write(img)
    print("wrote %s: %d MB; boot block %d bytes; /Results at partition offset 0x%X (disk block %d)"
          % (args.out, args.size_mb, len(code), resoff, (part + resoff) // 512))
    print("BlueSCSI: name it HD<id>.hda; boot the Mac from it; then: build_probe.py read %s" % args.out)


def cmd_read(args):
    with open(args.image, "rb") as fh:
        img = fh.read()
    part = ENVELOPE_BLOCKS * 512
    code = img[part:part + 1024]
    marker = code.find(b"RESOFF__")
    if marker < 0:
        sys.exit("no probe boot block on this image")
    resoff = struct.unpack_from(">I", code, marker + 8)[0]
    rec = img[part + resoff:part + resoff + 512]
    if rec.startswith(SIG[:16]):
        print("the record is untouched: the boot block never ran (the Mac did not boot from this disk)")
        return 1
    w = struct.unpack_from(">8I", rec, 0)
    names = ["PRB1", "CAL0", "ECHO", "CAL1", "MSR", "CAL2", "PVR", "DONE"]
    for n, v in zip(names, w):
        print("  %-5s %08X %s" % (n, v, v.to_bytes(4, "big") if n in ("PRB1", "CAL0", "CAL1", "CAL2", "DONE") else ""))
    if w[0] != 0x50524231:
        print("no PRB1: the boot block did not get as far as its first write")
    elif w[2] != 0x5050:
        print("CAL0 but no echo: the Mixed Mode call to PowerPC code failed from a boot block.")
    elif w[4] == 0:
        print("echo ok, CAL1 but no MSR: mfmsr did not return. Emulated code is NOT in supervisor mode.")
    else:
        pr = (w[4] >> 14) & 1
        print("MSR %08X: PR=%d -> %s" % (w[4], pr, "SUPERVISOR mode: boot blocks are a route for super603"
                                          if pr == 0 else "user mode (mfmsr was emulated for us)"))
        if w[6]:
            print("PVR %08X: %s" % (w[6], {3: "603", 6: "603e", 7: "603ev", 4: "604", 9: "604e"}.get(w[6] >> 16, "?")))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.set_defaults(fn=cmd_build)
    b.add_argument("--out", default=os.path.join(HERE, "HD5_probe.hda")); b.add_argument("--size-mb", type=int, default=32)
    r = sub.add_parser("read"); r.set_defaults(fn=cmd_read); r.add_argument("image")
    args = p.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
