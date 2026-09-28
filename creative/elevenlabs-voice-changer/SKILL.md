---
name: elevenlabs-voice-changer
description: "Convert video/audio narration to ElevenLabs voice (speech-to-speech)."
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos]
required_environment_variables:
  - name: ELEVENLABS_API_KEY
    description: ElevenLabs API key (sk_...)
required_commands:
  - ffmpeg
  - ffprobe
metadata:
  hermes:
    tags: [elevenlabs, voice-changer, speech-to-speech, audio, video, dubbing]
---

# ElevenLabs Voice Changer

Convert the voice in a video (or audio file) to any ElevenLabs voice via the speech-to-speech API. Preserves timing, emotion, and delivery — just changes the voice.

## When to use

- Re-voice a NotebookLM-style podcast/video with a custom character voice
- Apply a branded voice ([character], narrator, etc.) over an existing track
- Quick A/B test of how a video sounds with a different voice

## When to use this vs `elevenlabs-narrator-revoice`

Two skills cover overlapping territory — pick deliberately:

| Need | Use |
|------|-----|
| Preserve original pacing, emotion, laughs, ums — just swap the voice | **This skill** (speech-to-speech) |
| Pristine TTS voice with zero source-audio artifacts (multi-voice source, slideshow content, no lip sync needed) | **`elevenlabs-narrator-revoice`** (STT→TTS) |
| Source has both male + female speakers but you want one voice over the whole thing | **`elevenlabs-narrator-revoice`** — speech-to-speech leaves audible pitch differences between speakers even with `--lock-identity` |
| Need exact timing match to video / lip-sync content | **This skill** |

Empirically on [brand] NotebookLM podcasts: voice-changer (`--lock-identity --pre-pitch -3`) is usable but the female-source bleed-through is detectable; narrator-revoice produces cleaner end-to-end results for that use case but loses the original delivery dynamics.

## Inputs

- A video (mp4) or audio file (mp3/wav/m4a)
- An ElevenLabs voice ID (find via dashboard or `GET /v1/voices`)
- Optional model override (default: `eleven_multilingual_sts_v2`)

## Output

- A new video file with the voice swapped (original video stream + new audio)
- OR if input was audio-only, just the converted audio mp3

## Usage

```bash
# Video → video with new voice
python ~/.hermes/skills/creative/elevenlabs-voice-changer/scripts/voice_change.py \
  /path/to/input.mp4 \
  /path/to/output.mp4 \
  --voice-id 6zTRy4vPhz1hAPsZhT9A

# Audio → audio
python ~/.hermes/skills/creative/elevenlabs-voice-changer/scripts/voice_change.py \
  /path/to/input.mp3 \
  /path/to/output.mp3 \
  --voice-id 6zTRy4vPhz1hAPsZhT9A

# Pre-known voice shortcuts (see VOICES section)
python .../voice_change.py in.mp4 out.mp4 --voice narrator-alt
```

## How it works

1. Extract audio from input (ffmpeg → mono 44.1 kHz mp3)
2. If audio is shorter than the chunk limit (default 270s — **API hard cap is 300s**), POST it as a single request to `/v1/speech-to-speech/{voice_id}`
3. If longer, find silence boundaries with `silencedetect` and split into chunks ≤ chunk-limit, POST each chunk separately, concatenate the returned mp3s
4. If input is video, mux the new audio over the original video stream (no re-encode of video)

## API details

```
POST https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}
Headers:
  xi-api-key: $ELEVENLABS_API_KEY
Form fields:
  audio: <audio file>
  model_id: eleven_multilingual_sts_v2  (default — supports non-English; for pure English use eleven_english_sts_v2)
  remove_background_noise: true|false   (default: false)
Query:
  output_format: mp3_44100_128 (default), mp3_44100_192 (Creator+), pcm_44100, etc.
```

## Pitfalls

- **Run BEFORE adding intro/outro music.** The voice changer model interprets silent music tracks as silence and returns nothing for those sections — you'll get a final video where the intro/outro are mute. Either (a) run voice changer on the content-only video, then prepend/append the intro/outro in a separate step, or (b) if you have to run on a video with intro/outro already attached, use the audio-splice recovery pattern below.

  **Recovery if you already converted a video that had intro/outro attached** — restore original music for those time ranges:
  ```bash
  INTRO_DUR=7.082  # length of intro = length of outro
  SRC=original-with-intro.mp4
  CONVERTED=converted-from-voice-changer.mp4
  TOTAL=$(ffprobe -v error -show_entries format=duration -of csv=p=0 $CONVERTED)
  OUTRO_START=$(python3 -c "print($TOTAL - $INTRO_DUR)")
  ffmpeg -y -i $SRC -i $CONVERTED \
    -filter_complex "\
      [0:a]atrim=0:${INTRO_DUR},asetpts=PTS-STARTPTS[intro_a]; \
      [1:a]atrim=${INTRO_DUR}:${OUTRO_START},asetpts=PTS-STARTPTS[mid_a]; \
      [0:a]atrim=${OUTRO_START}:${TOTAL},asetpts=PTS-STARTPTS[outro_a]; \
      [intro_a][mid_a][outro_a]concat=n=3:v=0:a=1[outa]" \
    -map 1:v -map "[outa]" -c:v copy -c:a aac -b:a 192k -shortest out.mp4
  ```

- **Source pitch bleed-through (female → male target only).** When the source has a female speaker and the target voice is male (or vice versa across a wide pitch gap), the model preserves some of the source pitch contour and the output sits a few semitones off from the target voice's natural range. Two fixes, often combined:
  - `--lock-identity` — sets stability=1.0, style=0.0, similarity_boost=1.0, speaker_boost=on. Cheap, no quality loss, but doesn't fully solve pitch.
  - `--pre-pitch -3` — pitch-shifts source audio DOWN 3 semitones (rubberband) before sending to API. This is much cleaner than post-shifting the output, because the model gets natural-sounding source input and generates naturally. Post-shifting after the fact introduces a vocoder-like "voice changer effect". For female→male target voice conversion, `--pre-pitch -3 --lock-identity` together is the recommended baseline.

  **Do NOT use `--pre-pitch` when the source and target are already in the same vocal range** (e.g. male source → male target). It'll just make the output unnaturally low. The pre-pitch trick is specifically for closing a gender/pitch gap between source and target speakers.
- **API hard cap is 300 seconds per request.** The script defaults to 270s chunks to be safe. A 397s video will be split into 2 chunks; 600s into 3, etc. ElevenLabs docs do NOT make this limit obvious — you only learn it when you get HTTP 400 `audio_too_long`.
- **Long inputs cost a lot.** Voice changer charges per second of input audio at a higher rate than TTS. Test on a short clip first.
- **The chunk boundary matters.** If you split mid-sentence the seam will be audible. The script splits on detected silence; if no silence is found within the chunk window it falls back to a hard cut and inserts 80 ms of silence between chunks.
- **Background noise.** If the source has music or noise, the model tries to preserve it as part of the "performance" and the result can be muddy. Use `--remove-background-noise` to strip it first.
- **Video re-mux only.** The script does NOT re-encode the video stream; it copies it. If your input audio is the same length as your video this works perfectly. If the converted audio is shorter/longer (rare but possible), the video gets padded with silence or truncated to match.
- **Multilingual model is the safer default.** `eleven_multilingual_sts_v2` handles English fine and won't break on accents. Only switch to `eleven_english_sts_v2` if you specifically need it.
- **44.1 kHz mono mp3 input is the sweet spot.** Stereo input is downmixed by the API anyway; sending mono saves bandwidth and avoids phase artifacts.

## Verification

After conversion, check:
- Output duration matches input (`ffprobe -show_entries format=duration -of csv=p=0 output.mp4`)
- Audio stream exists and is not silent (`ffmpeg -i output.mp4 -af volumedetect -f null - 2>&1 | grep mean_volume`)
- Listen to first 10s and last 10s — verifies seams if chunked

## Voice IDs ([brand])

- `6zTRy4vPhz1hAPsZhT9A` — **Narrator Alt** (deep gravelly [character], --voice narrator-alt)
- `TyJfVqGmT0iahaNbUE37` — **Narrator** (older gruff theatrical [character] in his 60s, --voice narrator)

`scripts/voices.json` is **shared with the `elevenlabs-narrator-revoice` skill** — both skills read shortcuts from this file, so add a new voice once and both pipelines pick it up automatically.
