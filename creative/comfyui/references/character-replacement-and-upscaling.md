# Character Replacement + Upscaling in ComfyUI

Measured on a RunPod L40S (46 GB) in Sept 2026. Every number here came from
an actual run; the failures are real failures, not hypotheticals.

## Ready-to-run scripts

These live in `scripts/` alongside this doc. Copy to the pod and run — they
already encode the wiring order that took four failed runs to get right.

```bash
# one-time model fetch (run on the pod)
bash scail2_fetch.sh        # SCAIL-2 + lightx2v + DPO + relight  (~20 GB)
bash upscaler_fetch.sh      # SeedVR2 7B + its VAE + ESRGAN x3    (~9 GB)

# character replacement
python3 scail2_run.py --source-video src.mp4 --reference-image char.png
python3 scail2_run.py --object-indices "0,2" --sort-by area   # multi-person
python3 scail2_run.py --relight-strength 0.8                  # match lighting
python3 scail2_run.py --save-only /tmp/wf.json                # inspect first

# upscaling — SEPARATE pipeline, run on approved clips only
python3 upscale_run.py --input clip.mp4 --engine seedvr2 --scale 2.0
python3 upscale_run.py --input clip.mp4 --engine esrgan --scale-after 0.5
python3 upscale_run.py --input still.png                      # auto → esrgan

# pose cache — skip re-extraction when reusing motion
python3 pose_library.py add walk.mp4 --name walk_turn_left --tags walk,turn
python3 pose_library.py list
```

`--save-only` dumps the graph JSON without submitting. Use it to verify
wiring before spending GPU minutes.

## Pick the right node FIRST — this is the whole game

Three Wan-family nodes look interchangeable and are not. Choosing wrong cost
four failed runs and several hours before the mistake was spotted.

| Node | Built for | Mask format |
|---|---|---|
| `WanVaceToVideo` | general V2V + image reference | none / control_video |
| `WanAnimateToVideo` | **animate a still** from driving motion | plain binary `character_mask` |
| `WanSCAILToVideo` | **replace a person in video** | **colored per-identity** masks |

`WanSCAILToVideo` has an explicit `replacement_mode` boolean. If the task is
"swap the person in this footage for my character", that is the node. Animate
animates; SCAIL replaces.

**The mask formats are not interchangeable.** Animate wants a binary mask.
SCAIL-2 wants colored masks from `SCAIL2ColoredMask`, where palette colour
encodes which tracked identity maps to which reference. Feeding Animate a
binary mask of the original subject collapsed identity in BOTH polarities —
normal and inverted — because polarity was never the problem.

### SCAIL-2 wiring that works

```
source video ─┬→ pose_video            (RAW frames — SCAIL does its own
              │                         motion extraction, no skeleton)
              ├→ RTDETR_detect(person) → SAM3_Detect → SAM3_VideoTrack
              │                              └→ driving_track_data
reference img ─→ RTDETR_detect(person) → SAM3_Detect → ref_track_data (MASK)
                                                │
                    SCAIL2ColoredMask(replacement_mode=True)
                          ├→ pose_video_mask      (white bg in replace mode)
                          └→ reference_image_mask (black bg in replace mode)
```

Then `WanSCAILToVideo` with both masks, `reference_image`, and
`clip_vision_output` (the model is trained with CLIP vision).

LoRA chain: `lightx2v` step-distill (enables ~8 steps at cfg 1.0) → `DPO`.
Add `relight` only when the character needs to match scene lighting.

`sort_by` on `SCAIL2ColoredMask` picks which identity gets which colour:
`left_to_right` (leftmost by centroid at first appearance), `area` (largest
first), or `none` (SAM3 order). `object_indices` ("0,2") selects which
tracked people to replace. This is the multi-character selection mechanism —
there is no semantic ("the woman in red") option.

## The generic-type trap

ComfyUI validates that a `MODEL` output connects to a `MODEL` input. It does
NOT validate that they are the *same kind* of model. Bad wiring passes graph
validation and explodes mid-execution, often minutes in.

Real failures from one session, all of which looked fine in the schema:

| Wiring | Error at runtime |
|---|---|
| `rt_detr` → `SDPoseKeypointExtractor.model` | "does not have a heatmap_head" |
| umt5 CONDITIONING → `SAM3_VideoTrack` | "mat1 and mat2 shapes cannot be multiplied (512x4096 and 1024x256)" |
| `SAM3_VideoTrack` with neither seed | "Either initial_mask or conditioning must be provided" — **both are schema-optional** |
| `VAEEncode` → Conditioning *and* → Chunk in parallel | "conditioning shape must match latent ... (1,16,37,...) vs (1,17,41,...)" |

Rules that follow:

1. **Schema-optional does not mean runtime-optional.** `SAM3_VideoTrack`
   marks both `initial_mask` and `conditioning` optional but refuses to run
   with neither.
2. **Read the raw JSON, not a formatted dump.** Printing
   `input.required.<field>[0]` on a COMBO gives the string `"COMBO"`; the
   actual values live in `[1]["options"]`. A truncated read reported
   `['C','O','M','B','O']` and led to a wrong conclusion about whether
   `person` was an available class.
3. **Sequential beats parallel when shapes must agree.** Chunking nodes
   change tensor dimensions — anything consuming the chunked latent must be
   built FROM it, not from its parent.
4. **Test each new node cheaply before wiring it into an expensive graph.**

## Model folder placement

ComfyUI only scans known folders. Check with `GET /models`, and confirm a
loader actually lists the file before building a graph around it.

- SAM3 and rt_detr load via **`UNETLoader`** from `models/diffusion_models/`.
  A `models/sam3/` or `models/detection/` folder will not be picked up by
  the loader even if it exists.
- SDPose loads via `CheckpointLoaderSimple` from `models/checkpoints/`.
- Verify: `curl -s HOST:8188/models/diffusion_models`

## Upscaling

Keep upscaling in a **separate script** from generation, so test renders
never pay upscale compute and approved clips can be batched.

| Engine | Model | 832x480 → 1664x960 | Notes |
|---|---|---|---|
| ESRGAN | `4x-UltraSharp` | **220 s** | frame-by-frame, can shimmer on motion |
| SeedVR2 | `seedvr2_7b_sharp_int8_convrot` | slower | temporal chunk/merge, no shimmer |

SeedVR2 nodes ship natively (`SeedVR2Preprocess`, `SeedVR2Conditioning`,
`SeedVR2TemporalChunk`, `SeedVR2TemporalMerge`, `SeedVR2PostProcessing`);
only the weights need downloading, **plus its own VAE**
(`seedvr2_ema_vae_fp16.safetensors`) — the Wan VAE will not do.

SeedVR2 order that works:

```
ImageScale(to target) → SeedVR2Preprocess → VAEEncode
  → SeedVR2TemporalChunk → SeedVR2Conditioning   (chunk BEFORE conditioning)
  → KSamplerAdvanced → SeedVR2TemporalMerge → VAEDecode
  → SeedVR2PostProcessing(color_correction="lab")
```

ESRGAN models have a **fixed** factor (usually 4x). To land on an arbitrary
target, run the model then `ImageScaleBy` — e.g. 4x then 0.5 = net 2x.

## Measured VRAM (L40S 46 GB)

| Workload | Peak |
|---|---|
| Wan VACE / Animate / SCAIL-2 generation | ~33 GB |
| SeedVR2 7B upscale @ 2x | **36.5 GB**, GPU 100%, ~310 W |

**These cannot run concurrently on a 46 GB card.** For parallel generation
and finishing lanes, either use SeedVR2 3B (~3.5 GB weights instead of 8.3)
or move to an 80–96 GB GPU.

## Pod lifecycle gotcha

`/workspace` (the network volume) persists across pod termination. The
container filesystem does NOT. `apt`-installed tools like **ffmpeg vanish on
every redeploy** even though all models and venvs survive. Reinstall it as
part of pod bring-up, or the first `ffprobe` call fails.

## Don't trust pixel metrics for visual judgement

Colour-histogram measurements (e.g. "% teal pixels" as a proxy for whether a
character transferred) are useful for detecting *passthrough* — a near-zero
frame-to-frame difference means nothing was generated. They are poor at
judging whether a replacement looks convincing: they cannot see lighting
adaptation, edge quality, or temporal plausibility.

In one session these metrics ranked SCAIL-2 below an alternative, while the
human reviewing the actual video judged SCAIL-2 clearly best because it had
adapted the character's lighting to the scene. **Use metrics to catch
regressions and to prove something ran; use human review to judge quality.**
