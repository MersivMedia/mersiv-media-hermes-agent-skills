# Preserve-vocals remix — verified run

A real end-to-end run: commercial track, restyled instrumental, original vocal
preserved. 30-second preview cost **~$0.06** and took about five minutes.

## What the user asked for

"Remix this song but keep the original vocals. Trippy bass heavy, heavy drops,
trap vibe."

The initial plan was a rented GPU running YuE2. That was **wrong** — YuE2
regenerates the backing track *and* synthesizes a new singer, so "keep the
original vocals" is impossible by construction. Catching this before renting
saved the pod cost and produced a better result. Always ask the vocal question
first.

## Pipeline

```
1  fetch source            Google Drive (user-supplied file)
2  strip cover art         mjpeg stream breaks stream mapping
3  energy scan             locate the loudest 30s for the preview
4  stem split              htdemucs via triadmusic/stems-separator
5  sum instrumental        bass + drums + other -> one bed
6  restyle                 sakemin/musicgen-remixer, model_version=chord
7  remux                   sidechain-ducked mix + limiter
```

## Step 1 — Google Drive source

Use the existing OAuth credentials rather than asking for a re-upload. Refresh
a token, read metadata, then download with `alt=media`.

```python
import json, os, urllib.request, urllib.parse
data = urllib.parse.urlencode({
    "client_id": os.environ["GOOGLE_CLIENT_ID"],
    "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
    "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
    "grant_type": "refresh_token",
}).encode()
tok = json.load(urllib.request.urlopen(
    "https://oauth2.googleapis.com/token", data))["access_token"]

req = urllib.request.Request(
    f"https://www.googleapis.com/drive/v3/files/{FILE_ID}?fields=name,mimeType,size",
    headers={"Authorization": f"Bearer {tok}"})
print(json.load(urllib.request.urlopen(req)))
```

```bash
curl -s -L -H "Authorization: Bearer $TOK" \
  "https://www.googleapis.com/drive/v3/files/$FID?alt=media" -o src.mp3
```

The file ID is the long segment in `drive.google.com/file/d/<ID>/view`.

## Step 2 — strip cover art

The source had an embedded `mjpeg` artwork stream. Symptoms: `-map` defaults
pick the wrong stream, filters behave oddly, later probes return nothing.

```bash
ffmpeg -hide_banner -v error -i src.mp3 -map 0:a:0 -vn \
  -acodec libmp3lame -ar 44100 -b:a 192k clean.mp3 -y
```

## Step 3 — energy scan

Two failed attempts before this worked, both worth avoiding:

**`astats` reports cumulative averages.** With `metadata=1:reset=240` the
values drifted from 0 dB down through -183 dB monotonically — that is a running
mean, not per-block energy.

**`-v error` suppresses `volumedetect`.** The filter prints at info level, so
the flag hid the exact lines being grepped. Every reading came back empty and
defaulted to -99. Use `-hide_banner`.

```bash
for t in $(seq 0 10 180); do
  v=$(ffmpeg -hide_banner -ss $t -t 10 -i clean.mp3 -af volumedetect -f null - 2>&1 \
      | grep -oP 'mean_volume: \K[-0-9.]+')
  printf "  %3ds  %6s dB\n" "$t" "$v"
done
```

Real output showed a clear peak: intro -23.9 dB rising to -8.6 dB at 70 s.
Preview cut from 68 s.

## Step 4 — stem separation

```bash
curl -s -X POST "https://api.replicate.com/v1/files" \
  -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  -F "content=@preview_src.mp3;type=audio/mpeg"
```

Returns `urls.get` — use that as the model input. Then:

```json
{"version": "171d8e6a...", "input": {
  "audio": "<uploaded-url>", "model_name": "htdemucs", "output_format": "mp3"}}
```

Output is a dict; `guitar` and `piano` come back `null` for most material.

```
bass, drums, other, vocals   populated
guitar, piano                null
```

## Step 5 — sum the instrumental

```bash
ffmpeg -hide_banner -v error -i bass.mp3 -i drums.mp3 -i other.mp3 \
  -filter_complex "amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.95" \
  -acodec libmp3lame -b:a 192k instrumental.mp3 -y
```

`normalize=0` matters — the default divides each input by the input count.

## Step 6 — restyle

```json
{"version": "0b769f28...", "input": {
  "music_input": "<instrumental-url>",
  "prompt": "<detailed production prompt>",
  "model_version": "chord",
  "beat_sync_threshold": 0.75,
  "output_format": "mp3"}}
```

Took **146 s** for 30 seconds of audio.

### Prefer header cap

`Prefer: wait=300` is rejected:

```
{"detail":"Prefer: wait=x header must specify a value between 1 and 60"}
```

Submit async and poll `urls.get` every 6 s instead. The whole poll loop exceeds
the 600 s foreground terminal cap for full tracks, so run it with
`background=true, notify=true`.

## Step 7 — remux

See the filter chain in SKILL.md. Result measured `mean_volume: -15.7 dB`,
`max_volume: -0.7 dB` — loud, no clipping.

## Costs

```
stem separation      ~$0.02
musicgen-remixer     ~$0.04     146s for 30s of audio
                     ------
30s preview          ~$0.06
full 3-minute track  ~$0.35 estimated
```

## What to tell the user about drops

`musicgen-remixer` with `model_version=chord` follows the source progression.
It delivers genuine production change and energy contrast, but not engineered
transitions. A riser into silence into an 808 hit is an ffmpeg post step:
filter sweep, a beat of near-silence, then the drop.

Say this before rendering, not after.
