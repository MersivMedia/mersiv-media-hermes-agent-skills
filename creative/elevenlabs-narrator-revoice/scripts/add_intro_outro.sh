#!/bin/bash
# Add [brand] intro+outro to a narrated/voice-changed content-only video.
#
# Usage: add_intro_outro.sh INPUT.mp4 OUTPUT.mp4 [BUMPER.mp4]
#
# Prepends the bumper as intro and appends it again as outro, with 0.5s audio
# fades (out-at-end on intro, in-at-start on outro) so the music doesn't hard-cut
# into/out of narration. Output is always re-encoded (concat filter, not demuxer)
# because input codecs from revoice/voice-change typically don't match the bumper.
#
# Defaults to /tmp/hermes/logos/brand-intro-outro-v4.mp4 if no bumper passed.
# Forces output to 1280x720 @ 24fps ([brand] standard).
set -e

IN="$1"
OUT="$2"
BUMPER="${3:-/tmp/hermes/logos/brand-intro-outro-v4.mp4}"

if [ -z "$IN" ] || [ -z "$OUT" ]; then
  echo "Usage: $0 INPUT.mp4 OUTPUT.mp4 [BUMPER.mp4]" >&2
  exit 1
fi
if [ ! -f "$IN" ] || [ ! -f "$BUMPER" ]; then
  echo "Missing input or bumper" >&2
  exit 1
fi

WORKDIR=$(mktemp -d)
trap "rm -rf $WORKDIR" EXIT

# Probe bumper duration so fade-out lands exactly at the tail
BUMPER_DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$BUMPER")
FADE_END=$(python3 -c "print($BUMPER_DUR - 0.5)")

# Intro: bumper with last 0.5s of audio fading out
ffmpeg -hide_banner -loglevel error -y -i "$BUMPER" \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24" \
  -af "afade=t=out:st=$FADE_END:d=0.5" \
  -c:v libx264 -pix_fmt yuv420p -preset fast -c:a aac -b:a 128k -ar 44100 \
  "$WORKDIR/intro.mp4"

# Outro: bumper with first 0.5s of audio fading in
ffmpeg -hide_banner -loglevel error -y -i "$BUMPER" \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24" \
  -af "afade=t=in:st=0:d=0.5" \
  -c:v libx264 -pix_fmt yuv420p -preset fast -c:a aac -b:a 128k -ar 44100 \
  "$WORKDIR/outro.mp4"

# Concat FILTER (not demuxer) — decodes and re-encodes in one pass.
# Demuxer chokes on NAL/timestamp mismatches between revoice output and bumper.
# setsar=1 must be INSIDE the filtergraph; do NOT add a separate -vf flag here.
ffmpeg -hide_banner -loglevel error -y \
  -i "$WORKDIR/intro.mp4" -i "$IN" -i "$WORKDIR/outro.mp4" \
  -filter_complex "[0:v:0]setsar=1[v0];[1:v:0]setsar=1[v1];[2:v:0]setsar=1[v2];[v0][0:a:0][v1][1:a:0][v2][2:a:0]concat=n=3:v=1:a=1[outv][outa]" \
  -map "[outv]" -map "[outa]" \
  -aspect 1280/720 \
  -c:v libx264 -pix_fmt yuv420p -preset fast \
  -c:a aac -b:a 128k -ar 44100 \
  "$OUT"

OUT_DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT")
echo "✓ $OUT (${OUT_DUR}s)"
