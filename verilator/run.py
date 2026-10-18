#!/usr/bin/env python3
"""Build a CPU's Verilator model and replay a real chip's golden vectors.

    python verilator/run.py                 the DSPPC603 against the 603e run
    python verilator/run.py --cpu 604       the DSPPC604 against the 604 run
    python verilator/run.py --only int      integer vectors only
    python verilator/run.py --name FMADD    one instruction (all its variants)
    python verilator/run.py --show 20       print more failures per instruction
    python verilator/run.py --csv x.csv     another vector file (see fpmodel.py)

--cpu 603 (the default) builds rtl/DSPPC603 and replays
cputest/runs/results_603e_6300_run1.csv; --cpu 604 builds rtl/DSPPC604 and
replays ppctest/runs/results_604_run2.csv. Each model has its own build
directory. Other options are passed on to the test bench; `--help` lists them.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD_ENV = "PIPPIN_BUILD"
# the real chip's results each model is checked against by default
DEFAULT_CSV = {
    "603": os.path.join(HERE, "..", "cputest", "runs", "results_603e_6300_run1.csv"),
    "604": os.path.join(HERE, "..", "ppctest", "runs", "results_604_run2.csv"),
}


def build_dir(cpu):
    """Where a model's benches are built: one directory per CPU model."""
    root = os.environ.get(BUILD_ENV) or os.path.join(
        os.path.expanduser("~"), ".cache", "applepippin", "verilator")
    return os.path.join(root, "cpu" + cpu)


def take_cpu(args):
    """Remove --cpu N from the arguments; return (N, the rest)."""
    cpu = "603"
    if "--cpu" in args:
        i = args.index("--cpu")
        cpu = args[i + 1]
        args = args[:i] + args[i + 2:]
    if cpu not in DEFAULT_CSV:
        raise SystemExit("--cpu: 603 or 604")
    return cpu, args


def main():
    cpu, args = take_cpu(sys.argv[1:])
    args = [os.path.abspath(a) if os.path.isfile(a) else a for a in args]
    if "--csv" not in args and "--help" not in args and "-h" not in args:
        args += ["--csv", os.path.abspath(DEFAULT_CSV[cpu])]
    build = build_dir(cpu)
    os.makedirs(build, exist_ok=True)
    rc = subprocess.call(["make", "-s", "-C", HERE, "BUILD=" + build, "CPU=" + cpu])
    if rc:
        print("build failed")
        return rc
    os.chdir(HERE)
    sys.stdout.flush()
    return subprocess.call([os.path.join(build, "vector_tb")] + args)


if __name__ == "__main__":
    sys.exit(main())
