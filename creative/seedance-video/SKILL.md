---
name: seedance-video
description: Generate video with audio via Seedance on Replicate.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
prerequisites:
  commands: ["curl", "python3"]
  env: ["REPLICATE_API_TOKEN"]
metadata:
  hermes:
    tags:
      - video-generation
      - seedance
      - bytedance
      - replicate
      - text-to-video
      - image-to-video
      - audio
    related_skills: [replicate-api-generation, generative-video-consistency, comfyui, character-reference-sheet]
    category: creative
---

# Seedance Video Skill

Generate video with synchronized native audio using ByteDance's Seedance
models through the Replicate API. Seedance 2.5 produces up to 30 seconds in a
single pass with joint audio-video generation, multi-shot continuity, and
large multimodal reference sets.

There are **no public weights** for any Seedance model. It is API-only — you
cannot self-host it on a GPU. Any "Seedance ComfyUI" node pack is an API
wrapper that bills a remote service, not a local checkpoint.

## When to Use

- User wants a video clip with matching audio from a text prompt
- User wants character or style consistency across shots via reference images
- User wants lip-sync or audio-driven motion from a reference audio track
- User wants to extend, edit, or restyle an existing video
- User wants first-frame / last-frame controlled interpolation

Use `comfyui` with open-weight models (LTX-2.5, Wan) instead when the work
must run locally, needs custom nodes, or must avoid per-generation billing.
## Character references

Build a `character-reference-sheet` for each character. Use the **full panel sheet** (`sheet.jpg`, `~/.hermes/data/character-reference-sheet/<slug>/`, `manifest.json` → `video_ref`) as the character reference, one image per character. With several characters, pass one sheet each; that fits inside seedance-2.0's 9-image cap with room for scene references. Put `identity_text` in the prompt. Whether panel labels or borders ever leak into renders hasn't been measured: check the first frames, and if they do, fall back to the individual plates (`top_refs["9"]`).

## Prerequisites

`REPLICATE_API_TOKEN` must be set. Get one at https://replicate.com/account/api-tokens.

```bash
export REPLICATE_API_TOKEN="r8_..."
```

## Quick Reference

| Model | Replicate ID | Notes |
|---|---|---|
| Seedance 2.5 | `bytedance/seedance-2.5` | Flagship. 30s, native audio, 30 ref images |
| Seedance 2.0 | `bytedance/seedance-2.0` | Prior gen, native audio |
| Seedance 1 Pro | `bytedance/seedance-1-pro` | 5s/10s, no native audio |
| Seedance 1 Lite | `bytedance/seedance-1-lite` | Cheaper 5s/10s tier |

These are **official** Replicate models — do NOT pin a version hash. Pinning
one on an official model causes a 422. (Community models are the opposite:
they require a hash.)

### Seedance 2.5 inputs (verified live from the API schema)

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | string | `""` | Optional if a media input is given. Prefers detailed "production brief" style |
| `image` | uri | none | First frame for I2V |
| `last_frame_image` | uri | none | Requires `image`. Not combinable with references |
| `reference_images` | uri[] | `[]` | Up to 30. Cite as `[Image1]`, `[Image2]` in prompt |
| `reference_videos` | uri[] | `[]` | Up to 10, combined <=30s. Motion transfer, edit, extend. Cite as `[Video1]` |
| `reference_audios` | uri[] | `[]` | Up to 10, combined <=30s. Needs >=1 ref image/video. Cite as `[Audio1]` |
| `duration` | int | `5` | 1-30, or `-1` for model-chosen. Editing mode REQUIRES `-1` |
| `resolution` | enum | `720p` | **Only `480p` or `720p`** — 1080p is not offered on Replicate despite marketing copy |
| `aspect_ratio` | enum | `16:9` | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive` |
| `generate_audio` | bool | `true` | Dialogue (use double quotes in prompt), SFX, music |
| `output_format` | enum | `mp4` | `mp4` or `mov` |
| `watermark` | bool | `false` | |
| `seed` | int | none | Reproducibility is not guaranteed even when set |

Output is a single URI string pointing at the generated video.

## How to Run

Use `scripts/seedance.py` — it submits, polls, and downloads in one step.

```bash
# Text to video with audio
python3 scripts/seedance.py \
  --prompt 'A lighthouse keeper climbs a spiral staircase at dawn. Waves crash below.' \
  --duration 10 --resolution 720p --aspect-ratio 21:9 \
  --output-dir ./outputs

# Image to video
python3 scripts/seedance.py \
  --prompt "The camera slowly pushes in as she turns toward the window" \
  --image ./portrait.png --duration 5

# Character consistency across shots
python3 scripts/seedance.py \
  --prompt "[Image1] walks through a neon-lit market, then [Image1] stops at a food stall" \
  --reference-image ./hero_front.png --reference-image ./hero_side.png \
  --duration 15

# Silent output
python3 scripts/seedance.py --prompt "aerial over dunes" --no-audio
```

Always run ONE clip before any batch — these bill per generation.

## Procedure

1. **Confirm the model exists and read its live schema.** Never trust a
   remembered parameter list; Replicate changes them.
   ```bash
   curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
     https://api.replicate.com/v1/models/bytedance/seedance-2.5
   ```
   Use `curl`, not Python `urllib` — Replicate returns 403 to some default
   user agents.

2. **Write a production-brief prompt.** Seedance 2.5 rewards structure over
   keyword soup. Cover: subject and action, camera move, lighting, setting,
   mood, and any spoken line in double quotes. Timestamp cues like
   `[0:00-0:05]` work for multi-shot direction.

3. **Single test generation.** Check motion, audio sync, and whether
   references were honored before spending on a batch.

4. **Scale up** only after the test reads correctly.

## Pitfalls

1. **No weights exist.** Seedance cannot run locally on any GPU. If the goal
   is local generation, switch to LTX-2.5 or Wan via `comfyui`.

2. **Official models reject version hashes.** Send `{"input": {...}}` to
   `/v1/models/bytedance/seedance-2.5/predictions` with no `version` field.

3. **Resolution caps at 720p here.** Marketing pages cite 1080p/4K for the
   Seedance family; the Replicate enum offers only `480p` and `720p`. Verify
   the enum live rather than promising a client 1080p.

4. **References and frame control are mutually exclusive.** `reference_images`
   cannot combine with `image` / `last_frame_image`.

5. **Reference audio needs visual context.** `reference_audios` requires at
   least one reference image or video, or the request fails.

6. **Editing mode needs `duration: -1`.** Any explicit duration in editing
   mode is rejected.

7. **Seeds are not reliably reproducible.** Do not promise deterministic
   reruns. For consistency across shots, use `reference_images` instead.

8. **Inputs must be reachable URLs or data URIs.** Local paths are not
   uploaded automatically; the script converts local files to data URIs.

9. **Cost is per generation and scales with duration.** A 30s 720p clip costs
   far more than a 5s test. Estimate before batching.

10. **Generation is SLOW — budget ~10 minutes for a 5s clip.** A verified
    5s 720p 21:9 run took `predict_time` 608s. A naive foreground call will
    blow past most tool/shell timeouts. Run the script with
    `terminal(background=True, notify=True)`, or submit and poll separately.

11. **Recover an orphaned prediction instead of resubmitting.** If the poller
    dies, the prediction keeps running server-side — resubmitting bills you
    twice. List recent predictions and resume by ID:
    ```bash
    curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
      "https://api.replicate.com/v1/predictions?limit=5"
    curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
      "https://api.replicate.com/v1/predictions/<id>"
    ```

## Verification

- [ ] `curl` on the model endpoint returns HTTP 200
- [ ] `REPLICATE_API_TOKEN` is set and not echoed into logs
- [ ] A single 5s test clip downloads and plays
- [ ] Audio is present when `generate_audio` is true
- [ ] Reference images are visibly honored before running a batch
