# Graph Wiring Failures — real transcripts and fixes

Every entry below is an actual execution error from authoring ComfyUI video
graphs programmatically. They share one root cause: **ComfyUI's generic
types (`MODEL`, `CONDITIONING`, `IMAGE`, `MASK`) accept anything at graph
validation time.** `/prompt` returns 200, then the node dies at execution.

The schema gives you the **type**. The tooltip gives you the **contract**.
Read the tooltip.

---

## 1. Wrong model into a task-specific socket

```
ValueError: The provided model does not have a heatmap_head.
Please use SDPose model from here
https://huggingface.co/Comfy-Org/SDPose/tree/main/checkpoints
```

**Cause.** `SDPoseKeypointExtractor.model` was wired to
`rt_detr_v4-x-hgnet_fp16` (the person *detector*, which emits bounding
boxes) instead of `sdpose_wholebody_fp16` (the *pose* model with the
heatmap head). Both shipped in the same HF repo; both satisfy `MODEL`.

**Fix.** Load the pose checkpoint via `CheckpointLoaderSimple`, which
returns `(MODEL, CLIP, VAE)` — take `model` from output 0 and `vae` from
output 2. The detector belongs on a `bboxes` input, not a `model` input.

**Generalises to:** any pipeline with both a detector and a task model.
Check which one the node actually consumes.

---

## 2. Text encoder dimension mismatch

```
RuntimeError: mat1 and mat2 shapes cannot be multiplied (512x4096 and 1024x256)
```

**Cause.** Wan's umt5 encoder (`CLIPTextEncode` with `type: wan`) produces
**4096-dim** embeddings. `SAM3_VideoTrack.conditioning` expects **1024**.
Both are `CONDITIONING`, so the graph validated.

**Fix.** Do not feed cross-family conditioning. `CLIPLoader` has no `sam3`
type — SAM3 uses its own internal text encoder, so that socket is not for
external embeddings. Seed the tracker a different way (see #3).

**Generalises to:** any `CONDITIONING` crossing a model-family boundary.
The dimensions in the error name the mismatch: first number is what you
supplied, second is what was wanted.

---

## 3. Schema-optional, runtime-required

```
ValueError: Either initial_mask or conditioning must be provided
```

**Cause.** Both inputs are listed `optional` in `/object_info`. The node
rejects having *neither*. Fixing #2 by deleting the bad conditioning
produced this error immediately.

**Fix.** Supply `initial_mask` instead, produced by `SAM3_Detect` seeded
with either `bboxes` or `positive_coords` (JSON pixel points:
`[{"x": 413, "y": 213}]`).

**Generalises to:** "optional" in a ComfyUI schema means "this field may be
omitted", not "this node works without it". Look for either/or validation.

---

## 4. Model file in an unscanned folder

**Symptom.** File downloaded, confirmed on disk, but absent from every
loader's combo list.

**Cause.** SAM3 was placed in `models/detection/` — a folder ComfyUI lists
in `GET /models` but which no loader node reads from for that model type.

**Fix.** `curl $HOST/models` to list scanned folders, then find which
loader actually exposes a sibling model. SAM3 loads via `UNETLoader` from
`diffusion_models/`, alongside `rt_detr`. Restart after moving — model
scans happen at boot.

**Diagnostic.** Walk `/object_info` and print any loader whose combo
options contain your filename. No hits = wrong directory.

---

## 5. Right type, wrong semantics (the expensive one)

**Symptom.** Graph runs. Output is wrong. No error anywhere.

**Cause.** `WanAnimateToVideo.character_mask` takes a plain binary `MASK`.
SCAIL-2's equivalent wants **coloured per-identity** masks from
`SCAIL2ColoredMask`, where palette colour maps each tracked person to their
reference. Both satisfy the type system.

**Consequence.** Four runs and two wrong hypotheses (missing CLIP vision,
then inverted mask polarity) were spent before the real problem surfaced:
wrong node for the task entirely. Neither mask polarity could work because
the *format* was wrong, not the sign.

**Fix.** When a graph runs clean but the output is wrong, suspect node
selection before parameter tuning. Compare against the model's official
template if one exists.

---

## Probing checklist

Before wiring any unfamiliar node:

1. `probe_node_schema.py --node X --raw` — raw JSON, not a summary. A
   pretty-printer shows a COMBO as the literal string `"COMBO"` and hides
   the `options` array you need.
2. Read every tooltip. They carry contracts: "Required for multi-person
   detection", "SCAIL-2 only", "will be downscaled to half the resolution".
3. Check which loader exposes the file you intend to load.
4. If two nodes look interchangeable, find the input one has and the other
   does not — that flag usually names the intended use case.

## Non-wiring gotchas from the same sessions

- **`SaveVideo` output lands under `outputs[node]["images"]`** with
  `animated: true`, not under `"videos"`. Searching only `videos` reports a
  successful run as a failure.
- **Stale logs.** After a failed launch, reading the old log shows the
  previous traceback and looks like a fresh failure. Truncate before launch
  and confirm with `pgrep`.
- **torch too old for `comfy_kitchen`.** Quantized checkpoints need it, and
  it uses PEP 585 builtin generics that older `torch.library.infer_schema`
  rejects with the same `list[int]` ValueError. torch 2.4.1 and 2.6.0 both
  fail; 2.11.0+cu128 works. The instinct to *downgrade* is wrong.
- **Never build the venv with `--system-site-packages` on GPU images.** The
  image's own torch shadows the venv's, pip skips `nvidia-cudnn-cu12` as
  "already satisfied", and tracebacks cite `/usr/local/...` while you think
  you are testing your venv.
