# MiniMax H3 reference-to-video (ref2va) for character replacement

An alternative to the VACE/Wan path. H3 edits a source video from a written
prompt plus labelled reference images/videos, rather than from a pose skeleton.

## Hard limits (model card)

- Output 4–15 s at **24 fps**. Local H3-Base renders 768p; 2K needs
  H3-Regenerate-2K via MiniMax's API.
- Ref2VA inputs: ≤9 images, ≤3 videos (each 2–15 s, **total ≤15 s**), ≤12 files.
- ComfyUI `length` must be 17k+5 frames. The shipped workflow's formula:
  `max(5, round(s*24)) + (5 - (max(5, round(s*24)) % 17)) % 17` → 5 s = 124,
  15 s = 362. Trained range ~124–362.

Anything longer than 15 s must be chunked — see "Long sources" below.

## Weights: use the official ComfyUI repack

`Comfy-Org/MiniMax-H3` repacks the **official** weights with the filenames
ComfyUI workflows expect. Community workflows often load a third-party finetune
in the UNET slot — swap it for the official file one-for-one, no rewiring.

Minimal ref2va set (~67 GB with int8 text encoder):

| File | Size |
|---|---|
| `diffusion_models/minimax_h3_ref2va_int8_convrot` | 34.0 GB |
| `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot` (non-Blackwell) | 27.1 GB |
| `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq` (Blackwell only) | 15.7 GB |
| `vae/minimax_h3_video_vae_int8_convrot` | 2.8 GB |
| `vae/minimax_h3_audio_vae_fp32` | 0.6 GB |
| `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16` | 2.0 GB |

**Check the turbo LoRA's task family.** A supplied workflow loaded
`fl2v_turbo_8step` onto a **ref2va** model — wrong family. Use the `ref2v_*`
LoRA with a ref2va UNET.

The H3 nodes are in core ComfyUI (`comfy_extras/nodes_minimax_h3.py`) on recent
commits; `VHS_LoadVideo` needs ComfyUI-VideoHelperSuite.

## Node behaviour worth knowing

`MiniMaxH3ReferenceToVideo` uses Autogrow inputs (`ref_images.ref_image_N`,
`ref_videos.ref_video_N`) and **skips `None` entries**, so an optional reference
can be passed through a node that returns `None` when unused — no extra switch.

## In-graph prompt engine (custom node pattern)

Built as `H3PromptDirector` (source kept under
`~/.hermes/skills/creative/ref-character-replacement-content-pipeline/comfy_node/`).
Design points that held up:

- Inputs: source video frames, character image, optional background image,
  instruction, mode (`character_only` / `character_and_background`), duration.
  Outputs: `prompt`, `preview` (to a `PreviewAny` node so manual users can read
  it), and `background_passthrough` — returns the background only in background
  mode, else `None`, which H3 skips. That replaces a separate boolean toggle; an
  unwired toggle on the canvas misleads manual users.
- Sample ~6 evenly spaced frames, send as JPEG base64 to the LLM with the
  writing guide and cinematography vocabulary bundled beside the node.
- Validate the five section keys in the output; raise with a retry message if
  any are missing.
- Duration primitive drives **both** the Director and the length formula.
- API key from the pod **environment only** — never a widget — so exported
  workflow JSON carries no secret. Use a dedicated, revocable key per pod.
- Content policy enforced inside the node (including a screen on
  `manual_override` text), so browser runs and agent runs obey the same rule.

Rebuilding a supplied UI-format workflow programmatically: edit
`nodes`/`links` together and run an integrity check afterwards — every link's
source output must list it and its destination input must point back. 0 errors
before deploying; a half-updated link list loads but fails at queue time.

## Deploying on a RunPod network volume with browser access

- **The network volume ignores chmod.** A `secrets.env` written 600 read back
  as 666 on the MooseFS `/workspace` mount — readable by any pod mounting the
  volume. Keep secrets on container disk (`/root/secrets.env`, real 600) and
  delete any volume copy.
- Keep ComfyUI on `127.0.0.1:<internal>` and put an auth proxy on the exposed
  port, so the public `https://<pod>-8188.proxy.runpod.net` URL is never an
  open GPU.
- **RunPod images already run their own nginx** (listening on 9091, 3001, 7861,
  8081, 8001, 7270) from an `/etc/nginx/nginx.conf` with **no `include
  sites-enabled`**. A site file dropped in `sites-enabled` is silently ignored
  and `nginx -t` still passes, because it never reads it. Starting a second
  `nginx` fails with `bind() ... failed (98)`. Check `grep include
  /etc/nginx/nginx.conf` first and add the include (back up the conf), then
  `nginx -s reload` and confirm the port with `ss -ltnp`.
- **Verify the auth gate before announcing the URL**: no credentials and a
  wrong password must both be refused, good credentials must reach
  `/system_stats`. A `000` status means nothing is listening.
- Upgrading `huggingface_hub` to 2.x breaks `tokenizers` (needs `<2.0`); pin
  `huggingface_hub<2.0`. The `hf_transfer` extra is gone — Xet transfers are
  already fast (34 GB in 77 s on RunPod).

## Prompt format: full-reference mode

Follows `docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md` in the MiniMax-H3 HF repo.
Sections: `subject_definitions`, `retention_analysis`, `detailed_description`,
`overall_soundscape`, `non_diegetic_music`. Label mapping that keeps prompt and
graph consistent:

| Label | Graph input | Meaning |
|---|---|---|
| `<Video 1>` | `ref_video_0` | source video being edited — camera/timing fixed |
| `<Picture 1>` | `ref_image_0` (ImageFromBatch idx 0) | first frame of the source |
| `<Picture 2>` | `ref_image_1` | replacement character |
| `<Picture 3>` | `ref_image_2` | target background (background mode only) |
| `<Subject 1>` | — | original performer: `partially_preserved` |
| `<Subject 2>` | — | new character: `attribute_transfer` |

In **editing** mode the source camera is fixed structure: a prompt enhancer
should *describe* the source camera accurately and enhance lighting, rendition,
colour and environment — never invent camera moves.

Keep the prompt's duration and the rendered `length` driven by the same value,
or timestamps in `detailed_description` disagree with the frames rendered.

## Long sources (planned, not yet measured)

Split on hard cuts first (free seams), sub-split scenes >15 s at low-motion
points, pass each chunk's last frame as the next chunk's `<Picture N>` first
frame, **and** re-feed the original character reference + identical subject
text every chunk so identity anchors to the source rather than drifting through
outputs. Mux the original audio back over the joined result. Seam quality and
per-chunk runtime were not measured yet — time one chunk before quoting cost.

## Content boundary

Photo-of-a-person + swap-into-video is the exact shape of a non-consensual
deepfake tool. Community H3 workflows ship NSFW finetunes and explicit example
prompts. Use official weights, keep sexual content out of generated prompts,
and require consent for real identifiable people. Enforce it inside the prompt
node itself so manual browser runs and agent runs obey the same rule.
