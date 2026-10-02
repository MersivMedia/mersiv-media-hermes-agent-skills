#!/usr/bin/env bash
# new_project.sh — scaffold a motion-graphics project from the skill templates.
# Usage: bash new_project.sh <dir>
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DIR=${1:?usage: new_project.sh <dir>}
[ -e "$DIR/index.html" ] && { echo "$DIR already has index.html; not overwriting"; exit 1; }
mkdir -p "$DIR"/{lib,assets,refs,audio,docs,out}
cp "$SKILL/templates/index.html" "$SKILL/templates/render.mjs" "$SKILL/templates/sfx.mjs" "$SKILL/templates/music.mjs" \
   "$SKILL/templates/beats.py" "$SKILL/templates/mix.sh" "$SKILL/templates/qc.sh" "$SKILL/templates/formats.sh" "$DIR/"
cp "$SKILL/templates/lib/motion.js" "$DIR/lib/"
cp "$SKILL/templates/STUDIO_RULES.md" "$DIR/STUDIO_RULES.md"
cp "$SKILL/templates/review_log.md" "$DIR/docs/review_log.md"
printf 'out/\nnode_modules/\n.env\n' > "$DIR/.gitignore"
echo '[]' > "$DIR/cues.json"
echo "scaffolded $DIR"
echo "next: edit index.html SCENES, then: node music.mjs --dur N && node render.mjs --stills 0.5,1,2 && bash qc.sh ..."
