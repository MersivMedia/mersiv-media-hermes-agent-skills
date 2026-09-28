# Character Replacement in Video — Node Selection and Measured Results

Swapping a person in an existing video for a new character, without training
anything. Three Wan-family node families can be wired to *look* like they do
this. Only one is built for it. Picking wrong costs hours and produces
confidently-wrong debugging — this file exists because an entire session was
spent tuning parameters on the wrong node.

Complements `references/wan22-vace-v2v.md` (the verified VACE graph) by
answering the question that comes *before* it: which node family at all.

Measured on a RunPod L40S (48 GB), Sept 2026, 832x480, 77-81 frames, 8 steps.

## Pick the node FIRST

| Node | Built for | `replacement_mode` | Mask format | Multi-identity |
|---|---|---|---|---|
| `WanSCAILToVideo` | **in-video character replacement** | yes, explicit bool | **colored per-identity** | yes, `object_indices` |
| `WanAnimateToVideo` | character *animation* (drive a still with motion) | no | plain binary `character_mask` | no |
| `WanVaceToVideo` | general control/reference conditioning | no | `control_masks` | no |

**If the task is "replace the person in this video", use `WanSCAILToVideo`.**
`SCAIL2ColoredMask` generates both `pose_video_mask` and
`reference_image_mask` from `SAM3_TRACK_DATA`, with `object_indices`
("0,2,3") and `sort_by` for choosing *which* tracked person maps to which
reference. That is a first-class feature, not something to bolt on.

SCAIL-2 also has native chunked long-video support: `previous_frames` +
`previous_frame_count` (trained at 5, on 81-frame chunks) — the built-in
answer to seam drift past ~5 s, which otherwise requires hand-rolled
overlap logic.

### SCAIL-2 required models

Repo `Comfy-Org/SCAIL-2` (ungated). Canonical list at
`docs.comfy.org/tutorials/video/zai/scail2`.

| File | Folder | GB |
|---|---|---|
| `wan2.1_14B_SCAIL_2_fp16` (or `_int8_convrot`) | diffusion_models | 32.8 / 16.7 |
| `wan2.1_SCAIL_2_DPO_lora_bf16` | loras | 1.23 |
| `wan2.1_SCAIL_2_relight_lora_bf16` | loras | 1.23 |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16` | loras | 0.74 |
| `umt5_xxl_fp8_e4m3fn_scaled` | text_encoders | 6.74 |
| `clip_vision_h` | clip_vision | 1.26 |
| `wan_2.1_vae` | vae | 0.25 |
| `sam3.1_multiplex_fp16` | diffusion_models | 1.75 |

`lightx2v` lora lives in `Kijai/WanVideo_comfy` under `Lightx2v/`.
`clip_vision_h` is in `Comfy-Org/Wan_2.1_ComfyUI_repackaged` — **not** the
2.2 repo, which has no `clip_vision` directory at all.

## What a wrong-node run looks like (so you recognise it early)

Four `WanAnimateToVideo` runs against one `WanVaceToVideo` run, identical
inputs: same reference character, same cached pose skeleton, same seed 4242.
Identity = % of frame pixels matching the reference character's two
signature colours. Warping = mean per-pixel change between consecutive
frames, sampled in background-only regions.

| Config | teal | copper | bg brightness | warping |
|---|---|---|---|---|
| VACE, reference_image | **10.22%** | **18.28%** | 71.3 (leaked) | 2.57 |
| Animate + background_video | 2.20% | 0.43% | 142.4 | 9.73 |
| Animate + clip_vision | 2.27% | 0.46% | 146.2 | 10.52 |
| Animate + binary mask | 0.29% | 0.21% | 110.5 | 2.73 |
| Animate + mask INVERTED | 0.00% | 0.01% | 113.8 | 5.87 |

Reference image brightness 74.6; intended target scene ~175.

Read it this way: identity collapsed in **every** Animate configuration and
no input combination recovered it. Adding `clip_vision_output` — the socket
that supposedly encodes the reference — changed nothing (0.43 → 0.46%). Then
*both* polarities of the mask suppressed the character further.

**When a knob that should matter does nothing, and then both directions of a
binary are wrong, the node is wrong.** The parameters are not undertuned.
Stop tuning and re-read what the node is documented to do. Two hypotheses
were burned here (missing CLIP vision, inverted mask polarity) before the
user asked "have we been using SCAIL?" — which was the actual answer.

The mask result has a clean explanation in hindsight: Animate takes a plain
binary mask; SCAIL-2 wants *colored per-identity* masks where hue encodes
which tracked person maps to which reference. Feeding binary where colored
is expected is a format mismatch, not a polarity bug, so neither invert
direction could ever have worked.

Architectural difference worth noting: Animate is single-model (one
`UNETLoader`, one sampler pass). VACE is a dual-expert MoE — high-noise pass
with `return_with_leftover_noise: enable`, then low-noise with
`add_noise: disable` starting at the handoff step.

## Known conditioning behaviours

**VACE `reference_image` conditions the WHOLE frame, not an isolated
subject.** A reference shot in a busy environment drags that environment
into the output: a night-market reference against a warehouse target gave
output brightness 71.3 (tracking the reference) instead of ~175. The same
cause makes backgrounds *warp* — only the subject has a control signal, so
nothing anchors the background across frames (2.57/frame vs 0.36 with a
plain grey reference). Mitigation: segment the reference subject onto
neutral grey before feeding it.

**VACE `control_video` must carry STRUCTURE ONLY.** Feeding raw RGB frames
hands the model a complete photograph of the original person, so it
restyles them and ignores `reference_image` entirely. Feed a pose skeleton
(`SDPoseKeypointExtractor` → `SDPoseDrawKeypoints`), depth, or Canny. This
single change is the difference between "restyled the original person" and
"replaced them", and it is invisible in any success/failure status — the
run succeeds either way.

## Choosing WHICH person (multi-subject footage)

`max_detections: 1` picks highest confidence — arbitrary the moment two
people are in frame, and crowd scenes are exactly where replacement work
gets interesting. Available selectors, all positional rather than semantic:

- `SAM3_Detect.positive_coords` — JSON `[{"x":int,"y":int}]` pixel points
- `SAM3_Detect.bboxes` — explicit `{x,y,width,height}`
- `SAM3_Detect.individual_masks: true` — per-object instead of union
- `SAM3_TrackToMask.object_indices` — `"0,2,3"`, empty = all
- `SCAIL2ColoredMask.object_indices` + `sort_by` — the real answer

For semantic selection ("the one on the left", "the foreground one"), derive
it from keypoints:

```
RTDETR_detect(max_detections=N) → bboxes
  → SDPoseKeypointExtractor(bboxes=...) → per-person keypoints
  → pick by hip x / bbox height / wrist position
  → SAM3_Detect(positive_coords=that point)
```

`SDPoseKeypointExtractor` is **single-person without `bboxes`** — its
tooltip states bboxes are "Required for multi-person detection". The
detector must run first; pose cannot bootstrap its own person-selection.

Seeding a mask from an already-extracted pose skeleton works but is
circular — on genuinely new footage the skeleton does not exist yet. The
detector path above has no such dependency.

## Pose skeleton caching

Pose extraction is deterministic (same input → same skeleton) and costs
~40 s per clip. Extract once, store the skeleton mp4 plus a JSON manifest
(frames, fps, resolution, motion description, tags, source), and reuse it.

Later runs skip straight to reference-image + skeleton → video, and the
motion is byte-identical across shots — which is what makes A/B comparisons
genuinely controlled rather than approximately so.

## Measuring results when you cannot see frames

Decode and compare numerically. Each of these caught a real regression:

```bash
# decode one frame to raw RGB for byte-level comparison
ffmpeg -v error -i clip.mp4 -vf "select=eq(n\,80)" -vframes 1 \
       -f rawvideo -pix_fmt rgb24 -
```

- **Passthrough check** — mean abs pixel diff against the source clip. ~0
  means the graph returned the input unchanged; ~50 means real resynthesis.
  Frame count and codec prove nothing here.
- **Identity** — count pixels matching the reference character's signature
  colours. Get a floor by running the same metric on output where that
  character was absent.
- **Background leak** — output mean brightness against the reference image
  and against the intended target scene. Tracking the reference = leak.
- **Warping** — mean per-pixel change between frames N and N+2 in
  background-only regions (frame edges), reported beside the same metric in
  the subject region. Background should be far *lower* than subject; a ratio
  approaching 1 means the whole frame is churning.

Generate the test character deliberately: saturated, unusual colour
combination, plain backdrop, full figure. That is what makes every count
above meaningful. A muted or naturalistic test character produces numbers
you cannot interpret.

## Pitfalls specific to this node family

- **ComfyUI's generic `MODEL` / `CONDITIONING` types pass graph validation
  regardless of compatibility.** Errors surface only at execution. Four
  separate wiring mistakes in one session came from this: a detector model
  in a pose-estimator's `model` socket ("does not have a heatmap_head"), a
  4096-dim umt5 encoding into SAM3's 1024-dim text path ("mat1 and mat2
  shapes cannot be multiplied (512x4096 and 1024x256)"), a checkpoint placed
  in a model folder ComfyUI does not scan, and an input marked optional in
  the schema but required at runtime. The schema tells you the *type*, not
  the *contract*. Probe each new node cheaply before wiring it into a
  four-minute graph.
- **Schema-optional does not mean runtime-optional.** `SAM3_VideoTrack`
  lists both `initial_mask` and `conditioning` as optional, then refuses to
  run with neither: "Either initial_mask or conditioning must be provided".
- **SAM3 checkpoints load via `UNETLoader`** from `models/diffusion_models/`,
  alongside `rt_detr` — not from a `detection/` or `sam3/` folder. Check
  which loader's combo box actually lists the file.
- **`facebook/sam3` is `gated: manual`** — a human reviews each request, so
  approval can take days. `Comfy-Org/sam3.1` is the same family, ungated,
  and smaller (1.75 GB vs 3.44 GB). Following a 307 redirect on a
  `Comfy-Org/<name>` API lookup can surface a renamed ungated mirror.
- **ComfyUI reports `SaveVideo` output under `outputs[node]["images"]` with
  `animated: true`**, not under `"videos"`. Collecting only `videos`/`gifs`
  makes a successful run look like a failure — verify against
  `/history/<prompt_id>` before believing your own error message.
- **Wan generates at 16 fps natively** (81 frames ≈ 5 s). Generating at 30
  hands the model a frame spacing it never learned. Generate at 16, then
  interpolate for delivery with `RIFE VFI` (`multiplier: 2` → 32 fps), which
  ships in the `ComfyUI-Frame-Interpolation` pack and beats ffmpeg's
  `minterpolate`. Say both numbers out loud in any handover.
- **Hosted t2v models may silently interpolate.** `wan-2.2-t2v-fast` on
  Replicate defaults `interpolate_output: true`, returning 152 frames @ 30fps
  when you requested 81 @ 16. Re-normalise with ffmpeg before feeding a
  frame-count-sensitive node, and note the source clip is then
  interpolated-then-decimated — slightly degraded through no fault of the
  model under test.
