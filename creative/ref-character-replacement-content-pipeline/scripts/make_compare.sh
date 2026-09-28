#!/usr/bin/env bash
# Build a labelled side-by-side: [source | reference (as H3 saw it) | result].
# Usage: make_compare.sh <source.mp4> <reference.png> <result.mp4> <out.mp4>
# Height is normalised to 720 so mismatched inputs line up; the reference still
# is held for the full duration. Audio comes from the RESULT (H3 generates it).
set -euo pipefail
SRC="$1"; REF="$2"; RES="$3"; OUT="$4"
H=720
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$RES")
FONT=$(fc-match -f '%{file}' 'DejaVu Sans:bold' 2>/dev/null || echo /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf)
lab() { echo "drawtext=fontfile=$FONT:text='$1':x=20:y=20:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10"; }
HAS_AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$RES" | head -1)
ffmpeg -v error -y \
  -i "$SRC" -loop 1 -t "$DUR" -i "$REF" -i "$RES" \
  -filter_complex "\
[0:v]scale=-2:$H,setsar=1,fps=24,trim=duration=$DUR,setpts=PTS-STARTPTS,$(lab 'SOURCE')[a];\
[1:v]scale=-2:$H,setsar=1,fps=24,$(lab 'REFERENCE')[b];\
[2:v]scale=-2:$H,setsar=1,fps=24,$(lab 'RESULT')[c];\
[a][b][c]hstack=inputs=3,pad=ceil(iw/2)*2:ceil(ih/2)*2[v]" \
  -map "[v]" ${HAS_AUDIO:+-map 2:a -c:a aac -b:a 160k} \
  -c:v libx264 -crf 18 -pix_fmt yuv420p -t "$DUR" -movflags +faststart "$OUT"
ffprobe -v error -show_entries stream=codec_type,width,height,nb_frames -show_entries format=duration -of compact=p=0 "$OUT"
