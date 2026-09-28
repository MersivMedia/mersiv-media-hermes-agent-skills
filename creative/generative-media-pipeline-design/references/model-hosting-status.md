# Model hosting status: API-only vs open weights

A verified snapshot of *where* specific video models can actually run, and
**which control architecture each family speaks**. The durable value is not
the catalogue (models ship constantly) but the two routing questions it
answers: hosted API or rentable GPU, and which reference/control mechanism
is even applicable once you pick a base model.

Re-verify before relying on any row — these move. The verification commands
are in `rented-gpu-operations.md` §1.0 and §4.4, plus §1.5 below.

---

## 1. The split that matters

| | API-only | Open weights |
|---|---|---|
| Can rent a GPU for it | **No** | Yes |
| ComfyUI integration | API nodes (network clients, bill per generation) | Real checkpoint loaders |
| Cost shape | per generation | per GPU-hour + storage |
| Ceiling | provider's rate limits and pricing | your VRAM |
| Content moderation | enforced by the vendor | none in the loop |

The trap is that both appear in ComfyUI as installable nodes. An "install
<model> for ComfyUI" repo tells you nothing about whether weights exist.

The moderation row matters for routing, not just ethics: when the brief is
horror, medical, forensic, or any other legitimately graphic genre, a hosted
model will refuse regardless of how good it is. That alone can decide the
track.

### Status table (verified Sept 2026)

| Model | Weights public? | Runs |
|---|---|---|
| **LTX-2 / LTX-2.5** (Lightricks) | **Yes** | Local. Gated HF repo, license click |
| **Wan 2.1 / 2.2** (Alibaba) | **Yes** | Local |
| **Wan 3.0** (Alibaba) | **No** | Hosted API only |
| **Seedance 1.x / 2.x** (ByteDance) | **No** | Hosted API only |
| **MiniMax H3** | Yes | Local |

---

## 1.5. Audit a RUNNING server to separate local from cloud nodes

The node catalog settles this definitively — no web research needed. The
`category` field is the discriminator: `partner/...` means hosted, anything
else is local.

```bash
curl -s http://127.0.0.1:8188/object_info -o /tmp/oi.json

python3 - <<'EOF'
import json
d = json.load(open("/tmp/oi.json"))
print("total node classes:", len(d))
for k in sorted(d):
    cat = d[k].get("category") or ""
    if cat.startswith("partner"):
        print(f"  CLOUD  {k:34} {cat}")
EOF
```

Observed contrast on one install:

```
WanVaceToVideo          category: model/conditioning/wan/vace   -> LOCAL
Wan3ReferenceToVideoApi category: partner/video/Wan             -> CLOUD
LtxApi25ImageToVideo    category: partner/video/...             -> CLOUD
```

**The same trap exists in the shipped workflow templates.** Under
`comfyui_workflow_templates_json/templates/`, `api_*.json` wires **cloud**
nodes and `video_*.json` wires **local** ones. Loading `api_ltx2_5_i2v.json`
expecting local inference silently bills a remote endpoint on every run.

Dump a node's full input schema before designing around it:

```python
i = d["WanVaceToVideo"]
for sec in ("required", "optional"):
    for k, v in (i.get("input", {}).get(sec) or {}).items():
        t = v[0] if isinstance(v, list) and v else v
        extra = v[1] if isinstance(v, list) and len(v) > 1 else ""
        print(f"  {sec[:3]} {k:18} {str(t)[:40]:42} {str(extra)[:60]}")
print("returns:", i.get("output"), i.get("output_name"))
```

---

## 2. ByteDance Seedance — API-only at every version

No public weights for 1.0 Pro/Lite, 2.0, or 2.5. ByteDance's Seed pages offer
"Try Now" and "Get API"; there is no checkpoint to download and no self-host
path. Third-party ComfyUI node packs bridge to paid API aggregators.

**Seedance 2.5** (released 2026-07-31) — audio-video joint generation, the
current flagship. Verified live on Replicate as `bytedance/seedance-2.5`
(166k+ runs, official model, so **no version hash** — community models require
one, official models must not have one).

Verified input schema:

| Field | Notes |
|---|---|
| `prompt` | optional when a media input is supplied |
| `image` | first-frame for i2v |
| `last_frame_image` | requires `image`; not combinable with some ref modes |
| `reference_images` | array, **up to 30** — character/style locks |
| `reference_videos` | up to 10, combined ≤30s — motion transfer |
| `reference_audios` | up to 10, combined ≤30s |
| `duration` | int seconds, default 5; **`-1` = model picks** |
| `resolution` | enum — **only `480p` and `720p`** on Replicate, despite marketing copy citing 1080p |
| `aspect_ratio` | enum, default `16:9`; `adaptive` lets the model choose |
| `generate_audio` | bool, **default true** |
| `watermark` | bool, default false |
| `output_format` | enum, default `mp4` |
| `seed` | int; reproducibility explicitly not guaranteed |

Two things worth noting against this skill's continuity guidance: the large
`reference_images` budget (30) suits the reference-sheet approach directly, and
native `reference_audios` means the synthesize-TTS-first ordering is supported
rather than needing a workaround.

**Budget ~10 minutes of wall time for a 5-second clip.** A verified 5s / 720p /
21:9 run reported `predict_time` **608s**. A naive foreground call will exceed
most tool and shell timeouts. Run it backgrounded, or submit and poll
separately. If a poller dies, the prediction **keeps running server-side** —
recover it by ID rather than resubmitting, or you pay twice:

```bash
curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  "https://api.replicate.com/v1/predictions?limit=5"
curl -s -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  "https://api.replicate.com/v1/predictions/<id>"
```

---

## 2.5. Alibaba Wan 3.0 — API-only (Wan 2.x is not)

Launched 2026-08-24. The vendor's own model page answers the open-weights
question in writing: **no**. No Hugging Face checkpoint, no inference repo, no
local runtime. Its ComfyUI presence is `Wan3ImageToVideoApi` and
`Wan3ReferenceToVideoApi`, both under `partner/video/Wan`.

Worth knowing because the version number is misleading: **Wan 2.1 and 2.2 are
open weights, Wan 3.0 is not.** Assuming continuity of licensing across a
version bump within one vendor family is a live failure mode.

The API does natively accept reference images, videos, *and* audio, combined
freely and cited in the prompt as `@Image1`, `@Video1`, `@Audio1` — so it is a
genuinely strong hosted option where moderation is acceptable.

---

## 3. Lightricks LTX-2.5 — open weights, gated

22B DiT audio-video model, open weights on Hugging Face at
`Lightricks/LTX-2.5`, built into ComfyUI core with official T2V/I2V templates.
This is the rentable counterpart to Seedance.

`gated: auto` — but see the caveat in `rented-gpu-operations.md`: the metadata
endpoint returns 200 to anyone and only describes the gate *type*. `auto` means
auto-approved **after a human accepts the license**, and downloads 403 until
then. Test with a real file HEAD, not the metadata endpoint.

Full repo is **~201 GB**. Inventory (verified via the HF tree API):

| File | Size |
|---|---|
| `diffusion_models/…-distilled-transformer-bf16` | 42.02 GB |
| `diffusion_models/…-dev-transformer-bf16` | 42.02 GB |
| `text_encoders/gemma4-12b-with-proj-…-bf16` | 26.26 GB |
| `diffusion_models/…-distilled-transformer-comfy-int8-convrot` | 21.50 GB |
| `diffusion_models/…-dev-transformer-comfy-int8-convrot` | 21.50 GB |
| `diffusion_models/…-distilled-transformer-nvfp4` | 18.72 GB |
| `text_encoders/…-comfy-int8-convrot` | 15.37 GB |
| `loras/…-distilled-lora-450-bf16` | 8.90 GB |
| `vae/…-video-vae-bf16` | 1.47 GB |
| `vae/…-video-vae-conv-bf16` | 1.45 GB |
| `latent_upscale_models/…-spatial-upscaler-x2` | 1.00 GB |
| `vae/…-audio-vae-bf16` | 0.36 GB |
| `latent_upscale_models/…-temporal-upscaler-x2` | 0.26 GB |
| `model_patches/…-duration-head-bf16` | ~0 |

**Working set for a demo on a 48 GB card, ~47 GB on disk:** distilled
transformer int8 + gemma4 int8 text encoder + distilled LoRA + all three VAEs
+ both upscalers + duration head. Taking `distilled` over `dev` and int8 over
bf16 is what fits it; see `rented-gpu-operations.md` §4.4 for the reasoning
and the enumeration command.

Note the int8 caveat already documented in §6.6 of that file: fused int8
Triton kernels are shape- and GPU-specific and **raise rather than falling
back** on untuned shapes. Keep bf16 headroom in the VRAM budget so the
fallback is available.

---

## 3.5. Control architectures do NOT port across model families

The expensive mistake in this area. "Use VACE with model X" is only a coherent
request if X is a Wan-family model. Reference/control adapters bind to a
specific architecture, and there is no bridge.

| Family | V2V + image-reference mechanism | Node(s) |
|---|---|---|
| **Wan 2.1 / 2.2** | **VACE** — one node takes control video, reference image and masks | `WanVaceToVideo` (+ `TrimVideoLatent`) |
| **LTX-2 / 2.5** | **IC-LoRA** in-context guides | `LTXVAddGuide`, `LTXVAddLatentGuide`, `GetICLoRAParameters`; full structural control needs the `ComfyUI-LTXVideo` pack (`LTXICLoRALoaderModelOnly`, `LTXAddVideoICLoRAGuide`) |

A VACE-for-LTX build does exist (`ali-vilab/VACE-LTX-Video-0.9`) — the VACE
paper used LTX-Video-2B for speed and Wan-T2V-14B for quality. But it targets
**LTX-Video 2B, 0.9.x**, not the 22B LTX-2.5 DiT. Different architecture; the
adapter has nothing to attach to. **Version numbers inside adapter repo names
are load-bearing** — read them before assuming applicability.

Check adapter-to-base version match even within a family: published Lightricks
IC-LoRA Union Control adapters are built on **LTX-2.3**. Lightricks states most
2.3 adapters run on 2.5 unchanged but explicitly says to validate. Treat
cross-version adapter use as "test before building on top of it," and say so
rather than presenting it as settled.

### `WanVaceToVideo` inputs (verified live)

Relevant to the continuity guidance in the parent skill: this does motion
transfer plus subject insertion in a **single node with no training at all**,
which is almost always the right first attempt before any LoRA work.

| Input | Type | Purpose |
|---|---|---|
| `control_video` | IMAGE | source clip driving structure/motion |
| `reference_image` | IMAGE | subject/character reference |
| `control_masks` | MASK | region targeting for inpaint-style edits |
| `strength` | FLOAT | default 1.0 |
| `width`/`height`/`length` | INT | default 832×480, 81 frames |

Returns `positive`, `negative`, `latent`, `trim_latent` — feed `trim_latent`
into `TrimVideoLatent`.

### Wan 2.2 VACE weight inventory

Repo naming is not guessable. Verify existence via the HF API before writing
any download script:

```bash
for r in "Wan-AI/Wan2.2-VACE-A14B" "alibaba-pai/Wan2.2-VACE-Fun-A14B" \
         "Comfy-Org/Wan_2.2_ComfyUI_Repackaged"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $HF_TOKEN" "https://huggingface.co/api/models/$r")
  echo "$r -> HTTP $code"
done
```

The intuitive `Wan-AI/Wan2.2-VACE-A14B` **404s**. Real sources are
`alibaba-pai/Wan2.2-VACE-Fun-A14B` (original) and
`Comfy-Org/Wan_2.2_ComfyUI_Repackaged` (ComfyUI-ready split files — prefer).

**VACE Fun A14B is a dual-expert MoE. Both halves are mandatory:**

| File | fp8_scaled | bf16 |
|---|---|---|
| `wan2.2_fun_vace_high_noise_14B` | 17.35 GB | 34.68 GB |
| `wan2.2_fun_vace_low_noise_14B` | 17.35 GB | 34.68 GB |
| `umt5_xxl` text encoder | 6.74 GB | 11.37 GB |
| `wan2.2_vae` / `wan_2.1_vae` | 1.41 / 0.25 GB | — |

fp8_scaled ≈ **43 GB** total; bf16 ≈ 81 GB. Downloading only `high_noise`
yields a model that cannot run — and **the server still lists it**, so the
models endpoint alone will not catch the omission. Verify both files exist and
match in size; identical byte counts are expected for a correct MoE pair:

```bash
ls -l models/diffusion_models/*vace*.safetensors | awk '{print $5, $9}'
```

---

## 4. Routing heuristic

Ask in this order:

1. Do public weights exist? (HF tree API returns files with sizes)
2. If no → hosted API from the local box; **do not rent**.
3. Does the brief involve content a hosted vendor will refuse (graphic horror,
   medical, forensic)? If yes and weights exist → local is the only route.
4. If yes to weights → is the hosted route's ceiling actually binding? Rent
   only for a measured reason: fidelity, rate limit, per-unit cost at volume,
   moderation, or the need to demonstrate local operation.
5. **Which control architecture does the chosen base model speak?** Settle this
   before downloading — it determines the node graph and the adapters, and it
   is not transferable between families (§3.5).
6. If the deliverable is a screen recording, weight the decision toward
   whatever keeps per-action wall time low — distilled variants, nearby
   region. See §4.2 and §4.4 of `rented-gpu-operations.md`.

When a user names an API-only model and also wants GPU-backed work, these are
**two parallel tracks**, not a conflict: API calls for the named model, open
weights for the hardware demonstration.
