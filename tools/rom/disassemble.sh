#!/bin/sh
# Region-map and disassemble Pippin boot ROMs (data only; no ROM code runs).
#
#   tools/rom/disassemble.sh                 # both known ROMs in ROMs/ -> disasm/, plus the 1.0-vs-Dev diff,
#                                            # then repacks disasm/disasm.tar.xz (the committed copy)
#   tools/rom/disassemble.sh <rom> [outdir]  # one ROM; outdir defaults to disasm/<rom file name stem>
#
# Run tools/rom/setup.sh once first.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PY="$ROOT/scratch/venv/bin/python3"
DETOK="$ROOT/scratch/third_party/fcode-utils/detok/detok"
RUN="$ROOT/tools/rom/run.py"
[ -x "$PY" ] || { echo "missing $PY: run tools/rom/setup.sh" >&2; exit 1; }
[ -x "$DETOK" ] || echo "note: detok not built; FCode images will be hex-dumped only" >&2

if [ $# -ge 1 ]; then
    rom=$1
    stem=$(basename "$rom" | sed 's/\.[Rr][Oo][Mm]$//; s/[^A-Za-z0-9._-]/_/g')
    out=${2:-"$ROOT/disasm/$stem"}
    "$PY" -I "$RUN" "$rom" "$out" --label "$stem" --detok "$DETOK"
    exit 0
fi

R10="$ROOT/ROMs/2BEF21B7 - Bandai Pippin (Kinka 1.0).ROM"
RDEV="$ROOT/ROMs/2BF65931 - Bandai Pippin (Kinka Dev).ROM"
"$PY" -I "$RUN" "$R10" "$ROOT/disasm/kinka-1.0" --label "Kinka 1.0" --detok "$DETOK"
"$PY" -I "$RUN" "$RDEV" "$ROOT/disasm/kinka-dev" --label "Kinka Dev" --detok "$DETOK"
"$PY" -I "$RUN" --diff "$R10" "$RDEV" "$ROOT/disasm/diff-1.0-vs-dev.md" --labels "Kinka 1.0" "Kinka Dev"
python3 -I "$ROOT/tools/rom/pack.py" pack "$ROOT/disasm"
