---
name: video-character-replacement
description: Swap a character in video, keeping the original motion.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
prerequisites:
  commands: ["python3", "ffmpeg", "curl"]
metadata:
  hermes:
    tags:
      - character-replacement
      - video-to-video
      - comfyui
      - wan
      - vace
      - pose-transfer
      - segmentation
    related_skills: [comfyui, generative-video-consistency, generated-asset-verification, replicate-api-generation]
    category: creative
---

# Video Character Replacement Skill

Replace the person in a source clip with a different character while keeping
the original motion, timing, and camera. Covers the ComfyUI graph shapes that
work, the conditioning mistake that silently ruins the result, and how to
measure whether a run actually succeeded.

This is the **inference-time** path — no training. If the goal genuinely
needs a trained adapter, that is a different job; try this first, because it
is hours cheaper and does not degrade the base model's motion prior.

## When to Use

- Swap the actor in existing footage for a designed character
- Put a reference-image character into a motion you already have
- Build a reusable motion library and re-skin it with different characters
- Debug a replacement that "restyled the same person" instead of replacing them
- Debug a replacement where the background warps, swims, or leaks

## Prerequisites

- ComfyUI on a GPU with **>=24 GB VRAM** (48 GB comfortable at 832x480).
  For provisioning, load the `comfyui` skill and read
  `references/gpu-pod-ltx25-setup.md`.
- Models: a Wan VACE pair (dual high/low-noise experts) or Wan Animate,
  plus `umt5_xxl` text encoder and `wan_2.1_vae`.
- `ffmpeg` on the **same machine as ComfyUI** — GPU images often ship
  without it (`apt-get install -y ffmpeg`).

## Quick Reference

### The one thing that decides success

**`control_video` must carry STRUCTURE ONLY — never raw RGB frames.**

Feed VACE the source clip's actual pixels and it has a complete photograph of
the original person, so it *restyles* them and ignores your reference. Feed it
a pose skeleton and appearance is stripped, leaving `reference_image` as the
only identity signal.

Measured on an identical prompt/seed, colour-signature of the target
character in the output:

| `control_video` | teal garment | copper hair |
|---|---|---|
| raw RGB frames | 0.00% | 0.27% |
| **pose skeleton** | **10.22%** | **18.28%** |

Same graph, same seed. That is the difference between restyling a person and
replacing one.

### Graph shape that works (VACE)

```
LoadVideo -> GetVideoComponents -> SDPoseKeypointExtractor
                                -> SDPoseDrawKeypoints   (skeleton IMAGE)
                                            |
LoadImage (character) ---------------.      | control_video
                                     v      v
CLIPLoader(umt5, "wan") -> encode -> WanVaceToVideo -> (pos, neg, latent, trim)
                                            |
  high-noise expert -> KSamplerAdvanced [0..boundary, leftover noise = enable]
  low-noise  expert -> KSamplerAdvanced [boundary..end, add_noise = disable]
                                            |
        TrimVideoLatent -> VAEDecode -> RIFE VFI -> CreateVideo -> SaveVideo
```

Wan VACE is a **dual-expert MoE**: both `high_noise` and `low_noise` files are
required. Hand off at roughly half the step count, with
`return_with_leftover_noise: enable` on the first and `add_noise: disable` on
the second. Wire `TrimVideoLatent.trim_amount` to VACE's 4th output — VACE
prepends reference latents that must be trimmed.

### Model selection, measured

| | identity | background leak | warping |
|---|---|---|---|
| VACE + pose skeleton | **best** | leaks from reference | low |
| Wan Animate + background_video | weak | reduced | high |
| Wan Animate + CLIP vision | weak (no change) | reduced | high |
| Wan Animate + character_mask | worst | reduced | **lowest** |

VACE gave the strongest identity transfer in every comparison run. Animate's
`background_video`, `face_video`, `character_mask` and `continue_motion`
inputs are architecturally attractive, but on measured results its identity
transfer was far weaker. **Do not assume the newer model wins — benchmark it
against VACE on your own footage before committing.**

**MiniMax H3 ref2va** is a third path: prompt-driven editing from labelled
reference images and the source video, 24 fps, 4–15 s per pass, ~67 GB of
weights. Label mapping, official weight set, the LoRA task-family trap, length
formula, the in-graph prompt-engine node pattern, RunPod deployment behind an
auth proxy (and the pre-installed-nginx trap), and the content boundary:
`references/minimax-h3-ref2va.md`. Not yet benchmarked against VACE — measure
before choosing.

### Frame rate

Wan is trained at **16 fps**. Generate at 16, then interpolate up as a
finishing step — generating at 30 gives the model spacing it never learned.
Use the `RIFE VFI` node (`ComfyUI-Frame-Interpolation`, install with
`requirements-no-cupy.txt`) rather than ffmpeg `minterpolate`; set
`multiplier: 2` for 32 fps.

## Procedure

1. **Normalize inputs to the model's native geometry.** VACE defaults
   832x480 / 81 frames; Animate defaults length 77. Match exactly so no
   resampling happens inside the graph.

2. **Extract the pose skeleton.** `SDPoseKeypointExtractor` ->
   `SDPoseDrawKeypoints`. Save it — see the pose-library pattern below.

3. **Prepare the reference image.** Full figure, head to feet, facing camera,
   on a plain neutral backdrop if possible (see pitfall 2).

4. **Run one clip** at low steps (8 on distilled) before any batch.

5. **Measure, do not eyeball** — see `references/measuring-replacement-quality.md`.

6. **Interpolate to delivery fps** as the last step.

### Pose library pattern

Pose extraction is deterministic and costs ~40 s per clip, so cache it.
Store skeleton MP4s in a directory with a JSON manifest recording frames,
fps, resolution, a plain-language motion description, and the source clip.
Later runs load the cached skeleton and skip extraction entirely, which also
guarantees byte-identical motion across shots of the same action.

## Pitfalls

1. **Raw RGB as `control_video`.** The defining failure. Symptom: output is
   recognisably the original person in a different style. Fix: pose skeleton,
   depth map, or Canny — never source pixels.

2. **`reference_image` conditions the WHOLE FRAME, not just the subject.**
   A reference shot in a busy environment drags that environment into the
   output *and* destabilises it. Measured with a night-market reference
   against a warehouse target: output brightness 71.3 tracked the
   **reference** (74.6), not the target (175.4); background change-per-frame
   went 0.36 -> 2.57 versus a plain-backdrop reference. Fix: shoot or
   generate references on a neutral backdrop, or segment the subject and
   composite onto flat grey before feeding it in.

3. **ComfyUI's generic types pass validation and fail at execution.**
   `MODEL` and `CONDITIONING` accept anything at queue time, so wiring
   mistakes only surface mid-run. Cost four failed runs in one session.
   Test each new node cheaply before wiring it into an expensive graph.
   Specific traps in `references/comfyui-node-wiring-traps.md`.

4. **`SaveVideo` outputs are reported under `images`, not `videos`.**
   History JSON files them in the `images` list with `animated: true`.
   Collection code that only checks `videos`/`gifs` will report a successful
   run as a failure. Check all three lists.

5. **SDPose is single-person unless given bboxes.** The `bboxes` input is
   documented "Required for multi-person detection." For crowd footage,
   detect people first (`RTDETR_detect`, `max_detections: N`), then feed
   those boxes in for per-person keypoints.

6. **Person selection is positional, not semantic.** `max_detections: 1`
   returns the highest-confidence person, which is arbitrary with two or more
   in frame. `object_indices` selects by index, not meaning. For deliberate
   choice, detect N people, derive per-person keypoints, and pick by an
   explicit rule (leftmost hip x, largest bbox, most central) before seeding
   segmentation.

7. **Chunking long clips introduces seams.** Attention is quadratic in latent
   sequence length, so a 30 s clip cannot be one pass — 481 frames is ~33x the
   attention cost of 81 and OOMs a run already at 33/46 GB. Chunk into
   81-frame segments (~55 s of compute per 1 s of video at 480p/8 steps) and
   expect drift at boundaries. Overlap chunks or use `continue_motion`.

8. **Verify the layer the user actually uses.** A `curl` check passing while
   the user's browser fails means you are testing a different path, not that
   the problem is imaginary. When a UI is reported broken, reproduce through
   the same protocol and client the user has, or ask for the devtools network
   trace instead of re-asserting that the endpoint returns 200.

9. **"Configured" is not "working".** Writing a proxy config and seeing
   `nginx -t` pass is not evidence the proxy serves anything — one session
   reported a login proxy as set up when nothing was listening on the port.
   Test the exact public path (no creds refused, wrong creds refused, right
   creds reach the backend) before reporting it, and say "unverified" until
   then.

10. **Batch approval-gated steps when the user is on a phone.** Every SSH step
    touching secrets or remote config may trigger an approval prompt; four
    timed out in one session and each stalled the build while a $3.49/hr pod
    idled. Group remote work into as few commands as possible, keep secret
    handling in one step, and when a prompt times out, report state plus the
    pod's running cost and offer to stop it rather than waiting silently.

## Verification

- [ ] `control_video` is a skeleton/depth/edge map, NOT source RGB
- [ ] Reference image is full-figure on a neutral backdrop where possible
- [ ] Input geometry matches the model's native frames/resolution
- [ ] Both VACE experts loaded, or single model for Animate
- [ ] `TrimVideoLatent` wired to the conditioning node's trim output
- [ ] Output frame count and fps match expectation (RIFE: n*mult - (mult-1))
- [ ] Identity measured against a same-seed baseline, not eyeballed
- [ ] Background brightness compared against target scene, not reference
- [ ] A side-by-side comparison video was produced and actually delivered
