#!/usr/bin/env bash
# poster0.sh — burn the poster frame into frame 0. X, Slack and Discord ignore cover metadata and show frame 0.
# Usage: bash poster0.sh out/final.mp4 out/poster.png out/final_poster.mp4
set -euo pipefail
IN=$1; PNG=$2; OUT=$3
ffmpeg -y -loglevel error -i "$IN" -i "$PNG" -filter_complex "[1:v][0:v]scale2ref[p][v];[v][p]overlay=0:0:enable='eq(n,0)',format=yuv420p[o]" \
  -map "[o]" -map 0:a? -c:v libx264 -crf 16 -preset medium -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -c:a copy -movflags +faststart "$OUT"
echo "wrote $OUT (frame 0 = $PNG)"
