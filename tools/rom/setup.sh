#!/bin/sh
# One-time setup of the ROM tool dependencies.  Everything goes under scratch/
# (git-ignored); nothing is installed system-wide.
#   - scratch/venv: Python venv with capstone (disassembler engine) and,
#     optionally for cross-checks, Elliot Nunn's tbxi
#   - scratch/third_party/fcode-utils: OpenBIOS FCode tools; detok is built
#   - scratch/third_party/multiversal: only needed to regenerate data/*.tsv
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
S="$ROOT/scratch"
mkdir -p "$S/third_party"
if [ ! -x "$S/venv/bin/python3" ]; then
    python3 -m venv "$S/venv"
fi
"$S/venv/bin/pip" install -q 'capstone==5.0.9' 'tbxi==0.13'
if [ ! -d "$S/third_party/fcode-utils" ]; then
    git clone -q https://github.com/openbios/fcode-utils.git "$S/third_party/fcode-utils"
    git -C "$S/third_party/fcode-utils" checkout -q 6e563ee54aa9f60e538d90eedaa012ae77610344
fi
make -s -C "$S/third_party/fcode-utils/detok"
if [ ! -d "$S/third_party/multiversal" ]; then
    git clone -q https://github.com/autc04/multiversal.git "$S/third_party/multiversal"
    git -C "$S/third_party/multiversal" checkout -q 55b83c5ce9ae0fa2244d1679d30e77dcf5d3a5d9
fi
echo "setup done: $S/venv, $S/third_party/fcode-utils/detok/detok"
