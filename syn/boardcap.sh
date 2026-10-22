#!/bin/bash
# One capture round on the board (.92, MiSTerss1): put a core, start the trace
# streamer, load the core through the OSD (the mounted disc boots), fetch the
# trace, decode it, and print the CPU capture as a stream (syn/capview.py).
#
#     syn/boardcap.sh RBF NAME [SECONDS]
#
# gives scratch/tr_NAME.bin, .txt and scratch/NAME_stream.txt. SECONDS (default
# 60) is how long the streamer runs; the stall is ~16 s into the boot and the
# capture's drain takes a few ms more.
set -e
cd "$(dirname "$0")/.."
RBF=$1; NAME=$2; SECS=${3:-60}
ROM="scratch/pippin/bandai pippin,19960920 - kinka 1.3,- 3e6b3ee4-a52528e9ce8c.rom"
K="$HOME/Downloads/MiSTerKVMS-0.9.5-linux-x86_64/misterkvms-cli --mister 192.168.99.92"
f() { "$@" 2>&1 | grep -v "WARNING\|session may\|server may\|Identity file\|^\[" || true; }
f python3 syn/mister.py put-core "$RBF"
f python3 syn/mister.py trace-capture "$SECS"
sleep 2
for k in F12 right enter enter; do $K key $k > /dev/null; sleep 1; done
echo "core loading $(date +%T)"
sleep $((SECS + 5))
f ssh -i ~/.ssh/id_rsa root@192.168.99.92 'cat /tmp/trstream.log'
scp -q -i ~/.ssh/id_rsa root@192.168.99.92:/tmp/trace.bin "scratch/tr_$NAME.bin"
python3 syn/mister.py trace --file "scratch/tr_$NAME.bin" > "scratch/tr_$NAME.txt"
echo "records: $(grep -c '' "scratch/tr_$NAME.txt"), cap: $(grep -c ' cap ' "scratch/tr_$NAME.txt")"
python3 syn/capview.py "scratch/tr_$NAME.txt" 0 8192 --rom "$ROM" > "scratch/${NAME}_stream.txt"
wc -l "scratch/${NAME}_stream.txt"
