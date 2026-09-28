# Reference-Locked V2V: Wan 2.2 Fun VACE

A **local, uncensored reference lock**, verified end-to-end: drive a source
clip's motion while substituting a chosen character supplied as a single
reference image. No LoRA, no dataset, no training run.

This is the cheapest structural identity lock in this skill's toolkit — the
character enters as a tensor input the model must honour, rather than as
prompt wording it may ignore. Reach for it before any LoRA training.

**Verified on a RunPod L40S (48 GB), Sept 2026**: 81 frames at 832x480 in
250 s, 33 GB VRAM peak, output confirmed resynthesized (not a passthrough).

## 1. Which models can do this at all

VACE is a **Wan-family architecture**. It does not port across families.
Each row cost real time to establish:

| Model | VACE? | Local weights? |
|---|---|---|
| Wan 2.2 Fun VACE A14B | **yes, native core node** | yes |
| Wan 2.1 VACE 14B | yes | yes |
| Wan 3.0 | no | **NO — API only** |
| LTX-2.5 (22B) | no — uses IC-LoRA instead | yes |
| Seedance 2.x | no | **NO — API only** |

- `WanVaceToVideo` is ComfyUI core, category `model/conditioning/wan/vace`.
  A Wan node whose category starts with `partner/` is a **hosted API node**
  that bills credits and applies content moderation. The names are nearly
  identical (`Wan3ReferenceToVideoApi` vs `WanVaceToVideo`) — **check the
  category, not the name**, before assuming a node runs locally.
- `ali-vilab/VACE-LTX-Video-0.9` exists but targets **LTX-Video 2B 0.9.x**,
  not LTX-2.5's 22B DiT. It will not attach. The VACE paper used LTX-Video-2B
  for speed and Wan-T2V-14B for quality; neither is LTX-2.5.
- Lightricks' reference path for LTX is IC-LoRA
  (`LTXICLoRALoaderModelOnly` + `LTXAddVideoICLoRAGuide`, from the
  `ComfyUI-LTXVideo` custom node pack), not VACE. Published Union Control
  IC-LoRAs target LTX-2.3; Lightricks says most run on 2.5 but to validate.
- `Wan-AI/Wan2.2-VACE-A14B` **does not exist** (404). Real sources:
  `alibaba-pai/Wan2.2-VACE-Fun-A14B`, and the ComfyUI-ready
  `Comfy-Org/Wan_2.2_ComfyUI_Repackaged`.

This extends `references/model-hosting-status.md`: *a ComfyUI node existing
for a model does not mean weights exist*, and now also **a node existing for
a technique does not mean your base model supports it**.

## 2. Files

From `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` (ungated, no token needed):

| File | Dest | Size |
|---|---|---|
| `split_files/diffusion_models/wan2.2_fun_vace_high_noise_14B_fp8_scaled.safetensors` | `diffusion_models/` | 17.35 GB |
| `split_files/diffusion_models/wan2.2_fun_vace_low_noise_14B_fp8_scaled.safetensors` | `diffusion_models/` | 17.35 GB |
| `split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors` | `text_encoders/` | 6.74 GB |
| `split_files/vae/wan_2.1_vae.safetensors` | `vae/` | 0.25 GB |
| **total** | | **~42 GB** |

- **Both experts are mandatory.** VACE Fun A14B is a dual-expert MoE:
  high-noise denoises early steps, low-noise finishes. One half is not a
  working model. Both files are byte-identical in size (17,346,056,104) — a
  free integrity check.
- fp8_scaled, not bf16 — the bf16 pair alone is 69 GB.
- **`wan_2.1_vae`** for the 14B models. `wan2.2_vae` belongs to the 5B TI2V;
  the wrong VAE degrades output silently rather than erroring.
- `CLIPLoader` requires `type: "wan"`.

## 3. The graph

```
LoadVideo -> GetVideoComponents -> images ----------.
LoadImage (character reference) -------------------.|
CLIPLoader(umt5, type=wan) -> CLIPTextEncode(pos)  ||
                           -> CLIPTextEncode(neg)  ||
VAELoader(wan_2.1_vae) ----------------------------++-> WanVaceToVideo
                                    out: positive, negative, latent, trim_latent
                                                         |
   UNETLoader(high) -> ModelSamplingSD3 -> KSamplerAdvanced [0 -> boundary]
                                              add_noise=enable
                                              return_with_leftover_noise=enable
                                                         |
   UNETLoader(low)  -> ModelSamplingSD3 -> KSamplerAdvanced [boundary -> 10000]
                                              add_noise=disable
                                              return_with_leftover_noise=disable
                                                         |
                    TrimVideoLatent(trim_amount = VACE output 3)
                             -> VAEDecode -> CreateVideo(fps=16) -> SaveVideo
```

`WanVaceToVideo` inputs: `control_video` (IMAGE — the driving clip),
`reference_image` (IMAGE — the character), `control_masks` (MASK, optional
region targeting for inpaint-style edits), `strength`, and
`width`/`height`/`length` (defaults 832 / 480 / 81).

**Wire output 3 (`trim_latent`) into `TrimVideoLatent.trim_amount`.** VACE
prepends reference latents that must be trimmed before decode, and the count
is dynamic. Hardcoding it leaves garbage frames at the head of the video.

The dual-expert handoff is the fiddly part and the most likely thing to need
iteration: the high-noise sampler must pass leftover noise
(`return_with_leftover_noise=enable`) and the low-noise sampler must not add
its own (`add_noise=disable`).

## 4. Verified parameters

```
width 832, height 480, length 81
steps 8, boundary 4      # high-noise 0->4, low-noise 4->end
cfg 1.0, shift 8.0
sampler euler, scheduler simple
strength 1.0, fps 16
```

Two dials matter. **`boundary`** — the expert handoff step; wrong placement
gives muddy or smeared motion. **`strength`** — lower it when the control
clip overwhelms the reference character.

## 5. Frame rate: generate at 16, interpolate afterwards

**Wan 2.2 is trained at 16 fps.** 81 frames @ 16 fps is canonical and matches
`WanVaceToVideo`'s defaults. Generating at 24 or 30 hands the model a frame
spacing it never learned and degrades coherence — this is the same
"behavioural limit is tighter than the API limit" pattern as the 4–6s shot
ceiling.

Deliverables should still never ship at 16 fps, and a user will rightly
challenge it. Generate native, interpolate as a post step:

```bash
ffmpeg -i out_16fps.mp4 \
  -filter:v "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p out_30fps.mp4
```

`minterpolate` with motion compensation synthesizes real intermediate frames
rather than duplicating. RIFE or FILM as a ComfyUI node beats it noticeably
when quality matters.

State the native-vs-delivery distinction up front. "16 fps" looks like a
mistake unless you explain that it is the training rate and interpolation is
the deliberate finishing step.

## 6. Input preparation

Normalize to exact target geometry before upload. Resampling inside the graph
adds a failure mode that masks real model problems:

```bash
ffmpeg -i source.mp4 -vf "fps=16,scale=832:480" -frames:v 81 \
  -an -c:v libx264 -crf 16 -pix_fmt yuv420p control_81f.mp4

ffmpeg -i ref.png -vf "scale=832:480:force_original_aspect_ratio=decrease,\
pad=832:480:(ow-iw)/2:(oh-ih)/2:color=gray" ref_832x480.png
```

Both go in `ComfyUI/input/` to appear in the `LoadVideo` / `LoadImage` combos.

**Reference image:** full figure head-to-feet, facing camera, arms relaxed,
plain seamless backdrop, even frontal light — consistent with this skill's
rule that identity locks carry no grade. Background clutter confuses the
reference encoder.

**First control clip:** deliberately boring. Locked-off camera, plain
background, unambiguous full-body motion. Busy footage makes failure
impossible to diagnose, and the first run is a test of the graph, not of
cinematography.

## 7. Prove it is not a passthrough

A V2V graph that silently echoes its input still reports `success`. Frame
count, dimensions and codec prove nothing — same trap as "valid video is not
a valid stream". Compare pixels:

```python
import subprocess
def raw(p):
    return subprocess.run(
        ["ffmpeg","-v","error","-i",p,"-f","rawvideo","-pix_fmt","rgb24","-"],
        capture_output=True).stdout

a, b = raw("frames/ctl_27.png"), raw("frames/out_27.png")
idx = list(range(0, len(a), 997))          # prime-stride sample
print(sum(abs(a[i]-b[i]) for i in idx) / len(idx))
```

**~0 means passthrough (broken).** A working run on a plain control clip
measured **47–51** mean absolute difference across sampled frames.

The tempting ffmpeg one-liner
(`blend=all_mode=difference,signalstats,metadata=print`) returns **empty
strings** in some builds, which reads as "no difference" rather than "no
measurement". Decode and compare bytes instead — per debugging principle 15,
suspect the harness when a measurement looks suspiciously clean.

## 8. Deliver a labelled side-by-side

Never hand back a bare output file. Transfer quality cannot be judged without
the control beside it, and the agent generally cannot see frames:

```bash
ffmpeg -i control_81f.mp4 -i output.mp4 -filter_complex "\
[0:v]drawtext=text='CONTROL (input)':x=12:y=12:fontsize=22:fontcolor=white:\
box=1:boxcolor=black@0.6:boxborderw=6[l];\
[1:v]drawtext=text='VACE OUTPUT':x=12:y=12:fontsize=22:fontcolor=white:\
box=1:boxcolor=black@0.6:boxborderw=6[r];\
[l][r]hstack=inputs=2[v]" -map "[v]" -c:v libx264 -crf 18 sbs.mp4
```

Ship the 30 fps interpolated cut as primary, a half-speed version
(`setpts=2.0*PTS`) for judging identity, and a stacked contact sheet. **Upload
to shared storage and give links** — a path on the agent's box is not a
deliverable, and the user is often on a phone.

Say explicitly that the pipeline is verified mechanically while the visual
result is **unjudged**. Frame counts and pixel deltas prove the graph ran;
they say nothing about whether the character actually transferred.

## 9. Pitfalls

1. **`WanVaceToVideo` is Wan-only.** It cannot drive LTX, Hunyuan, or any
   non-Wan base no matter how well the inputs match.

2. **`partner/` category == hosted API**, with credits and moderation. For
   uncensored local work use only plain-local node categories.

3. **Both MoE experts are required.** Half a dual-expert pair is not a model.
   Downloading only one wastes the transfer and fails at load.

4. **Wrong VAE degrades silently.** 14B needs `wan_2.1_vae`, not `wan2.2_vae`.

5. **`trim_latent` comes from VACE output 3**, never hardcoded.

6. **Replicate's `wan-video/wan-2.2-t2v-fast` defaults
   `interpolate_output=True`.** A request for 81 frames @ 16 fps returns 152
   frames @ 30 fps. Set it false or renormalize before feeding VACE. Verify
   `nb_read_frames` on any remotely generated media — the same
   "assert the returned result, don't assume the request was honoured" rule
   that governs multi-image calls. Note the side effect: a control clip that
   was interpolated then decimated has lost quality that is not VACE's fault.

7. **`ffprobe` is frequently absent on GPU pod images** even where ffmpeg
   Python packages are installed. Pull the file to a machine that has it
   rather than concluding verification is impossible.

8. **ComfyUI caches `/object_info`.** Re-fetch it after downloading models, or
   a stale combo list makes a successful download look like a failure.

9. **A submitted prompt that returns a `prompt_id` is already partly
   validated.** ComfyUI checks node types, links and input ranges before
   queueing, so no 400 on submit means the graph is structurally sound. Use
   that as an early signal instead of waiting the full render to learn the
   wiring was wrong.
