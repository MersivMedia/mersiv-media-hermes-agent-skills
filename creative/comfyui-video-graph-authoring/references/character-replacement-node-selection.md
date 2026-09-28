# Character Replacement: Node Selection (Wan family)

Measured on a RunPod L40S (48 GB), Sept 2026. One source clip (81f, 832x480,
16fps, single walker), one reference character (distinctive: copper-red braid,
teal parka with orange stripes, yellow boots, busy night-market background),
seed 4242 pinned across every run.

## The decision

Use **`WanSCAILToVideo`** for in-video character replacement.

It is the only Wan node with an explicit `replacement_mode` flag and it was
the configuration the user judged successful — clean swap with correctly
adapted lighting. Six earlier runs on the wrong nodes cost most of a session.

## Measured comparison

| Run | teal % | copper % | bg brightness | bg warp/frame |
|---|---|---|---|---|
| VACE, complex reference | 10.22 | 18.28 | 71.3 (leaked) | 2.57 |
| Animate, no clip_vision | 2.20 | 0.43 | 142.4 | 9.73 |
| Animate + clip_vision | 2.27 | 0.46 | 146.2 | 10.52 |
| Animate + binary mask | 0.29 | 0.21 | 110.5 | 2.73 |
| Animate + mask inverted | 0.00 | 0.01 | 113.8 | 5.87 |
| **SCAIL-2 replacement** | 3.85 | 0.61 | 112.4 | **3.06** |

Reference-image brightness 74.6; target scene ~175.4.

**Read these numbers carefully.** SCAIL-2 scores lower on the colour metrics
than VACE yet was the visually correct result. The metrics track "how many
pixels match the reference palette", which rewards a reference-coloured
*background leak* (VACE's failure) and penalises correct lighting adaptation
(SCAIL-2's success). This is the canonical example of why proxy metrics must
not decide acceptance — see pitfall 1 in the parent SKILL.md.

What the metrics *are* good for: `bg warp/frame` genuinely tracked visual
stability, and the Animate runs were correctly identified as broken.

## Why Animate failed

`WanAnimateToVideo` animates a still reference **from** motion. It was never
built to swap a person already present in footage. Two consequences:

- Feeding it `background_video` containing the original walker makes the
  model fight itself: it is told to place a new character where a different
  person already stands. Signature = muddied identity, unstable background,
  brightness averaging between reference and target.
- Its `character_mask` is a plain binary mask. SCAIL-2 wants **coloured
  per-identity** masks. That is a data-format mismatch, not a polarity bug —
  which is why testing both mask polarities changed nothing useful.

## SCAIL-2 wiring that worked

```
source video ─┬→ pose_video  (RAW frames — SCAIL-2 does its own motion
              │               extraction; do NOT feed it a skeleton)
              └→ RTDETR_detect(person) → SAM3_Detect(individual_masks=True)
                     → SAM3_VideoTrack → driving_track_data ┐
reference img ─→ RTDETR_detect(person) → SAM3_Detect ──→ ref_track_data (MASK)
                                                              │
        SCAIL2ColoredMask(replacement_mode=True, sort_by=left_to_right)
              ├→ pose_video_mask       (white bg in replacement mode)
              └→ reference_image_mask  (black bg in replacement mode)
                                                              │
  SCAIL-2 model → lightx2v step-distill LoRA → DPO LoRA → ModelSamplingSD3
              → WanSCAILToVideo → KSamplerAdvanced → VAEDecode
              → RIFE VFI (x2) → CreateVideo → SaveVideo
```

Settings: `length 81` (trained value), `width 832`, `height 480`,
`steps 8`, `cfg 1.0`, `shift 8.0`, `pose_strength 1.0`,
`previous_frame_count 5`. Runtime ~441s fresh, ~180s with cache hits.

### Mode flags must agree

`replacement_mode` appears on **both** `SCAIL2ColoredMask` and
`WanSCAILToVideo` and controls mask background polarity:

- `True` (replacement): `pose_video_mask` white bg, `reference_image_mask` black bg
- `False` (animation): the inverse

Set them to the same value or the masks will not match what the model expects.

### Multi-person selection

`SCAIL2ColoredMask` handles this natively, which the Animate path could not:

- `object_indices` — `"0,2,3"`, empty means all
- `sort_by` — `left_to_right` (leftmost centroid at first appearance gets the
  first colour), `area` (largest first), `none` (SAM3 order)

Colours are assigned consistently across reference and pose video so each
identity keeps its mapping. Set `max_objects` and `max_detections` above 1
when more than one person is in frame.

## Required models

| File | Folder | GB |
|---|---|---|
| `wan2.1_14B_SCAIL_2_int8_convrot.safetensors` | diffusion_models | 16.65 |
| `wan2.1_SCAIL_2_DPO_lora_bf16.safetensors` | loras | 1.23 |
| `wan2.1_SCAIL_2_relight_lora_bf16.safetensors` | loras | 1.23 |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | loras | 0.74 |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | text_encoders | 6.74 |
| `clip_vision_h.safetensors` | clip_vision | 1.26 |
| `wan_2.1_vae.safetensors` | vae | 0.25 |
| `sam3.1_multiplex_fp16.safetensors` | diffusion_models | 1.75 |

Sources: `Comfy-Org/SCAIL-2` (ungated), `Kijai/WanVideo_comfy` for lightx2v,
`Comfy-Org/Wan_2.1_ComfyUI_repackaged` for `clip_vision_h` (it is **not** in
the 2.2 repo), `Comfy-Org/sam3.1` for SAM3.

Docs specify the fp16 SCAIL checkpoint (32.79 GB); `int8_convrot` is the same
model quantized at half the size and worked fine.

### SAM3 gating

`facebook/sam3` is `gated: manual` — a human reviews each request, so it can
take days. **`Comfy-Org/sam3.1` is ungated, smaller (1.75 GB), and works.**
Prefer it rather than waiting on approval.
