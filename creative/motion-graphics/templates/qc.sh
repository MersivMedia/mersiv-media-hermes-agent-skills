#!/usr/bin/env bash
# qc.sh — the critique kit. Produces the images the agent must LOOK at before calling a render done.
# Usage: bash qc.sh out/final.mp4 [fast_action_time_s]
#   out/contact.png  2 frames/s, 6 across (pacing, variety, dead beats)
#   out/strip.png    12 consecutive frames around a fast action (pops, overlaps, sliding)
#   out/phone.png    1 frame/s at 360 px wide (readability on a phone)
#   out/poster.png   a single hero frame (default: 30% in)
#   out/loop_check.mp4  the film twice back to back (watch the seam)
# Adapted from @0xMovez's course (2026-09-27).
set -euo pipefail
V=$1; T=${2:-}
D=$(dirname "$V")
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
FRAMES=$(python3 -c "import math;print(max(1,math.ceil(float('$DUR')*2)))")
ROWS=$(python3 -c "print(max(1,-(-$FRAMES//6)))")
ffmpeg -y -loglevel error -i "$V" -vf "fps=2,scale=270:-1,tile=6x${ROWS}:padding=4:color=0x222222" -frames:v 1 "$D/contact.png"
[ -z "$T" ] && T=$(python3 -c "print(round(float('$DUR')*0.4,2))")
ffmpeg -y -loglevel error -ss "$(python3 -c "print(max(0,$T-0.1))")" -i "$V" -vf "scale=320:-1,tile=12x1:padding=2" -frames:v 1 "$D/strip.png"
PR=$(python3 -c "import math;print(max(1,math.ceil(float('$DUR')/5)))")
ffmpeg -y -loglevel error -i "$V" -vf "fps=1,scale=360:-1,tile=5x${PR}:padding=4:color=0x222222" -frames:v 1 "$D/phone.png"
ffmpeg -y -loglevel error -ss "$(python3 -c "print(round(float('$DUR')*0.3,2))")" -i "$V" -frames:v 1 "$D/poster.png"
ffmpeg -y -loglevel error -stream_loop 1 -i "$V" -c copy "$D/loop_check.mp4"
# loop seam: first vs last frame difference (0 = identical; only matters for loops)
python3 - "$V" <<'EOF'
import subprocess, sys
v = sys.argv[1]
def frame(args):
    return subprocess.run(["ffmpeg", "-loglevel", "error", *args, "-i", v, "-frames:v", "1", "-vf", "scale=64:-1",
                           "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
a, b = frame([]), frame(["-sseof", "-0.05"])
if a and b and len(a) == len(b):
    print(f"loop seam diff (mean abs, 0-255): {sum(abs(x - y) for x, y in zip(a, b)) / len(a):.1f}")
EOF
echo "QC images in $D: contact.png strip.png phone.png poster.png loop_check.mp4 (duration ${DUR}s)"
