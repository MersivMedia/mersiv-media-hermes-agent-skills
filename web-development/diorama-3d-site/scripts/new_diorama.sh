#!/usr/bin/env bash
# new_diorama.sh — scaffold a 3D diorama site on the dioramas engine (MIT, pinned commit) + our Replicate pipeline.
# Usage: bash new_diorama.sh <project_dir> <slug>
#   Sparse-clones github.com/blendi-remade/dioramas @ PIN WITHOUT the 310 MB of example models (one 2 MB sample kept
#   for smoke tests), npm installs, then adds examples/<slug>/ from our page template + jobs.json for gen3d.py.
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
PIN=868539fb5b64a843071a2247d5d8bacb706a07b1   # 2026-09-29, MIT; bump deliberately after reading the diff
DIR=${1:?usage: new_diorama.sh <project_dir> <slug>}; SLUG=${2:?slug}
[[ "$SLUG" =~ ^[a-z0-9-]+$ ]] || { echo "slug must be lowercase letters, digits, hyphens"; exit 1; }
if [ ! -d "$DIR/.git" ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/blendi-remade/dioramas "$DIR"
  cd "$DIR"
  git sparse-checkout init --no-cone
  printf '/*\n!/public/models/*\n/public/models/sucre/macaron-lo.glb\n!/docs/media/*\n' > .git/info/sparse-checkout
  git checkout -q "$PIN"
  npm install --no-audit --no-fund --loglevel=error
else
  cd "$DIR"
fi
[ -e "examples/$SLUG" ] && { echo "examples/$SLUG exists; not overwriting"; exit 1; }
mkdir -p "examples/$SLUG" "public/models/$SLUG" "public/img/$SLUG" assets/src assets/raw
cp "$SK/templates/page/"{index.html,main.js,style.css} "examples/$SLUG/"
cp "$SK/templates/optimize-any.mjs" scripts/optimize-any.mjs
sed -i "s/__SLUG__/$SLUG/g" "examples/$SLUG/"*
cp "$SK/templates/jobs.json" "assets/jobs-$SLUG.json"
sed -i "s/__SLUG__/$SLUG/g" "assets/jobs-$SLUG.json"
cp "$SK/templates/BRIEF.md" "docs/briefs/$SLUG.md"
grep -q "^FAL_KEY" .env 2>/dev/null || true
echo "scaffolded $DIR (dioramas @ ${PIN:0:7}) with examples/$SLUG"
echo "next: fill docs/briefs/$SLUG.md -> assets/jobs-$SLUG.json -> python3 $SK/scripts/gen3d.py assets/jobs-$SLUG.json --dry-run"
