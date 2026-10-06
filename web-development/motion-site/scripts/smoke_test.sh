#!/usr/bin/env bash
# smoke_test.sh — free end-to-end test (no Replicate spend): scaffold -> synthetic clips (ffmpeg) -> frames.py ->
# gen.py --dry-run -> qa.mjs (desktop + mobile screenshots, scrub check, console errors).
# Usage: bash smoke_test.sh [workdir]
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
W=${1:-$(mktemp -d)}
bash "$SK/scripts/new_site.sh" "$W/site"
cd "$W/site"
# synthetic "generated" clips: moving gradients with a drifting object, one per video section in site.json
i=0
for sec in hero craft pour; do
  i=$((i+1))
  ffmpeg -v error -y -f lavfi -i "gradients=s=1280x720:d=5:r=24:speed=0.02:c0=0x2a160a:c1=0xe8a24a:seed=$i" \
    -f lavfi -i "color=c=0xf4ede4:s=180x180:d=5:r=24" \
    -filter_complex "[1:v]format=rgba,geq=lum='lum(X,Y)':a='if(lt(hypot(X-90,Y-90),88),255,0)'[dot];[0:v][dot]overlay=x='200+t*150':y='270+sin(t*2)*60':shortest=1,format=yuv420p" \
    -c:v libx264 -crf 22 "assets/clips/$sec.mp4"
done
python3 "$SK/scripts/frames.py" . --max-frames 72
python3 "$SK/scripts/gen.py" plan.json --dry-run | tail -4
node "$SK/scripts/qa.mjs" . --stops 0.05,0.5,0.95
echo "SITE SMOKE DONE: $W/site"
