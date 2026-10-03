#!/usr/bin/env bash
# new_remake.sh — scaffold a frame-locked remake project.
# Usage: bash new_remake.sh <dir> [path/to/reference.mp4]
# Copies the remake engine + the motion-graphics audio/QC tools it reuses (drop.py, mix.py, assets.py, qc.py).
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
MG="$SK/../motion-graphics/templates"
DIR=${1:?usage: new_remake.sh <dir> [reference.mp4]}
[ -e "$DIR/core.js" ] && { echo "$DIR already scaffolded; not overwriting"; exit 1; }
mkdir -p "$DIR"/{ref,shots,assets,audio,sfx,measure,out}
T="$SK/templates"
cp "$T"/core.js "$T"/index.html "$T"/project.json "$T"/remake_render.mjs "$T"/remake_analyze.py "$T"/remake_stub.py \
   "$T"/remake_sync.py "$T"/remake_qa.py "$T"/remake_audio.py "$DIR/"
cp "$T/BRIEF_TEMPLATE.md" "$T/SPEC_TEMPLATE.md" "$DIR/"
cp "$MG/drop.py" "$MG/mix.py" "$MG/assets.py" "$MG/qc.py" "$DIR/"
[ -n "${2:-}" ] && cp "$2" "$DIR/ref/reference.mp4"
printf 'out/\nref/full/\nref/sheet/\nmeasure/\nnode_modules/\n.env\n' > "$DIR/.gitignore"
echo "scaffolded $DIR"
echo "next: edit project.json (fps, size, brand tokens, mark, oldHues) -> python3 remake_analyze.py -> SPEC.md -> groups -> python3 remake_stub.py"
