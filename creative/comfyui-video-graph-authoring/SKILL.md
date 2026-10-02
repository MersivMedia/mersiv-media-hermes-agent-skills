---
name: comfyui-video-graph-authoring
description: Author and debug ComfyUI video graphs via the REST API.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: ["curl", "python3"]
metadata:
  hermes:
    tags:
      - comfyui
      - video-generation
      - workflow-authoring
      - character-replacement
      - debugging
      - wan
      - ltx
    related_skills: [comfyui, generative-video-consistency, generative-media-pipeline-design, seedance-video]
    category: creative
---

# ComfyUI Video Graph Authoring

Build ComfyUI video workflows **programmatically** — emit API-format JSON
from `/object_info`, submit to `/prompt`, poll `/history`, verify the output
numerically. This is the authoring-and-debugging side, distinct from the
`comfyui` skill which covers install, lifecycle, and running workflows that
already exist.

The recurring failure mode is not bad parameters. It is **wiring a plausible
value into a socket that wanted something else**, which passes graph
validation and dies at execution.

## When to Use

- Generating a ComfyUI workflow in code rather than the web UI
- Choosing between video nodes that look interchangeable but are not
- Debugging `mat1 and mat2 shapes cannot be multiplied`, `does not have a
  heatmap_head`, or `Either X or Y must be provided`
- Building an A/B harness that changes one variable per run
- Character replacement, motion transfer, or upscaling pipelines on Wan/LTX

## Prerequisites

- A running ComfyUI server (`curl $HOST/system_stats` returns JSON).
- For rented-GPU setups see `references/gpu-pod-provisioning.md`.
- `ffmpeg`/`ffprobe` locally for verifying outputs. GPU pod images often
  ship without them: `apt-get install -y ffmpeg`.

## Bundled Files

| Path | Use |
|---|---|
| `scripts/probe_node_schema.py` | Dump a node's real types, tooltips, and enum options; find which loader exposes a model file; list scanned model folders |
| `references/character-replacement-node-selection.md` | Measured Wan node comparison (VACE / Animate / SCAIL-2) + full SCAIL-2 wiring and model list |
| `references/graph-wiring-failures.md` | Five wiring failure classes with real error transcripts and fixes |
| `references/gpu-pod-provisioning.md` | RunPod deploy traps, getting a GPU when stock is thin (poll, error meanings, stop-on-failure), container-disk rebuild (no rsync, chmod ignored), basic-auth nginx on RunPod's image, Caddy fallback, idle-cost discipline |

## Quick Reference

### Pick the node before tuning parameters

Node choice dominates every parameter. For Wan character work:

| Node | Built for | `replacement_mode`? |
|---|---|---|
| `WanSCAILToVideo` | **swap a person already in a video** | **Yes** |
| `WanAnimateToVideo` | animate a still reference from motion | No |
| `WanVaceToVideo` | general V2V + reference conditioning | No |

Their schemas look near-identical — all take `reference_image`, a pose
input, a mask. They behave completely differently. Measured comparison and
full SCAIL-2 wiring: `references/character-replacement-node-selection.md`.

### The five wiring failure classes

Full transcripts in `references/graph-wiring-failures.md`. Summary:

| Symptom | Cause |
|---|---|
| `does not have a heatmap_head` | detector model wired where a task model was wanted |
| `mat1 and mat2 shapes cannot be multiplied (512x4096 and 1024x256)` | conditioning from the wrong text encoder (umt5 4096-dim into a 1024-dim path). Same class with SAM3: text encoded by a video model's Qwen3-VL (5120-dim) → `(1x5120 and 1024x256)`. Load SAM3 through `CheckpointLoaderSimple` and use **its own** CLIP output |
| `Either initial_mask or conditioning must be provided` | schema-optional input that is runtime-required |
| model absent from every loader combo | file in a folder ComfyUI does not scan |
| runs but output is wrong | correct types, wrong *semantics* (binary mask where coloured per-identity was wanted) |

`MODEL`, `CONDITIONING`, and `IMAGE` are generic. The schema tells you the
**type**, never the **contract**. Probe before wiring.

### Output collection gotcha

`SaveVideo` results are reported under `outputs[node]["images"]` with
`animated: true` — **not** under `"videos"`. Check every list:

```python
for nd in (entry.get("outputs") or {}).values():
    for key in ("videos", "gifs", "images"):
        for item in nd.get(key) or []:
            ...
```

**Filter history outputs by `type == "output"`.** `/history` also lists the
*loaded* input clip (typed `"input"`, a load-node preview) and temp previews
(`"temp"`), sometimes after the real SaveVideo entry. Taking "the last .mp4"
picked the input clip and crashed an upscale lane with FileNotFound. Also
check the file exists and prefer a filename matching your `filename_prefix`.
Any mock ComfyUI used for tests must emit those extra entries too, or it
hides this bug (it did, through a green 50-check suite).

**Websocket silence is not a dead connection.** A node that waits on an
external API (an LLM prompt node) can be silent for minutes. Treating a 15 s
`recv` timeout as "disconnected" fell back to history polling, which lost
per-node and per-step timings and billed the whole render to that one node.
On timeout, keep waiting; only a real close or error ends the loop.

## How to Run

Probe any node's real contract before wiring it:

```bash
python3 scripts/probe_node_schema.py --host http://127.0.0.1:8188 \
  --node WanSCAILToVideo --raw
```

`--raw` prints the untruncated JSON including enum `options` and tooltips.
A pretty-printed summary will show a COMBO as the literal string `"COMBO"`
and hide the values you need.

## Procedure

1. **Probe every node you intend to wire.** Read the tooltip, not just the
   type. Tooltips carry the contract: "Required for multi-person detection",
   "SCAIL-2 only", "will be downscaled to half resolution".

2. **Emit the graph from a Python builder with a `--save-only` flag.**
   Dump the JSON and assert the critical links before spending GPU time:
   ```
   print(wf["41"]["inputs"]["pose_video"])       # expect the right node id
   print(wf["41"]["inputs"]["replacement_mode"]) # expect True
   ```

3. **Submit and treat a clean accept as a type check only.** `/prompt`
   returning 200 proves types line up. It proves nothing about semantics.

4. **Run long jobs in the background.** A 5s clip can take 4-10 minutes.
   Use `terminal(background=True, notify=True)` — a foreground call will be
   killed mid-run and orphan the job.

5. **Verify the artifact, not the status.** `status: success` does not mean
   the output is right. Probe frame count, dimensions, fps, and whether
   pixels actually changed versus the input.

6. **Change ONE variable per run.** Pin the seed, reuse cached inputs, and
   diff against the previous run. Anything else is unattributable.

7. **Show the user the video.** See the pitfall below — this is not
   optional politeness, it is the only reliable evaluation.

## Pitfalls

1. **Numeric proxies are not quality judgments — surface the artifact.**
   Colour-histogram and pixel-diff metrics can say a generation "lost" while
   a human watching it sees a clean character swap with correctly adapted
   lighting. In one session these metrics nearly argued the user off the
   node that was actually working. Metrics are good for *regression*
   detection (did this change help or hurt?) and useless for *acceptance*
   (is this good?). Always render a labelled side-by-side and deliver it
   before drawing conclusions, and state plainly that the visual call is
   the user's.

2. **Build the comparison video every time, not just the numbers.** If you
   report metrics without the clip, you have made the result unreviewable.
   A labelled N-panel grid (reference / source / each variant, each panel
   captioned with its score) is the deliverable.

3. **Schema-optional can be runtime-required.** Removing a bad input to fix
   one error can trigger "Either A or B must be provided". Read the node's
   validation, not only its input list.

4. **Stale logs read exactly like fresh failures.** After a failed launch,
   reading the old log with `read_file` shows the *previous* traceback.
   Truncate before starting (`: > server.log`) and confirm the process is
   alive with `pgrep` — an empty `pgrep` plus an old traceback means the
   server never started at all.

5. **Check where a model file must live, not where it seems to belong.**
   `GET /models` lists the folders ComfyUI scans. A detector may load via
   `UNETLoader` from `diffusion_models/` even though a `detection/` folder
   exists. If no loader combo lists your file, it is in the wrong directory.

6. **Generated clips rarely match requested frame counts.** Hosted models
   silently interpolate (one returned 152 frames @30fps for a requested
   81 @16fps). Always `ffprobe -count_frames` and renormalise with ffmpeg
   before feeding another model that expects an exact length.

7. **Generate at the model's native fps; interpolate afterwards.** Wan is
   trained at 16fps. Asking for 30 gives it frame spacing it never learned.
   Render at 16, then upsample with RIFE (`RIFE VFI`, in-graph) or
   `minterpolate` as a finishing pass.

8. **Attention cost is quadratic in frame count.** Latent frames are
   `(frames-1)//4 + 1`. Going 81 → 481 frames is ~33x the attention cost and
   ~5.7x VRAM. Long video means chunking, not a bigger `length` value.
   Nodes with `previous_frames` / `continue_motion` handle the seams.

9. **Cache sharing makes reruns look faster than they are.** A rerun that
   changes only one input reuses cached nodes and may finish in half the
   time. Do not quote that as the cost of a fresh run.

10. **UI→API conversion must handle V3 nested dropdowns.** Current core nodes
    (e.g. `SaveVideo.format`) declare `COMFY_DYNAMICCOMBO_V3`: the chosen
    option carries its own sub-inputs, keyed with dots (`format`,
    `format.codec`). A flat converter that walks `widgets_values` against
    top-level inputs only drops them. `/prompt` still accepts the graph, and
    the node fails at **execution**, after a full 16-minute render:
    `SaveVideo.execute() missing 1 required positional argument: 'format'`.
    Recurse into the selected option's `inputs.required` and consume one
    widget value per nested input. Convert against live `/object_info`,
    never a hand-kept widget order. Re-queueing after the fix reuses the
    cache and only re-runs the save.

11. **Every loader is validated before a run, even on branches the current
    settings bypass.** A `LoadImage` default pointing at a missing file fails
    the whole prompt. Default every loader to a file that exists in `input/`.

12. **Two ComfyUI servers on one install** (to run render and upscale as
    separate queues, because one server executes one prompt at a time) each
    need their own `--port`, `--user-directory` and `--temp-directory`.
    Otherwise they share the user DB and temp files. On one GPU, compute is
    time-sliced, so the gain comes only from each lane's idle gaps; measure
    peak VRAM before assuming both fit.

13. **Read the node source before promising a toggle saves compute.** Some
    joint models (MiniMax H3) generate audio in the same latent as video, so
    "audio off" only skips the decode and mux: seconds, not minutes. Use lazy
    inputs (`{"lazy": True}` + `check_lazy_status`) so a skipped branch
    doesn't execute at all.

14. **Test harness for graph code without a GPU:** a small mock server
    serving `/object_info` (the real schemas, including V3 combos),
    validating each submitted prompt's inputs against them, and writing
    fake outputs catches conversion, override and naming bugs for free.
    It can't catch problems specific to the target image (missing binaries,
    nginx, drivers). Say so when reporting it green.

15. **Exported UI workflows carry a stale `widgets_values_named` copy** of each
    node's widgets. ComfyUI never reads it (it uses `widgets_values`), so
    editing the real widgets leaves the old values in the file. A supplied
    workflow's copy kept a third-party NSFW finetune filename and an explicit
    example prompt after both were replaced, and it shipped in a public repo.
    Builder scripts should `n.pop("widgets_values_named", None)` for every
    node, then `assert` banned strings are absent from `json.dumps(wf)`. When
    auditing a workflow, grep the whole JSON, not only the visible fields.

## Verification

- [ ] Every non-obvious node was probed with `--raw` before wiring
- [ ] Graph dumped with `--save-only` and critical links asserted
- [ ] Long runs submitted in the background with notify
- [ ] Output verified with `ffprobe` (frames, dims, fps), not just `status`
- [ ] Output confirmed different from the input (pixel diff, not vibes)
- [ ] Exactly one variable changed versus the comparison run
- [ ] A labelled side-by-side video was produced and delivered
- [ ] Quality verdict left to the user, not asserted from metrics
