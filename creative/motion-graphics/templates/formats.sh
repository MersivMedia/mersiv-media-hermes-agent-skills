#!/usr/bin/env bash
# formats.sh — render several aspect ratios from the same timeline (scenes must use layout(), not fixed pixels).
# Usage: bash formats.sh [render.mjs args...]   -> out/final_<tag>.mp4 for each FORMATS entry
#   FORMATS="9x16 1x1 16x9 4x5" (default "9x16 1x1 16x9"). 4:5 = LinkedIn feed (1080x1350); X takes 16:9 or 1:1.
# Audio: if sound.json exists, mix.py builds out/mix.wav once and it is muxed onto every format.
# Renders are sequential (render.mjs holds a machine-wide lock); reframe type per format, never crop.
set -euo pipefail
declare -A SIZES=([9x16]="1080 1920" [1x1]="1080 1080" [16x9]="1920 1080" [4x5]="1080 1350")
FORMATS=${FORMATS:-"9x16 1x1 16x9"}
[ -f sound.json ] && python3 mix.py
for tag in $FORMATS; do
  read -r w h <<<"${SIZES[$tag]}"
  node render.mjs --w "$w" --h "$h" "$@" --out "out/silent_${tag}.mp4"
  if [ -f out/mix.wav ]; then
    ffmpeg -y -loglevel error -i "out/silent_${tag}.mp4" -i out/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k \
      -shortest -movflags +faststart "out/final_${tag}.mp4"
  else cp "out/silent_${tag}.mp4" "out/final_${tag}.mp4"; fi
done
ls -la out/final_*.mp4
