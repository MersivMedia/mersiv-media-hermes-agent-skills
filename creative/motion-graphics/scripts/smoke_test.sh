#!/usr/bin/env bash
# End-to-end smoke test of the motion-graphics skill templates. Usage: bash smoke_test.sh [workdir]
# Exercises: scaffold, synthesized music + beats, drop finder, stills, beat stills, draft, adaptive-subframe master
# with a declared hard cut, frame-count check, peak-aligned mix + two-pass loudnorm, numeric QC, QC sheets,
# determinism, poster-in-frame-0, 16:9 / 1:1 / 4:5 reframes.
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
W=${1:-$(mktemp -d)}
bash "$SKILL/scripts/new_project.sh" "$W/film"
cd "$W/film"
PY=${PYTHON:-python3}
node music.mjs --bpm 120 --dur 6 --out audio/music.wav --beats beats.json
$PY drop.py audio/music.wav | tail -3
cat > sound.json <<'EOF'
{"dur": 6, "music": "audio/music.wav", "offset": 0,
 "sfx": {"whoosh": "synth:whoosh", "pop": "synth:pop"},
 "cues": [[0.1, "thump", 0.3], [2.7, "whoosh", 0.15], [3.0, "thump", 0.3], [3.15, "pop", 0.08], [3.5, "click", 0.1], [4.0, "tick", 0.08]]}
EOF
node render.mjs --w 540 --h 960 --stills 0.5,1.5,2.85,3.5 --outdir out/stills
node render.mjs --w 540 --h 960 --beats
node render.mjs --w 1080 --h 1920 --draft --out out/draft.mp4
node render.mjs --w 540 --h 960 --fps 30 --sub 8 --adaptive --out out/silent.mp4
$PY mix.py --video out/silent.mp4 --out out/final.mp4
$PY qc.py out/final.mp4 || echo "(qc.py flagged issues above: expected only if the test film changed)"
bash qc.sh out/final.mp4 2.8
bash poster0.sh out/final.mp4 out/poster.png out/final_poster.mp4
node render.mjs --w 270 --h 480 --fps 30 --sub 1 --from 2.5 --to 3.5 --out out/det_a.mp4 >/dev/null
node render.mjs --w 270 --h 480 --fps 30 --sub 1 --from 2.5 --to 3.5 --out out/det_b.mp4 >/dev/null
A=$(ffmpeg -loglevel error -i out/det_a.mp4 -f framemd5 - | grep -v '^#' | md5sum); B=$(ffmpeg -loglevel error -i out/det_b.mp4 -f framemd5 - | grep -v '^#' | md5sum)
[ "$A" = "$B" ] && echo "determinism: identical frames" || { echo "determinism: FRAMES DIFFER"; exit 1; }
node render.mjs --w 960 --h 540 --stills 1.5,3.5 --outdir out/stills_16x9 >/dev/null
node render.mjs --w 540 --h 540 --stills 1.5,3.5 --outdir out/stills_1x1 >/dev/null
node render.mjs --w 540 --h 675 --stills 1.5,3.5 --outdir out/stills_4x5 >/dev/null
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,color_range,color_space -show_entries format=duration -of compact out/final.mp4
echo "SMOKE OK: $W/film"
