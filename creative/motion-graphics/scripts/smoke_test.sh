#!/usr/bin/env bash
# End-to-end smoke test of the motion-graphics skill templates. Usage: bash smoke_test.sh [workdir]
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
W=${1:-$(mktemp -d)}
bash "$SKILL/scripts/new_project.sh" "$W/film"
cd "$W/film"
node music.mjs --bpm 120 --dur 6 --out audio/music.wav --beats beats.json
echo '[{"t":0.05,"type":"thump"},{"t":0.3,"type":"whoosh"},{"t":3.0,"type":"pop"},{"t":3.5,"type":"click"},{"t":4.0,"type":"tick"},{"t":5.0,"type":"chime"}]' > cues.json
node sfx.mjs cues.json out/sfx.wav --dur 6
node render.mjs --w 540 --h 960 --stills 0.5,1.5,3.5 --outdir out/stills
python3 - <<'EOF'
import struct
for f in ["out/stills/t000.50.png", "out/stills/t003.50.png"]:
    with open(f, "rb") as fh: h = fh.read(24)
    print(f, "png", struct.unpack(">II", h[16:24]))
EOF
node render.mjs --w 540 --h 960 --fps 30 --sub 2 --dur 6 --out out/silent.mp4
bash mix.sh out/silent.mp4 out/final.mp4 audio/music.wav out/sfx.wav
bash qc.sh out/final.mp4 3.1
# determinism: a 1s range rendered twice must produce identical bytes
node render.mjs --w 270 --h 480 --fps 30 --sub 1 --from 3 --to 4 --out out/det_a.mp4 >/dev/null
node render.mjs --w 270 --h 480 --fps 30 --sub 1 --from 3 --to 4 --out out/det_b.mp4 >/dev/null
A=$(ffmpeg -loglevel error -i out/det_a.mp4 -f framemd5 - | grep -v '^#' | md5sum); B=$(ffmpeg -loglevel error -i out/det_b.mp4 -f framemd5 - | grep -v '^#' | md5sum)
[ "$A" = "$B" ] && echo "determinism: identical frames" || { echo "determinism: FRAMES DIFFER"; exit 1; }
# other formats reframe instead of crop
node render.mjs --w 960 --h 540 --stills 3.5 --outdir out/stills_16x9 >/dev/null
node render.mjs --w 540 --h 540 --stills 3.5 --outdir out/stills_1x1 >/dev/null
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels -show_entries format=duration -of compact out/final.mp4
echo "SMOKE OK: $W/film"
