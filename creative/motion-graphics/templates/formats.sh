#!/usr/bin/env bash
# formats.sh — render 9:16, 1:1 and 16:9 from the same timeline (scenes must use layout(), not fixed pixels).
# Usage: bash formats.sh [fps] [sub]      -> out/final_9x16.mp4, out/final_1x1.mp4, out/final_16x9.mp4
# Renders run sequentially by default (low-RAM boxes); set PARALLEL=1 to run all three at once.
set -euo pipefail
FPS=${1:-60}; SUB=${2:-4}
declare -A SIZES=([9x16]="1080 1920" [1x1]="1080 1080" [16x9]="1920 1080")
run() { local tag=$1 w h; read -r w h <<<"${SIZES[$tag]}"
  node render.mjs --w "$w" --h "$h" --fps "$FPS" --sub "$SUB" --out "out/silent_${tag}.mp4" \
  && bash mix.sh "out/silent_${tag}.mp4" "out/final_${tag}.mp4"; }
if [ "${PARALLEL:-0}" = 1 ]; then for t in 9x16 1x1 16x9; do run "$t" & done; wait
else for t in 9x16 1x1 16x9; do run "$t"; done; fi
ls -la out/final_*.mp4
