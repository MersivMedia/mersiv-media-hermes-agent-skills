#!/usr/bin/env bash
# optimize.sh — raw Replicate GLBs -> web GLBs (weld, meshopt, WebP textures) with scripts/optimize-any.mjs
# (dioramas' optimize.mjs + meshopt decoder, so already-compressed GLBs work too).
# Usage (from the project dir): bash optimize.sh <slug> [--ratio 1] [--tex 2048] [--q 88]
#   assets/raw/<id>.glb  ->  public/models/<slug>/<id>.glb   (skips up-to-date outputs)
# Budget per page: <= ~45 MB total download, <= 1.6M triangles on screen (dioramas' numbers).
set -euo pipefail
SLUG=${1:?slug}; shift
shopt -s nullglob
n=0
for f in assets/raw/*.glb; do
  id=$(basename "$f" .glb)
  out="public/models/$SLUG/$id.glb"
  if [ -f "$out" ] && [ "$out" -nt "$f" ]; then echo "up to date: $out"; continue; fi
  node scripts/optimize-any.mjs "$f" "$out" "$@"
  n=$((n+1))
done
echo "optimized $n file(s); page total: $(du -ch public/models/$SLUG/*.glb 2>/dev/null | tail -1 | cut -f1)"
