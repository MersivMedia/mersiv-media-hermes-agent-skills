---
name: ref-character-replacement-content-pipeline
description: Swap a character in a video with MiniMax H3 on RunPod.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [minimax-h3, comfyui, runpod, character-replacement, ref2va, video, prompt-engineering]
    related_skills: [runpod-pods, comfyui, video-character-replacement, film-craft-knowledge-base, replicate-api-generation]
---

# Reference Character Replacement Pipeline (MiniMax H3 Ref2VA)

## When to Use

- User sends (usually over Telegram, from a phone) a **character image** and a
  **source video** and says what to swap: *character only* or *character + background*.
- User wants to open the pipeline on their laptop in a browser and queue it by hand.
- Anything touching the `h3-refswap` pod, the `comfy-video` volume, or the
  **H3 Prompt Director** ComfyUI node.

Deliverables per job: final video + side-by-side comparison, both uploaded to
Drive, link in chat. The user composites elsewhere — do not auto-composite.

## Status (read first)

Built and verified: pod bring-up, official models, rebuilt workflow (0 link
errors), Prompt Director node registered, nginx basic-auth in front of ComfyUI
(401 no-creds / 401 wrong / 200 right, websocket OK through RunPod proxy), test
assets generated and uploaded. **Not yet verified: an actual H3 render**, the
Director's Claude call from inside the pod, per-clip runtime/cost, the chunker.
Do not quote per-clip cost or runtime until one render is timed.

## Content rules (built into the node, apply on every path)

The workflow the user supplied loaded a third-party NSFW finetune
(`10Eros_Max_h3_...`) with an explicit example prompt. The pipeline uses the
**official** weights only and the Director refuses sexual/nude content. Real
identifiable people only if it is the user or someone who consented; decline
celebrities/obvious non-consent. Manual prompts in `manual_override` go
through the same screen.

## Infrastructure

| Item | Value |
|---|---|
| Volume | `uldz4295en` "comfy-video", **EU-NL-1**, grown 200→270 GB (REST `PATCH /v1/networkvolumes/<id> {"size":N}`) |
| ComfyUI | `/workspace/ComfyUI`, core already has `MiniMaxH3ReferenceToVideo` (comfy_extras/nodes_minimax_h3.py) |
| venv | `/workspace/venv-clean` (torch 2.11+cu128). The old `/workspace/venv` is broken (cuDNN) — don't use it |
| GPU | RTX PRO 6000 (Blackwell, NVFP4-capable) preferred; H100 80GB used as fallback at $3.49/hr. **Ask before substituting a pricier card** |
| Ports | `8188/http` (nginx auth) → ComfyUI on `127.0.0.1:8189`; `22/tcp` |
| URL | `https://<pod-id>-8188.proxy.runpod.net` — changes if the pod is recreated |
| Secrets | `/root/secrets.env` (local disk, 600): `ANTHROPIC_API_KEY`, `COMFY_USER`, `COMFY_PASS`. Local copy of login: `~/.hermes/data/ref-character-replacement/comfy_login.env`. Pod key in `hermes-agent/.env` as `ANTHROPIC_API_KEY_REFSWAP` |

EU-NL-1 has **no S3 endpoint**, so the volume can only be inspected from a pod.

## Models — `Comfy-Org/MiniMax-H3` (official weights, ComfyUI filenames)

| File | Folder | Size |
|---|---|---|
| `minimax_h3_ref2va_int8_convrot.safetensors` | diffusion_models | 34.0 GB |
| `qwen3vl_32b_minimax_h3_nvfp4_awq` (Blackwell) **or** `..._int8_convrot` (H100/Ampere) | text_encoders | 15.7 / larger |
| `minimax_h3_video_vae_int8_convrot` | vae | 2.8 GB |
| `minimax_h3_audio_vae_fp32` | vae | 0.6 GB |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16` | loras | 2.0 GB |

Downloads ran ~67 GB in under 2 min via `hf download` on RunPod. NVFP4 needs
Blackwell — on H100 switch the text encoder to int8. The supplied workflow used
the **fl2v** turbo LoRA on a ref2va model (wrong task family) — use `ref2v_turbo`.

## H3 limits (from the model card)

- Output 4–15 s at 24 fps, 768p locally (2K only via MiniMax API).
- Reference videos ≤3 clips, each 2–15 s, **≤15 s total**.
- Frame count formula rounds to 17k+5: 5 s → 124, 15 s → 362.
- In video-edit mode the camera is fixed by the source: the prompt must
  **describe** framing/movement, never invent moves. Enhancement goes to
  lighting, style, rendition, background.

## Long-form (>15 s) — design, not yet built

1. Split on hard cuts (PySceneDetect) — free seams.
2. Sub-split long scenes at low-motion points (pose velocity), not every 15 s.
3. Chain: previous chunk's last frame = next chunk's `<Picture 1>` first
   frame, **plus** the original character reference and identical subject text
   in every chunk (chaining alone drifts).
4. Mux the original audio back over the joined chunks.
Background swaps seam more visibly than character-only.

## Components (this skill's files)

- `comfy_node/h3_prompt_director/` — custom node. Inputs: instruction, mode
  (`character_only` / `character_and_background`), character image, first
  frame, optional background, duration, `manual_override`. Outputs: prompt,
  preview, `background_passthrough` (None in character_only — H3 skips None
  refs). Calls Claude with `guide_ref_en.md` (H3 six-section prompt guide) and
  `cinematography_vocab.md` (from `generative-video-consistency-agent-pipeline` `shot_taxonomy.json`). Key read from
  env only, never stored in the workflow.
- `scripts/build_workflow.py <supplied_editor_wf.json> <out.json>` — rewires the
  supplied graph: official UNET/LoRA/TE, Director → H3 `prompt`, first-frame
  extract → `ref_image_0`, background via Director passthrough, preview + note
  nodes. Validates link integrity.
- `workflows/h3_refswap.json` — output; deployed as
  `user/default/workflows/H3 Ref Character Replacement.json`.
- `scripts/gen_test_assets.py` — Replicate test pair: seedance-1-lite source
  (grey-hoodie man, static camera, wave/step/turn) + flux-2-pro character
  (copper hair, teal jacket). Colours absent from the source → their pixel
  share in the output measures identity transfer objectively.

## Bring-up procedure

1. `pod.py balance` (≥ ~$30 before starting). Create on `uldz4295en`, EU-NL-1,
   `--ports "8188/http,22/tcp"`.
2. `scp` the node to `custom_nodes/`, workflow to `user/default/workflows/`;
   install VideoHelperSuite, ffmpeg, tmux.
3. Secrets to **`/root`**, not `/workspace` (the volume ignores chmod — a 600
   file reads back 666).
4. nginx basic auth — see `runpod-pods` → `references/web-ui-basic-auth.md`.
5. Launch ComfyUI in tmux: `--listen 127.0.0.1 --port 8189`, log to `/root`.
6. Verify externally: 401/401/200, `object_info/H3PromptDirector` 200,
   authenticated websocket connects, unauthenticated websocket 401.

## Pitfalls

- **ComfyUI validates every loader before running**, even ones the current
  mode ignores. A default filename that isn't in `input/` (`background.png`)
  fails the whole queue in character_only mode. Ship a placeholder or default
  every loader to a file that exists.
- **`huggingface_hub` 2.x breaks `tokenizers`** (<2.0 required). Pin
  `huggingface_hub<2` in the ComfyUI venv; `hf_transfer` is deprecated — use
  `HF_XET_HIGH_PERFORMANCE=1`.
- Upload inputs with `POST /upload/image` (works for mp4 too), then confirm
  via `object_info/LoadImage` and `object_info/VHS_LoadVideo` option lists.
- Replicate seedance-1-lite `resolution: 720p` returned **1920×1088**, 121
  frames — trim to an exact duration (`-t 5.0` → 120 frames) before use.
- Report pod spend (hours × rate) at each checkpoint; idle pods bill.
- Approval prompts for commands touching `.env`/secrets or system config
  paths time out often on Telegram; batch such steps and say exactly what the
  blocked command does.
