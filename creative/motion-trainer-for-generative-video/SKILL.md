---
name: motion-trainer-for-generative-video
description: Train motion LoRAs and insert avatars in AI video.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
prerequisites:
  commands: ["python3", "ffmpeg"]
metadata:
  hermes:
    tags:
      - lora-training
      - motion-transfer
      - video-generation
      - character-consistency
      - comfyui
      - ltx
      - wan
    related_skills: [comfyui, generative-video-consistency, generative-media-pipeline-design, seedance-video, character-reference-sheet]
    category: creative
---

# Motion Trainer for Generative Video Skill

Separate **motion** (how a body moves through time) from **identity** (who is
moving) so each can be controlled independently, then recombine them to put a
chosen avatar into a learned performance. Covers dataset prep, motion-LoRA
training, and the adapter-stacking needed at inference.

The central lesson: **most "motion LoRA" requests should not train a motion
LoRA at all.** Pose/reference conditioning solves the same problem faster,
cheaper, and without the motion-vs-identity conflict described below. Train
only when conditioning genuinely cannot express the motion.

> **Status: recipe researched, not yet executed end-to-end.** Parameter
> values below come from tool docs and published guides, not from a training
> run verified by this skill. Treat the first run as calibration and record
> actual results in `references/run-log.md`.

## When to Use

- User wants a specific movement style (a walk, a fight beat, a camera move)
  reproduced across different characters
- User wants an avatar inserted into an existing performance
- User wants consistent character identity across multiple shots
- User is debugging a LoRA that "killed all the motion" in a video model

Do NOT use this to train on real people's likeness or performance without
their consent, or to synthesize sexual content.
## Character references

The identity side of the motion/identity split comes from `character-reference-sheet`. For reference-to-video, pass the full panel `sheet.jpg` (`video_ref`). For avatar insertion or any step that maps ONE image onto a pose, use `single_image_ref`, so the motion LoRA never has to carry identity.

## Prerequisites

- A GPU with **>=24 GB VRAM** for rank-32 training at 720p; 48 GB is
  comfortable. To rent and provision one, load the `comfyui` skill and read
  its `references/gpu-pod-ltx25-setup.md`.
- `ffmpeg` for clip segmentation and normalization.
- A trainer, one of:
  - **musubi-tuner** (kohya) — Wan 2.1/2.2 T2V/I2V, most mature for motion
  - **ai-toolkit** — LTX character/IC-LoRA training
  - **fal LTX-2 video trainer** — hosted API, ~30 min, no local GPU
- 10-50 source clips. Quality and consistency of the *motion* matter far
  more than count.

## Quick Reference

### Decide the approach FIRST

| Goal | Approach | Train? |
|---|---|---|
| Reuse motion from a reference video | **IC-LoRA pose control / reference conditioning** | No |
| Specific character identity, any motion | Character LoRA (I2V) | Yes |
| A motion style with no reference clip available | Motion LoRA (T2V) | Yes |
| Both a named character AND a learned motion | Two adapters, stacked | Yes |

Pose/skeleton conditioning extracts joint positions from a reference clip
and drives the generation directly. It costs no training time and does not
degrade the base model's motion prior. Reach for it first.

### Motion LoRA vs Character LoRA — opposite captioning

This inversion is the single most useful idea in the skill.

| | Motion LoRA | Character LoRA |
|---|---|---|
| Learning | How things move | How a subject looks |
| Caption the | **action, camera, timing** | **identity token + framing** |
| Vary across dataset | subject, clothing, setting | pose, lighting, background |
| Hold constant | the movement itself | the character |
| Base type | T2V | I2V (if a reference image exists) |

A motion LoRA must see the **same motion performed by visibly different
subjects**, or it binds to appearance and becomes an accidental character
LoRA. Deliberately vary who/what is moving.

### Starting hyperparameters

| Param | Motion LoRA | Character LoRA |
|---|---|---|
| `rank` | 16-32 | 32 |
| `alpha` | = rank | = rank (or rank/2 for gentler effect) |
| `learning_rate` | 1e-4 | 1e-4 |
| `max_steps` | 1500-2500 | 1500-2000 |
| `batch_size` | 1 | 1 |
| `gradient_accumulation` | 4 | 4 |
| `mixed_precision` | bf16 | bf16 |
| `gradient_checkpointing` | true | true |
| clip length | 49-81 frames | 24-49 frames |
| fps | match base model (often 24) | 24 |

Save checkpoints every 250-500 steps. The best motion LoRA is frequently an
**earlier** checkpoint than the final one — overtraining is the main failure.

## How to Run

### 1. Prepare the dataset

```bash
python3 scripts/prep_motion_dataset.py \
  --input ./source_clips \
  --output ./dataset \
  --frames 49 --fps 24 --resolution 768x448 \
  --caption-template "a person {action}, {camera}"
```

The script segments long clips to fixed frame counts, normalizes fps and
resolution, drops clips with scene cuts (which poison temporal learning),
and writes a caption stub per clip for you to edit.

Review every caption by hand before training. Captioning is where motion
LoRAs are won or lost.

### 2. Train

```bash
# musubi-tuner (Wan 2.2), motion LoRA
accelerate launch wan_train_network.py \
  --task t2v-A14B \
  --dataset_config ./dataset/config.toml \
  --network_module networks.lora_wan \
  --network_dim 32 --network_alpha 32 \
  --learning_rate 1e-4 --max_train_steps 2000 \
  --mixed_precision bf16 --gradient_checkpointing \
  --save_every_n_steps 250 \
  --output_dir ./out --output_name motion_v1
```

Wan 2.2 uses a **dual high/low-noise** architecture — train the matching
pair or motion quality suffers. Check the trainer's Wan 2.2 docs for which
of the two your task needs.

### 3. Evaluate honestly

```bash
python3 scripts/eval_motion_lora.py \
  --comfy-host http://127.0.0.1:8188 \
  --workflow ./workflows/motion_test_api.json \
  --lora-dir ./out --strengths 0.4,0.6,0.8,1.0 \
  --prompt "a person walking through a doorway" \
  --output-dir ./eval
```

Sweep **checkpoint x strength** and compare against a no-LoRA baseline
generated with the same seed. Judge three axes separately:
motion fidelity, prompt adherence, identity bleed.

### 4. Stack adapters at inference

Apply in this order, and keep the strengths asymmetric:

```
base model
  -> motion LoRA        (strength 0.6-0.8)
  -> character identity (reference image / IC-LoRA, strength 0.7-1.0)
  -> pose conditioning  (optional, from a reference clip)
```

Chain `LoraLoaderModelOnly` nodes in ComfyUI, motion first. If identity is
supplied by a reference image (I2V) rather than a second LoRA, the conflict
described below largely disappears — prefer that arrangement.

## Procedure

1. **Try conditioning before training.** Run the motion through pose/
   reference conditioning. If it holds, stop — you've saved hours and a
   degraded motion prior.

2. **Collect 10-50 clips of the same motion, different subjects.** Same
   action, varied appearance, varied setting. Consistency of *movement* is
   the thing being learned.

3. **Segment and normalize.** Fixed frame count, uniform fps, uniform
   resolution, no scene cuts inside a clip.

4. **Caption the action, not the subject.** "figure pivots left and raises
   both arms, slow dolly in" — not "a woman in a red dress." Leave the
   subject generic and variable.

5. **Train with checkpoints every 250-500 steps.**

6. **Sweep checkpoints and strengths against a fixed-seed baseline.**

7. **Stack with identity and verify motion survived.** Re-run the baseline
   prompt with both adapters and confirm the model still obeys action words.

## Pitfalls

1. **Character LoRAs suppress motion — this is the defining failure mode.**
   A widely reported symptom (see Comfy-Org/ComfyUI discussion #13213) is
   that adding a character LoRA makes video models ignore action prompts and
   produce near-static output. The adapter overfits identity into layers the
   base model uses for temporal dynamics. Mitigations, in order:
   supply identity via **I2V reference image instead of a LoRA**; lower
   character strength to 0.5-0.7; lower `alpha` relative to `rank`; use an
   earlier checkpoint; train identity on stills plus a few clips rather than
   clips alone.

2. **Motion LoRAs silently become character LoRAs.** If every training clip
   shows the same person, the adapter learns that person. Vary subjects
   deliberately — it is the entire reason the dataset is built this way.

3. **Scene cuts inside a training clip poison temporal learning.** The model
   learns that content may teleport. Detect and split on cuts during prep.

4. **Overtraining is the norm, not the exception.** Motion LoRAs frequently
   peak at 1000-1500 steps and degrade after. Always sweep checkpoints;
   never assume the final one is best.

5. **T2V and I2V LoRAs are not interchangeable.** A T2V LoRA spreads its
   influence over appearance, motion, and composition together. An I2V LoRA
   works alongside a reference image and mostly adjusts temporal behavior.
   For identity preservation, I2V is the better instrument.

6. **Wan 2.2's dual high/low-noise design needs matched training.** Training
   only one half and applying it broadly gives muddy motion.

7. **Clip length costs time, not memory.** Peak VRAM is usually set by the
   caption/latent caching pass rather than the training step, so longer
   clips mostly slow each step. Do not assume a shorter clip fixes an OOM.

8. **Evaluate against a fixed seed, always.** Without a same-seed no-LoRA
   baseline you cannot tell whether the LoRA helped or the seed did.

9. **Do not train on real people without consent.** Likeness and performance
   captured in adapter weights cannot be recalled once distributed.

## Verification

- [ ] Conditioning-only approach was tried and genuinely rejected
- [ ] Dataset holds the same motion across visibly different subjects
- [ ] No clip contains a scene cut; fps and resolution are uniform
- [ ] Captions describe action and camera, not subject appearance
- [ ] Checkpoints exist at >=4 points across the run
- [ ] A same-seed, no-LoRA baseline clip was generated for comparison
- [ ] Checkpoint x strength sweep was reviewed before picking a winner
- [ ] With identity stacked, action prompts still visibly change the output
- [ ] Chosen strengths and checkpoint recorded in `references/run-log.md`
