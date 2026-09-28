# Cost vs Replicate, and the resolution ceiling (2026-09-28)

## Per 5 s clip

Replicate prices were read live from the model pages. Pod figures are measured on our H100 at $3.49/hr unless marked est.

| Option | Cost | Notes |
|---|---|---|
| Replicate `minimax/h3` 768P | $0.40 | $0.08/s. Inputs: prompt, reference_video_urls (≤3), reference_image_urls, first_frame_image, duration 4-15, ratio, resolution 768P/2K |
| Replicate `minimax/h3` 2K | $0.65 | $0.13/s. MiniMax's own 2K regen |
| Pod H100 turbo 480p | $0.22 | measured, 3.8 min |
| Pod H100 full 20-step 480p | $0.97 | measured, 16.6 min |
| Pod H100 turbo 768p | ~$0.54-0.86 | est, 2.5x pixels, NOT measured |
| Pod RTX PRO 6000 turbo 768p | ~$0.33-0.51 | est, assumes H100 speed; zero instances when tried |
| Replicate `wan-video/wan-2.2-animate-replace` | $0.10 (480p) / $0.25 (720p) | different model, character only |
| Replicate `kwaivgi/kling-o1` | $0.42-0.84 | prompt-driven editor |
| Replicate `runwayml/gen4-aleph` | $0.90 | prompt-driven editor |

## Fixed costs of the pod

- **Volume:** 270 GB × $0.07 = **$18.90/month**, charged whether or not a pod runs.
- **Each start:** ~$0.32 for boot, ComfyUI cold start and the first model load.
- **Bring-up day:** $6.13 total for 2 clips plus setup.

## Monthly totals (768p Replicate vs pod est)

| Clips | Replicate | Pod 768p | Pod 480p |
|---|---|---|---|
| 10 | $4 | ~$25 | ~$21 |
| 100 | $40 | ~$77 | ~$44 |
| 300 | $120 | ~$192 | ~$94 |

The pod only wins past ~100 clips/month, and only at 480p.

## Why the user keeps the pod anyway

The user's stated reason is uncensored content. That request was **declined for sexual/nude content**: this is a photo-of-a-real-person swap, so it would be a deepfake/NCII pipeline. The policy stays in the Director.

Legitimate pod advantages to offer instead:
- **Mature non-sexual film themes.** Violence, horror, gore, drugs and crime get blocked by hosted filters; Replicate E005 even blocked our own reference close-ups.
- **Privacy.** Footage and faces stay on our own volume.
- **Hands-on control** in the ComfyUI browser UI: seeds, steps, turbo LoRA, SAM3 cutout.

## Resolution ceiling

- **Locally, H3 tops out at 768p** (1344×768 at 16:9). Set `ResolutionSelector` node 115 megapixels to ~0.98; the default of 0.4 gives 864×480.
- **True 2K is H3-Regenerate-2K**, which the model card says is "not yet open-sourced". It is reachable only via the MiniMax Open Platform API (`/video-generation-v2-regeneration`, with Context-IR at `/video-generation-v2-h3-context-ir`) or Replicate `minimax/h3` resolution=2K. Recheck the HF repo `MiniMaxAI/MiniMax-H3` for a release before telling the user it is still closed.
- **Local path to 1080p/2K:** 768p render → **SeedVR2** diffusion video upscaler. Its weights are already on the `comfy-video` volume (`seedvr2`, from earlier projects). Planned as an optional final node. Timing is NOT measured yet.

## Open test

It is unconfirmed whether Replicate `minimax/h3` does true edit mode (keeps the source motion) or only uses the video as loose reference. One $0.40 test with `source.mp4` + `reference_complex` settles it.
