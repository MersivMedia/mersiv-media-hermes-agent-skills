---
name: elevenlabs-narrator-revoice
description: "Re-narrate a video via STT→TTS: transcribe with Replicate WhisperX, regenerate with ElevenLabs voice."
version: 1.0.0
author: Hermes
license: MIT
platforms: [linux, macos]
required_environment_variables:
  - name: ELEVENLABS_API_KEY
    description: ElevenLabs API key (sk_...)
  - name: REPLICATE_API_TOKEN
    description: Replicate API token (for WhisperX transcription)
required_commands:
  - ffmpeg
  - ffprobe
metadata:
  hermes:
    tags: [elevenlabs, replicate, whisperx, tts, stt, voice-over, narration, dubbing]
---

# ElevenLabs Narrator Revoice

Re-narrate a video by transcribing the original audio (Replicate WhisperX) and regenerating it with a clean ElevenLabs TTS voice. Best for **single-narrator** content (slideshow videos, explainers, vlogs) where lip sync isn't required and audio length flexibility is OK.

## When to use this vs voice changer

| Scenario | Use |
|----------|-----|
| Slideshow / no lip sync, want pristine voice with zero source-voice artifacts | **This skill** (STT→TTS) |
| Lip sync matters, must preserve timing exactly | `elevenlabs-voice-changer` (speech-to-speech) |
| Multi-speaker podcast where each host needs a different voice | Future: extend with speaker diarization |
| Source audio is already clean, just want a different voice with same delivery | `elevenlabs-voice-changer` |

STT→TTS produces a much more natural-sounding result because the TTS model generates from scratch — no source pitch contour, no acoustic bleed-through, no "voice changer" artifacts. The tradeoff: original pacing/emotion/laughs are lost, and final audio length may differ from video length.

## Inputs

- A video (mp4) or audio file
- ElevenLabs voice ID (or shortcut from `elevenlabs-voice-changer/scripts/voices.json`)
- Optional model override (default: `eleven_multilingual_v2`, the recommended quality tier)

## Output

- Re-narrated video with new audio (original video stream preserved)
- Side artifact: `transcript.json` saved alongside (text + segments + word timestamps from WhisperX)

## Usage

**Default for any-length content: chunked TTS with balanced ~2000-char chunks** (the script's default). For a typical 6-min ~6000-char transcript this produces 3 balanced chunks of ~2000 chars each, chained via `previous_request_ids`. This is the empirically-proven sweet spot — see Pitfalls below.

`--use-studio` exists in the script but **requires sales whitelist** on the ElevenLabs account. Self-serve and even paid plans return HTTP 403 `invalid_subscription`. Don't recommend this path to users until they confirm Studio API access. If they have it, Studio renders a single coherent take with zero drift, which is the gold standard.

```bash
# Default workflow: chunked TTS with stretched video to match new audio length
python ~/.hermes/skills/creative/elevenlabs-narrator-revoice/scripts/revoice.py \
  /path/to/input.mp4 \
  /path/to/output.mp4 \
  --voice narrator-alt \
  --stretch-video

# Skip STT and use existing transcript (saves Replicate cost on re-runs)
python .../revoice.py in.mp4 out.mp4 --voice narrator-alt --text-override script.txt --stretch-video

# Only if user confirmed Studio API whitelist
python .../revoice.py in.mp4 out.mp4 --voice narrator-alt --use-studio --stretch-video
```

## End-to-end workflow ([brand] style)

For NotebookLM-source videos with intro/outro music:
1. **Run on a content-only video** (no intro/outro yet) — the script's pipeline replaces all audio
2. **Use `--stretch-video`** so slides linger to match the slower narration pace
3. **Add intro/outro as a separate ffmpeg concat step** AFTER the revoice. Use the bundled helper — it's the proven `edit_video.py` pattern extracted as a standalone script:
   ```bash
   bash ~/.hermes/skills/creative/elevenlabs-narrator-revoice/scripts/add_intro_outro.sh \
     CONTENT.mp4 FINAL.mp4 [BUMPER.mp4]
   ```
   Defaults the bumper to `/tmp/hermes/logos/brand-intro-outro-v4.mp4`, forces 1280x720 @ 24fps, applies 0.5s afade-out/in so music doesn't hard-cut into/out of narration, and uses the concat FILTER (not demuxer) to survive codec mismatches from TTS output. See pitfalls in `creative/notebooklm-brand-edit/SKILL.md` for the underlying reasoning.
4. **Upload final to Drive** via `productivity/google-workspace`

If you only have a video that already includes intro/outro, trim them off first to recover content-only, run revoice, then reassemble. The bumpers are ~7s each, so:
```bash
# Probe total first
TOTAL=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 final.mp4)
CONTENT_END=$(python3 -c "print($TOTAL - 7.0)")
ffmpeg -y -i final.mp4 -ss 7.0 -to $CONTENT_END -c copy content-only.mp4
```
Verify content-only duration matches expected before passing to revoice.

### Batching multiple videos

For a batch (T01-T04 etc.), launch the revoice calls in parallel — each is bounded by Replicate STT (~10s) + ElevenLabs TTS (3 chunks × ~20s) + ffmpeg mux. Three concurrent runs finish in roughly the time of one. After all revoice jobs complete, run `add_intro_outro.sh` per video — these are fast (~30-60s each, ffmpeg-only) and can be sequential or parallel. Use Hermes background processes (`terminal(background=True, notify_on_complete=True)`) per video, NOT shell `&` (the foreground tool rejects backgrounding).

## How it works

1. **Extract audio** from input (ffmpeg → 44.1kHz mp3, stays mono)
2. **Upload to a temp URL** (Replicate API needs a fetchable URL; uses `tmpfiles.org` by default — set `--audio-url` to skip if you have your own host)
3. **POST to Replicate WhisperX** (`victor-upmeet/whisperx`) → returns segments with start/end + word timestamps
4. **Concatenate segments** into clean text, splitting on sentence boundaries to respect TTS char limits
5. **POST chunks to ElevenLabs TTS** with `previous_text`/`next_text` continuity hints
6. **Concat TTS chunks** into a single audio track
7. **Mux over original video**: trim or pad to match video duration (since TTS length differs from source)

## Pitfalls

- **Chunked TTS voice consistency.** Each TTS call is a fresh generation, so voice can drift across chunks or within a chunk on long content. Failure modes observed:
  - **Greedy packing (max=2000 → 4 chunks of 2000+2000+2000+89 chars):** the 89-char tail chunk creates an obvious seam at the end. NEVER let the chunker emit a tiny final fragment.
  - **Chunks too big (~3000+ chars):** voice drifts within a single generation, audible change ~5 min into the audio.
  - **Chunks too small (~1000 chars / 7 chunks):** each new chunk picks a slightly different voice timbre even with `previous_request_ids` chaining. Audible seams every ~30s.
  - **Sweet spot: 3 balanced chunks at ~2000 chars each** for a 6-minute video. Long enough that the model settles into a stable voice within each chunk; short enough that drift can't accumulate; few enough chunks that inter-chunk seams are minimized.
  - **The chunker algorithm matters.** Use `round(len/max_chars)` not `ceil()` to pick N chunks, then balance `len/N` chars per chunk on sentence boundaries with a hard cap of `max_chars × 1.2`. Greedy packing (filling chunk-by-chunk to the limit) gives ugly final-chunk tails. The script's current `chunk_text()` implements this — don't regress to greedy packing.
  - Studio API (`--use-studio`) would be a single coherent render but requires sales whitelist — gated 403 on self-serve and standard paid accounts.
- **TTS audio length will differ from source.** It will be a little shorter or longer because (a) the model speaks at its own natural pace and (b) STT may have dropped filler words. For lip-sync content this won't work — use the voice changer instead. For slideshows it's fine; the script can stretch the video to match (see scene stretching below).
- **TTS character limits.** `eleven_multilingual_v2` allows ~10,000 chars/request; `eleven_v3` is 5,000; Flash/Turbo are 40,000. The script defaults to **2,000 chars/chunk** for voice consistency (not API headroom — see the consistency pitfall above). Override with `--max-chars` only if you really need different.
- **WhisperX needs a public audio URL.** The script uses tmpfiles.org as a temporary anonymous host. If that fails, you can pass `--audio-url <https://...>` and host the audio yourself.
- **WhisperX cold start can be ~30-60s.** First Replicate call on a cold container takes a while; subsequent calls in the same session are much faster.
- **Run BEFORE adding intro/outro music.** Same pitfall as the voice-changer skill — TTS replaces ALL audio including silent intro/outro sections. Always run on a content-only video, then add intro/outro as a separate step. If you ran on a video that already had intro/outro and now they're silent, use the audio-splice recovery pattern from `creative/elevenlabs-voice-changer/SKILL.md` (same ffmpeg `atrim`/`concat` snippet works — splice the original intro/outro audio over the regenerated middle).
- **STT mistakes propagate.** WhisperX is excellent but not perfect. Numbers, company names, jargon get hallucinated occasionally. Read `transcript.json` and patch the text via `--text-override` if needed. Saving cost trick: if you already have a transcript from a prior run, pass `--text-override path/to/transcript.txt` to skip STT entirely on subsequent voice trials.

## Verification

After running, check:
- `transcript.json` exists and the `text` field reads cleanly
- Output duration is close (within ~10-20%) to input duration
- Listen to the first 30s and last 30s — verifies seams between chunks

## Scene stretching (for slideshow content)

When the new narration is longer than the original video (common — most [character] voices are slower than NotebookLM hosts), pass `--stretch-video` to slow every scene proportionally so the total runtime matches the new audio. This re-encodes the video stream with a `setpts` filter — every frame is held longer by the same ratio, so slides linger longer in lockstep. No audio time-stretch artifacts.

```bash
python .../revoice.py in.mp4 out.mp4 --voice narrator-alt --stretch-video
```

Without `--stretch-video` the script falls back to: pad audio with silence if shorter, or freeze-frame the last video frame if audio is longer. For slideshows, prefer `--stretch-video` — the freeze-frame at the end looks unfinished.

## Voice shortcuts

Voice shortcuts (`--voice narrator-alt`) are read from `~/.hermes/skills/creative/elevenlabs-voice-changer/scripts/voices.json` — the same file the voice-changer skill uses. Add new voices there and both skills pick them up automatically. Current shortcuts: `narrator-alt`, `narrator`.

## References

- `references/brand-workflow.md` — [brand] narrator workflow: voice casting, validated parameters, end-to-end pipeline (content-only → revoice → intro/outro concat → Drive upload), cost-saving transcript-reuse trick.
- `scripts/add_intro_outro.sh` — standalone helper to bookend a revoiced content-only video with the brand intro+outro bumper (0.5s afade in/out, concat-filter merge, 1280x720@24fps). Default bumper path: `/tmp/hermes/logos/brand-intro-outro-v4.mp4`.
