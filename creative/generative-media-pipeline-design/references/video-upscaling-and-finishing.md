# Video Upscaling and Finishing

The **finishing** layer: taking an approved clip from generation resolution to
delivery resolution. Measured on a RunPod L40S (46 GB), ComfyUI, Sept 2026.

Generation models have a native resolution they were trained at (Wan 2.2 at
832x480, 16 fps). Fighting that in the generation graph costs quality. Upscale
and interpolate as **separate finishing passes** instead.

## 1. Keep finishing in its own script

Not a flag on the generation script. Three reasons, in order of weight:

1. **Test renders should not pay upscale compute.** Most generation runs are
   experiments you will throw away. An inline upscale taxes every one of them.
2. **Approval is a human step.** The user watches the clip, then decides it is
   worth finishing. That decision point is a natural process boundary.
3. **Batching.** Approved clips accumulate; finishing them as a batch is a
   different job shape from generating one clip.

The user asked for this explicitly: *"standalone so we can run generations at
the same time."* Note the second half is a **separate claim** from the first —
see §5, it does not hold on a 46 GB card.

## 2. Two engines, different jobs

| Engine | Model | 832x480 -> 1664x960, 161f | Temporal |
|---|---|---|---|
| ESRGAN | `4x-UltraSharp.pth` | **220 s** | none — frame by frame |
| SeedVR2 | `seedvr2_7b_sharp_int8_convrot` | **461 s** | chunk/merge |

ESRGAN-family models are fast and good on static detail, but each frame is
upscaled in isolation, so fine texture on a moving subject can crawl or
shimmer between frames. SeedVR2 is a diffusion upscaler that processes with
awareness of neighbouring frames, which is what suppresses that shimmer.

Practical split: **ESRGAN as the default**, SeedVR2 for hero shots where a
moving subject holds the frame. Roughly 2x the time for temporal stability.

ESRGAN models have a **fixed** factor (usually 4x). To land on an arbitrary
target, run the model then rescale: 4x then `ImageScaleBy 0.5` = net 2x.

## 3. SeedVR2 wiring

The nodes ship **natively** with ComfyUI (`SeedVR2Preprocess`,
`SeedVR2Conditioning`, `SeedVR2TemporalChunk`, `SeedVR2TemporalMerge`,
`SeedVR2PostProcessing`). Only weights need downloading, from
`Comfy-Org/SeedVR2` — **including its own VAE**:

```
diffusion_models/seedvr2_7b_sharp_int8_convrot.safetensors   8.33 GB
vae/seedvr2_ema_vae_fp16.safetensors                         0.50 GB
```

A Wan or LTX VAE will not substitute. The 3B variants are ~3.4 GB if the 7B
does not fit.

Working order:

```
ImageScale(to TARGET size) -> SeedVR2Preprocess -> VAEEncode
  -> SeedVR2TemporalChunk -> SeedVR2Conditioning
  -> KSamplerAdvanced(cfg 1.0, euler/simple)
  -> SeedVR2TemporalMerge -> VAEDecode
  -> SeedVR2PostProcessing(color_correction="lab")
```

Two things that are easy to get wrong:

**Pre-resize to the target.** SeedVR2 refines detail *at* the output
resolution; it does not do the scaling itself. Feed it frames already at
1664x960.

**Chunk BEFORE conditioning.** Branching both `SeedVR2Conditioning` and
`SeedVR2TemporalChunk` off `VAEEncode` in parallel looks natural and fails:

```
ValueError: SeedVR2 conditioning shape must match latent batch/temporal/
spatial dimensions; got latent (1,16,37,120,208) and
conditioning (1,17,41,120,208)
```

The chunker changes the temporal dimension (41 -> 37). Anything the sampler
consumes alongside the chunked latent must be built **from** the chunked
latent, not from its parent. Generic `LATENT -> LATENT` typing means this
passes graph validation and only fails at execution, ~70 s in.

`SeedVR2PostProcessing` takes the *original resized* images as a second input
and colour-matches the output back to them, which stops the diffusion pass
drifting the grade.

## 4. Frame rate is a finishing decision too

Generate at the model's trained rate; interpolate up for delivery. Wan 2.2 is
trained at **16 fps / 81 frames** — generating at 30 gives it frame spacing it
never learned. `RIFE VFI` with `multiplier: 2` on `rife47.pth` turns 81f@16
into 161f@32.

Say both numbers out loud when delivering, or the native rate reads as an
oversight rather than a deliberate choice.

## 5. Concurrency: measure before promising it

Measured peaks on a 46 GB L40S:

| Workload | Peak VRAM |
|---|---|
| Wan generation (VACE / Animate / SCAIL-2) | ~33 GB |
| SeedVR2 7B upscale @ 2x | **36.5 GB**, 100% GPU, ~310 W |

**These cannot run concurrently on this card.** Separate *scripts* is a
process-architecture property; separate *lanes* needs the VRAM to exist. Two
honest options when parallel finishing matters:

- SeedVR2 **3B** (~3.4 GB weights instead of 8.3) in the finishing lane
- an 80-96 GB card (H100 80GB, RTX PRO 6000 96GB)

Report the measured number rather than the intent. The user accepted "larger
GPU on the next runs, but let's keep it where it is for now" immediately once
the ceiling was a measurement rather than a guess.

## 6. Comparing two upscalers honestly

**A full-frame side-by-side cannot show the difference between two 2x
upscales**, especially on a phone. Both panels get downscaled to fit, which
destroys exactly the detail under evaluation. Ship a **1:1 pixel crop** — a
fixed region at actual output resolution, with the source nearest-neighbour
enlarged to the same size for alignment.

Resist scoring sharpness with a per-pixel detail metric. A laplacian-style
"detail energy" reading scored:

| | detail energy |
|---|---|
| source 832x480 | 7.17 |
| ESRGAN 2x | 4.99 |
| SeedVR2 2x | 4.03 |

Read naively this says both upscalers *destroyed* detail and SeedVR2 was
worst. It is an artifact of the measure: the same edge spread over 2x the
pixels has a lower per-pixel gradient by construction. The metric cannot
compare images at different resolutions, and it cannot see temporal shimmer —
which is the entire reason to choose SeedVR2. Report it as inapplicable rather
than as a result.

## 7. Pod lifecycle: ffmpeg does not survive redeploy

The network volume (`/workspace`) persists across pod termination — models,
venvs, outputs all survive. The **container filesystem does not**. Anything
`apt`-installed is gone on the next pod, so the first `ffprobe` call in a
finishing script fails with `FileNotFoundError` on a pod where every model is
present and ComfyUI is healthy.

Fold it into bring-up:

```bash
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg
```

## Verification checklist

- [ ] Finishing runs from a script separate from generation
- [ ] SeedVR2's own VAE downloaded (`seedvr2_ema_vae_fp16`), not a Wan/LTX one
- [ ] Frames pre-resized to the target before `SeedVR2Preprocess`
- [ ] Conditioning built FROM the chunked latent, not parallel to it
- [ ] Output frame count equals input frame count (a dropped tail is silent)
- [ ] Comparison shipped as a 1:1 pixel crop, not full-frame panels
- [ ] Concurrency claims backed by a measured VRAM peak, not by the scripts
      being separate
- [ ] ffmpeg installed on the current pod, not assumed from a previous one
