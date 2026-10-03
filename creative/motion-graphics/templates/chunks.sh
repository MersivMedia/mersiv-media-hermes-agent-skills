#!/usr/bin/env bash
# chunks.sh — render a long film in K parallel time chunks, then concat losslessly.
# Usage: bash chunks.sh K out/silent.mp4 [render.mjs args...]   e.g. bash chunks.sh 3 out/silent.mp4 --w 1920 --h 1080 --sub 8 --adaptive
# Only worth it on machines with cores + RAM to spare: each chunk is its own Chromium + ffmpeg.
# On the 2-core / 2 GB Hermes box keep K=1 (one render at a time). The source pipeline used K=3 on a Mac
# for films > 25 s (~20 min for 55 s instead of ~55 min).
set -euo pipefail
K=${1:?K}; OUT=${2:?out}; shift 2
DUR=$(node -e "
const s=require('fs').readFileSync('index.html','utf8'); const m=s.match(/dur:\s*([0-9.]+)/); console.log(m?m[1]:15)")
for a in "$@"; do :; done
TMP=$(mktemp -d "out/chunks.XXXX")
pids=()
for ((i=0; i<K; i++)); do
  FROM=$(python3 -c "print(round($DUR*$i/$K, 4))"); TO=$(python3 -c "print(round($DUR*($i+1)/$K, 4))")
  MOTION_RENDER_SLOTS=$K node render.mjs "$@" --from "$FROM" --to "$TO" --out "$TMP/c$i.mp4" > "$TMP/c$i.log" 2>&1 &
  pids+=($!)
done
fail=0; for p in "${pids[@]}"; do wait "$p" || fail=1; done
[ "$fail" = 0 ] || { echo "a chunk failed; logs in $TMP"; exit 1; }
for ((i=0; i<K; i++)); do echo "file '$PWD/$TMP/c$i.mp4'"; done > "$TMP/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$TMP/list.txt" -c copy -movflags +faststart "$OUT"
ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$OUT" | sed "s|^|$OUT frames: |"
echo "chunk logs kept in $TMP"
