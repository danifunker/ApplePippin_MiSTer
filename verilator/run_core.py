#!/usr/bin/env python3
"""Build and run the pipeline tests of a CPU model.

    python verilator/run_core.py              everything below, DSPPC603
    python verilator/run_core.py --cpu 604    the same for DSPPC604
    python verilator/run_core.py --seeds 100  more random programs
    python verilator/run_core.py --quick      a short run

1. The real chip's integer vectors (the 603e run for DSPPC603, the 604 run
   for DSPPC604), assembled into one program and executed by the pipeline,
   without and with random bus wait states.
2. Its floating-point vectors, the same way.
3. Random floating-point programs (arithmetic, loads, stores, FPSCR
   instructions) with the state fpmodel.py expects after every instruction.
4. Each exception once, with what its handler must find in SRR0, SRR1, DAR
   and DSISR; address translation with every cause of DSI and ISI; the
   update forms, the indexed loads with rD = rB first; and a computation
   that thousands of external and decrementer interrupts must leave
   undisturbed.
5. Random programs in lockstep with dingusppc's interpreter, including
   supervisor instructions, mode switches and exceptions: after every
   instruction the registers and MSR must match, and at the end the memory.
   Then the same with address translation on.
6. The memory port carried across a clock boundary, at several clock
   ratios, with random requests checked against a software memory.

DINGUS=<dingusppc tree> (default ~/.cache/applepippin/dingusppc) is the
lockstep reference's source; MacPPC7300 used dingusppc 3f070249.
"""

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run import DEFAULT_CSV, build_dir   # noqa: E402


def completion_queue(cpu):
    """Whether the CPU is built with its completion queue (its top's default)."""
    top = os.path.join(HERE, "..", "rtl", "DSPPC" + cpu, "DSPPC" + cpu + ".sv")
    return int(re.search(r"parameter int\s+COMPLETION_ALU\s*=\s*(\d+)", open(top).read()).group(1))


def run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cpu", choices=("603", "604"), default="603", help="the CPU model (default 603)")
    ap.add_argument("--seeds", type=int, default=20, help="random programs to run (default 20)")
    ap.add_argument("--count", type=int, default=20000, help="instructions per random program")
    ap.add_argument("--first-seed", type=int, default=1)
    ap.add_argument("--quick", action="store_true", help="4 random programs, one golden pass")
    args = ap.parse_args()
    if args.quick:
        args.seeds = 4

    COMPLETION_QUEUE = completion_queue(args.cpu)
    os.environ["FPMODEL_CPU"] = args.cpu        # progs.py's programs expect this CPU's FPU (fpmodel.py)
    cache = os.path.join(os.path.expanduser("~"), ".cache", "applepippin")
    build = build_dir(args.cpu)
    dingus = os.environ.get("DINGUS") or os.path.join(cache, "dingusppc")
    csv = os.path.abspath(DEFAULT_CSV[args.cpu])
    chip = {"603": "603e", "604": "604"}[args.cpu]
    # the compilers' temporary files go in a directory of this build's own:
    # other WSL sessions working at the same time have deleted files in /tmp
    # under a running g++
    tmp = build.rstrip("/") + "-tmp"
    os.makedirs(tmp, exist_ok=True)
    os.environ["TMPDIR"] = tmp
    refdir = os.path.join(cache, "dingusref")
    progs = os.path.join(build, "progs")
    os.makedirs(progs, exist_ok=True)

    # the reference model, then the test bench linked with it
    r = run(["make", "-s", "-C", os.path.join(HERE, "ref"), "BUILD=" + refdir, "DINGUS=" + dingus])
    if r.returncode:
        print(r.stdout)
        print("building the dingusppc reference failed")
        return 1
    lib = os.path.join(refdir, "libdingusref.a")
    r = run(["make", "-s", "-C", HERE, "core", "BUILD=" + build, "REF_LIB=" + lib, "CPU=" + args.cpu])
    if r.returncode:
        print(r.stdout)
        print("building the test bench failed")
        return 1
    tb = os.path.join(build, "core_ref", "core_tb")

    failures = 0

    def report(label, r):
        nonlocal failures
        lines = r.stdout.strip().splitlines()
        ok = r.returncode == 0
        stats = next((l for l in lines if "cycles per instruction" in l), "")
        print("%-34s %s  %s" % (label, "pass" if ok else "FAIL", stats))
        # the cycle accounting (core_main.cpp print_perf), for the runs without wait states
        if ok and "wait states 0%" in label and "snoop" not in label:
            for i, l in enumerate(lines):
                if l.startswith("perf:"):
                    for p in lines[i + 1:i + 3]:
                        print("    " + p.strip())
        if not ok:
            failures += 1
            for l in lines[-14:]:
                print("    " + l)

    # 1. golden vectors as a program
    golden = os.path.join(progs, "golden.prog")
    r = run([sys.executable, os.path.join(HERE, "progs.py"), "golden", golden, csv])
    if r.returncode:
        print(r.stdout)
        return 1
    print("real-%s integer vectors through the pipeline:" % chip)
    for stall, seed in ((0, 1),) if args.quick else ((0, 1), (25, 2), (60, 3)):
        r = run([tb, "--prog", golden, "--stall", str(stall), "--seed", str(seed)])
        report("  wait states %d%%" % stall, r)
    # under a storm of read snoops: the DMA engine's traffic against the caches' arbitration
    # (the speed session's cache gate took an ungranted request only when a snoop and a
    # request met in one cycle: nothing else here makes that meeting)
    for stall, every, seed in ((0, 2, 5), (30, 3, 6)):
        r = run([tb, "--prog", golden, "--stall", str(stall), "--seed", str(seed), "--snoop-every", str(every)])
        report("  wait states %d%%, a snoop every %d cycles" % (stall, every), r)

    # 2. the floating-point vectors the same way
    goldenfp = os.path.join(progs, "goldenfp.prog")
    r = run([sys.executable, os.path.join(HERE, "progs.py"), "goldenfp", goldenfp, csv])
    if r.returncode:
        print(r.stdout)
        return 1
    print("real-%s floating-point vectors through the pipeline:" % chip)
    for stall, seed in ((0, 1),) if args.quick else ((0, 1), (30, 2)):
        r = run([tb, "--prog", goldenfp, "--stall", str(stall), "--seed", str(seed)])
        report("  wait states %d%%" % stall, r)

    # 3. random floating-point programs, every instruction checked against fpmodel.py
    print("random floating-point programs against the software model:")
    for seed in range(args.first_seed, args.first_seed + max(2, args.seeds // 4)):
        prog = os.path.join(progs, "fprandom.prog")
        r = run([sys.executable, os.path.join(HERE, "progs.py"), "fprandom", prog, str(args.count), str(seed)])
        if r.returncode:
            print(r.stdout)
            return 1
        stall = (0, 20, 50)[seed % 3]
        r = run([tb, "--prog", prog, "--stall", str(stall), "--seed", str(seed)])
        report("  seed %d, wait states %d%%" % (seed, stall), r)

    # 4. exceptions, interrupts and the update forms, with known outcomes
    print("exceptions, interrupts, the update forms:")
    for name, gen, tb_args in (
        ("each exception once", ["exctest"], ["--stall", "10"]),
        ("update forms, rD = rB", ["updtest"], []),
        ("update forms, with wait states", ["updtest"], ["--stall", "40", "--seed", "9"]),
        ("floating-point enabled exceptions", ["fpexctest"], ["--profile"]),
        ("address translation, DSI, ISI", ["mmutest"], ["--stall", "20", "--seed", "5"]),
        ("lwarx/stwcx., dcbz, cache ops", ["resvtest"], ["--stall", "25"]),
        ("caches, cache ops, HID0, DMA", ["cachetest"], ["--stall", "30", "--seed", "7"]),
        ("doubleword cache aliases", ["widecachetest"], []),
        ("doublewords, wait states, snoops", ["widecachetest"], ["--stall", "70", "--seed", "19", "--snoop-every", "3"]),
        ("I/D ownership, held ACK", ["acktest"], ["--lockstep", "--ack-hold", "1"]),
        ("I/D ownership, longer held ACK", ["acktest"], ["--lockstep", "--ack-hold", "4", "--stall", "40", "--seed", "23"]),
        ("doublewords, held ACK, snoops", ["widecachetest"], ["--lockstep", "--ack-hold", "2", "--stall", "30", "--snoop-every", "3"]),
        ("external interrupts", ["irqtest", "3000"], ["--irq-every", "97", "--stall", "10"]),
        ("decrementer interrupts", ["irqtest", "3000"], ["--tb-run"]),
        ("both, with wait states", ["irqtest", "3000"], ["--irq-every", "61", "--tb-run", "--stall", "30"]),
        ("FP operations queued behind EX", ["fpqtest", "2000"], ["--lockstep"]),
        ("the same, interrupts, wait states", ["fpqtest", "2000"], ["--lockstep", "--irq-every", "97", "--tb-run", "--stall", "30", "--seed", "5"]),
        ("overlap queue, external interrupts", ["irqoverlaptest", "3000"], ["--irq-every", "97", "--profile", "--stall", "20"]),
        ("overlap queue, both interrupts", ["irqoverlaptest", "3000"], ["--irq-every", "61", "--tb-run", "--profile", "--stall", "30"]),
        ("interrupts during page walks", ["irqwalktest", "1000"], ["--irq-every", "97", "--stall", "40", "--seed", "11"]),
        ("page walks, both interrupts", ["irqwalktest", "1000"], ["--irq-every", "61", "--tb-run", "--stall", "30", "--seed", "12"]),
        ("cancelled walks that would fault", ["irqwalkfaulttest", "1000"],
         ["--irq-every", "127", "--stall", "70", "--seed", "17", "--profile", "--max-cycles", "2000000"]),
        ("late fault after cancelled walk", ["irqwalkfaulttest", "1000"],
         ["--irq-every", "97", "--stall", "90", "--seed", "11", "--profile", "--max-cycles", "2000000"]),
        ("a walk into the vector's page as a DSI redirects", ["vecwalktest"], ["--lockstep", "--max-cycles", "200000"]),
        ("the same, with wait states", ["vecwalktest"], ["--lockstep", "--stall", "40", "--seed", "3", "--max-cycles", "400000"]),
    ):
        prog = os.path.join(progs, "exc.prog")
        r = run([sys.executable, os.path.join(HERE, "progs.py"), gen[0], prog] + gen[1:])
        if r.returncode:
            print(r.stdout)
            return 1
        r = run([tb, "--prog", prog] + tb_args)
        report("  " + name, r)
        if gen[0] == "irqwalkfaulttest":
            cancels = re.search(r"event walk_cancel\s+(\d+)", r.stdout)
            if not cancels or int(cancels.group(1)) == 0:
                failures += 1
                print("    FAIL: no page-table walk cancellation exercised")
        if gen[0] in ("irqoverlaptest", "fpexctest") and COMPLETION_QUEUE:
            events = dict((k, int(v)) for k, v in re.findall(r"event\s+(\w+)\s+(\d+)", r.stdout))
            if not events.get("overlap_execute", 0):
                failures += 1
                print("    FAIL: no speculative ALU completion exercised")

    # 5. random programs in lockstep, exceptions and supervisor instructions
    #    included; then the same with address translation on (page faults,
    #    protection faults, tlbie, and the page table's R and C bits compared
    #    at the end)
    total = 0
    for xlate in (False, True):
        print("random programs in lockstep with dingusppc%s:" % (", translation on" if xlate else ""))
        seeds = range(args.first_seed, args.first_seed + (max(2, args.seeds // 2) if xlate else args.seeds))
        for seed in seeds:
            prog = os.path.join(progs, "random.prog")
            r = run([sys.executable, os.path.join(HERE, "progs.py"), "random", prog, str(args.count), str(seed)]
                    + (["xlate"] if xlate else []))
            if r.returncode:
                print(r.stdout)
                return 1
            stall = (0, 15, 40, 70)[seed % 4]
            storm = ["--snoop-every", "2"] if seed % 5 == 0 else []   # every fifth under the snoop storm
            r = run([tb, "--prog", prog, "--lockstep", "--stall", str(stall), "--seed", str(seed)] + storm)
            report("  seed %d, wait states %d%%%s" % (seed, stall, ", snooped" if storm else ""), r)
            for l in r.stdout.splitlines():
                if l.endswith("per instruction)"):
                    total += int(l.split()[0])
    # the same body run four times without new fold epochs (no mtsr or icbi),
    # so that the branch target buffer folds its branches into the
    # instructions before them, under the same exceptions and wait states
    print("random programs in lockstep, repeated (folded branches):")
    for seed in range(args.first_seed, args.first_seed + max(2, args.seeds // 2)):
        prog = os.path.join(progs, "random.prog")
        r = run([sys.executable, os.path.join(HERE, "progs.py"), "random", prog, str(args.count), str(seed),
                 "repeat=4", "steady"])
        if r.returncode:
            print(r.stdout)
            return 1
        stall = (0, 15, 40, 70)[seed % 4]
        storm = ["--snoop-every", "2"] if seed % 5 == 0 else []
        r = run([tb, "--prog", prog, "--lockstep", "--stall", str(stall), "--seed", str(seed)] + storm)
        report("  seed %d, wait states %d%%%s" % (seed, stall, ", snooped" if storm else ""), r)
        for l in r.stdout.splitlines():
            if l.endswith("per instruction)"):
                total += int(l.split()[0])
    print("%d random instructions compared" % total)

    # Checked mixes exercise the completion FIFO's simultaneous append/pop,
    # wraparound and younger writes replacing a pending long-unit destination.
    # (the queue is optional, DSPPC604's COMPLETION_QUEUE; without it the
    # mixes still run in lockstep, and nothing is required to overlap)
    r = run([sys.executable, os.path.join(HERE, "perf.py"), "--tb", tb,
             "--out", os.path.join(progs, "perf"), "--loops", "100", "--lockstep"] +
            (["--require-overlap"] if COMPLETION_QUEUE else []))
    report("checked execution-overlap mixes", r)

    # 6. the memory port across two clocks
    r = run(["make", "-s", "-C", HERE, "cdc", "BUILD=" + build, "CPU=" + args.cpu])
    if r.returncode:
        print(r.stdout)
        print("building the clock-crossing bench failed")
        return 1
    print("the memory port across a clock boundary (CPU against memory clock):")
    for pa, pb, label in ((15152, 10000, "66 against 100 MHz"), (15152, 7692, "66 against 130 MHz"),
                          (15152, 15152, "66 against 66 MHz"), (10000, 15152, "100 against 66 MHz")):
        r = run([os.path.join(build, "cdc", "cdc_tb"), "--count", "5000", "--pa", str(pa), "--pb", str(pb),
                 "--stall", "30", "--seed", "3"])
        report("  " + label, r)

    print("\nRESULT: %s" % ("PASS" if failures == 0 else "FAIL (%d runs)" % failures))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
