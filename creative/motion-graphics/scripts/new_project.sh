#!/usr/bin/env bash
# new_project.sh — scaffold a motion-graphics project from the skill templates.
# Usage: bash new_project.sh <dir>
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DIR=${1:?usage: new_project.sh <dir>}
[ -e "$DIR/index.html" ] && { echo "$DIR already has index.html; not overwriting"; exit 1; }
mkdir -p "$DIR"/{lib,assets,refs,audio,sfx,docs,out,brand/screenshots}
T="$SKILL/templates"
cp "$T"/index.html "$T"/render.mjs "$T"/sfx.mjs "$T"/music.mjs "$T"/beats.py "$T"/drop.py "$T"/mix.py "$T"/mix.sh \
   "$T"/qc.sh "$T"/qc.py "$T"/formats.sh "$T"/chunks.sh "$T"/poster0.sh "$T"/assets.py "$DIR/"
cp "$T/lib/motion.js" "$DIR/lib/"
cp "$T/STUDIO_RULES.md" "$DIR/STUDIO_RULES.md"
cp "$T/BRIEF.md" "$DIR/docs/BRIEF.md"
cp "$T/facts.md" "$DIR/docs/facts.md"
cp "$T/review_log.md" "$DIR/docs/review_log.md"
printf 'out/\nnode_modules/\n.env\n' > "$DIR/.gitignore"
echo '[]' > "$DIR/cues.json"
cat > "$DIR/sound.json" <<'EOF'
{
  "dur": 6,
  "music": "audio/music.wav",
  "offset": 0,
  "sfx": {},
  "cues": []
}
EOF
echo "scaffolded $DIR"
echo "next: fill docs/BRIEF.md + docs/facts.md -> OK -> edit index.html SCENES -> node render.mjs --stills ... -> --draft -> critique"
