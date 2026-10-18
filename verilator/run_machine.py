#!/usr/bin/env python3
"""Build the whole Pippin (Pippin_system: DSPPC603 and the machine) under
Verilator and run a ROM on it, in lockstep with dingusppc's CPU.

    python3 verilator/run_machine.py [machine_tb options]

Defaults: the Kinka 1.3 ROM (scratch/pippin/, git-ignored; --rom10 for 1.0,
--rom FILE for any), in lockstep with dingusppc. Every other option is passed
to machine_tb (see core_main.cpp); --no-lockstep runs the machine alone.

    python3 verilator/run_machine.py --max-instr 1000000 --progress 100000
    python3 verilator/run_machine.py --dev-log dev.log --max-instr 2000000
    python3 verilator/run_machine.py --trace-from 5000 --trace-count 50

The device log (--dev-log) has the format of verilator/machref's log, so the
two can be compared with verilator/machref/devdiff.py; the reference log is
    machref --rom ROM --machine pippin --cpu 603 --pvr 00030100 --log ref.log
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROMS = os.path.join(HERE, "..", "scratch", "pippin")
ROM13 = os.path.join(ROMS, "bandai pippin,19960920 - kinka 1.3,- 3e6b3ee4-a52528e9ce8c.rom")
ROM10 = os.path.join(HERE, "..", "ROMs", "2BEF21B7 - Bandai Pippin (Kinka 1.0).ROM")


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    args = sys.argv[1:]
    cache = os.path.join(os.path.expanduser("~"), ".cache", "applepippin")
    build = os.environ.get("PIPPIN_BUILD") or os.path.join(cache, "verilator")
    build = os.path.join(build, "pippin")
    refdir = os.path.join(cache, "dingusref")
    dingus = os.environ.get("DINGUS") or os.path.join(cache, "dingusppc")
    tmp = build.rstrip("/") + "-tmp"
    os.makedirs(tmp, exist_ok=True)
    os.environ["TMPDIR"] = tmp

    lockstep = "--no-lockstep" not in args
    rom = ROM10 if "--rom10" in args else ROM13
    args = [a for a in args if a not in ("--no-lockstep", "--rom10")]
    if "--rom" not in args:
        args = ["--rom", rom] + args
    if lockstep and "--lockstep" not in args:
        args = ["--lockstep"] + args

    r = run(["make", "-s", "-C", os.path.join(HERE, "ref"), "BUILD=" + refdir, "DINGUS=" + dingus])
    if r.returncode:
        print(r.stdout)
        print("building the dingusppc reference failed")
        return 1
    lib = os.path.join(refdir, "libdingusref.a")
    r = run(["make", "-s", "-C", HERE, "machine", "BUILD=" + build, "REF_LIB=" + lib])
    if r.returncode:
        print(r.stdout)
        print("building the machine bench failed")
        return 1
    if r.stdout.strip():
        print(r.stdout.strip())
    tb = os.path.join(build, "machine_ref", "machine_tb")
    return subprocess.call([tb, "--machine"] + args)


if __name__ == "__main__":
    sys.exit(main())
