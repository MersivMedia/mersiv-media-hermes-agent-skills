#!/usr/bin/env bash
# mix.sh — combine the silent render with music + SFX, normalise to -14 LUFS, mux to the final MP4.
# Usage: bash mix.sh out/silent.mp4 out/final.mp4 [audio/music.wav] [out/sfx.wav]
# Missing audio files are skipped. Video stream is copied, never re-encoded.
set -euo pipefail
SILENT=$1; FINAL=$2; MUSIC=${3:-audio/music.wav}; SFX=${4:-out/sfx.wav}
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SILENT")
inputs=(); n=0
[ -f "$MUSIC" ] && inputs+=(-i "$MUSIC") && n=$((n+1))
[ -f "$SFX" ] && inputs+=(-i "$SFX") && n=$((n+1))
mkdir -p "$(dirname "$FINAL")"
if [ "$n" -eq 0 ]; then cp "$SILENT" "$FINAL"; echo "no audio, copied silent render"; exit 0; fi
if [ "$n" -eq 2 ]; then
  AF="[1:a]volume=1.0[m];[2:a]volume=0.9[s];[m][s]amix=inputs=2:duration=longest:normalize=0,atrim=0:${DUR},loudnorm=I=-14:TP=-1.5:LRA=11[a]"
else
  AF="[1:a]atrim=0:${DUR},loudnorm=I=-14:TP=-1.5:LRA=11[a]"
fi
ffmpeg -y -loglevel error -i "$SILENT" "${inputs[@]}" -filter_complex "$AF" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart "$FINAL"
echo "wrote $FINAL"
ffmpeg -hide_banner -nostats -i "$FINAL" -af ebur128=framelog=quiet -f null - 2>&1 | grep -E "^\s+I:" | head -1 | sed 's/^ */integrated loudness: /'
