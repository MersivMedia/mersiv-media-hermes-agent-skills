---
name: wan2gp-yue2-covers
description: Full-length AI song covers on a rented GPU.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [music, cover, yue2, wan2gp, runpod, sheetsage, gpu]
    related_skills: [runpod-pods, ai-cover-songs]
---

# Full-Length Covers with Wan2GP / YuE2

## When to Use

The user wants a **full-length cover with vocals** in a new genre — melody
carried across, new arrangement. Triggers: "cover this song as X", "remake
this track", "regenerate the backing track".

**Pick the right tool first:**

| Want | Use |
|---|---|
| Original instrumental, new singer | `ai-cover-songs` — Replicate RVC, ~$0.10, no GPU |
| Melody into a **new arrangement**, full length, vocals | this skill |
| Instrumental restyle only | `ai-cover-songs` — musicgen-remixer |

**YuE2 covers regenerate the backing track.** They do not preserve the
original instrumental. `defaults/yue2.json` states this outright. If the user
wants the real backing track kept, this is the wrong skill.

## Why a rented GPU

This box has **no GPU** (no NVIDIA driver, 1.9 GB RAM). Replicate has no
equivalent: `fofr/yue` is text-only (no audio input), `fofr/sheetsage` does
not exist, and `minimax/music-1.5` cannot accept a source song.
Melody-conditioned full-length covers with vocals exist only in this stack.

## What the stack is

[Wan2GP](https://github.com/deepbeepmeep/Wan2GP) — "video generator for the
GPU poor", 9.4k stars, actively developed. Bundles YuE2 **and SheetSage2**
together, so no separate transcription install.

Verified download, int8 path:

```
1.52 GB  YuE2_Acoustic_int8_convrot.safetensors
2.93 GB  YuE2_AR/YuE2_AR_int8_convrot.safetensors
0.13 GB  yue2/YuE2_VAE_bf16.safetensors
1.35 GB  sheetsage2/SheetSage2_MERT2_bf16.safetensors
------
5.93 GB  total       (3B model — a 24GB card is ample)
```

Weights: `huggingface.co/DeepBeepMeep/TTS`. Model entry is
`defaults/yue2.json`, labelled "Music YuE2 3B".

**Licence: CC BY-NC 4.0 — non-commercial.** Say so before commercial use.

## Cost

```
A40 48GB / RTX 4090 24GB    $0.34-0.35/hr
first session               ~45 min incl. 5.9 GB download   ~$0.30
later sessions              ~2 min startup (volume persists)
50 GB network volume        ~$3.50/month, ongoing
```

## Existing install — reuse it

A provisioned volume already exists; do not rebuild from scratch.

```
volume      <volume-id>  "wan2gp"  50 GB  EU-RO-1   (DC-locked)
contents    /workspace/Wan2GP          repo
            /workspace/Wan2GP/venv     7.6 GB, torch 2.6.0+cu124
            /workspace/Wan2GP/ckpts    ~11 GB weights incl. YuE2 + SheetSage2
            wgp_config.json            already patched to bf16
            /root/start.sh             launch script (recreate if pod is new)
```

Restart is ~2 minutes, not 25: create a pod **in EU-RO-1** with that volume,
then `tmux new-session -d -s srv "bash /root/start.sh > /root/srv.log 2>&1"`.
`/root` is container disk, so `start.sh` must be rewritten on a fresh pod —
only `/workspace` persists.

Wan2GP also carries Wan 2.1/2.2, LTX-2, Hunyuan, Flux, Qwen Image and a Motion
Designer plugin, so the same volume serves video work. Video wants more VRAM
than a 4090; check stock for larger cards **in EU-RO-1 specifically**.

## Setup

Use the `runpod-pods` skill for pod mechanics. Only the volume is special
here: **only `/workspace` survives termination**, so Wan2GP and its venv must
live there.

```bash
set -a; . ~/.hermes/.env; set +a
cd ~/.hermes/skills/mlops-cloud/runpod-pods/scripts

python3 pod.py balance
python3 pod.py gpus --min-vram 24
python3 pod.py volume-create --name wan2gp --size 50 --dc EU-RO-1
POD=$(python3 pod.py create --gpu "NVIDIA A40" --volume <vol-id> \
        --dc EU-RO-1 --ports "7860/http,22/tcp" --name yue2 --json | jq -r .id)
python3 pod.py wait $POD
```

Then on the pod — everything under `/workspace`:

```bash
cd /workspace
export HF_HOME=/workspace/hf              # keeps weights on the volume
[ -d Wan2GP ] || git clone https://github.com/deepbeepmeep/Wan2GP
cd Wan2GP
[ -d venv ] || python -m venv venv
. venv/bin/activate
pip install -q -r requirements.txt
pip install -q yt-dlp                     # not bundled; see below
python wgp.py --listen --server-port 7860
```

`--listen` binds 0.0.0.0 — without it the RunPod proxy sees nothing.

```bash
python3 pod.py url $POD 7860              # open this in a browser
```

## YouTube input

**Wan2GP has no YouTube support** — no yt-dlp in `requirements.txt`, nothing in
the docs. It accepts uploaded audio only. Fetch on the pod instead, so the user
never downloads anything locally:

```bash
cd /workspace/Wan2GP
yt-dlp -x --audio-format mp3 -o "source.%(ext)s" "<url>"
```

The file is then next to the model, ready to select in the UI.

## The int8 Triton crash — fix before generating

On an RTX 4090 the default int8 path crashes at generation time:

```
RuntimeError: No compatible Triton convrot configuration for shape=(1,2048,2048)
  shared/kernels/quanto_int8_triton.py:733
```

**The UI reports this as a video generation error even on the music tab** —
`wgp.py: generate_media()` is the shared entry point for every model, so the
label is generic. Do not chase it as a video problem. The real trace is in
`models/TTS/yue2/pipeline.py` loading SheetSage2.

Fix in `wgp_config.json` before the first run (back it up first):

```python
d["transformer_quantization"]  = "bf16"     # was int8
d["text_encoder_quantization"] = "bf16"     # was int8
d["enable_int8_kernels"]       = 0          # was 1
```

`enable_int8_kernels = 0` alone is **not enough** — the downloaded weights are
themselves the `*_int8_convrot.safetensors` variants, so the quantization keys
must change too. The model config lists bf16 URLs alongside the int8 ones and
will fetch them. Cost: roughly 11 GB VRAM instead of 6 GB, fine on 24 GB.

**Then quarantine the saved queue.** Wan2GP writes `error_queue.zip` on failure
and *replays it at every startup*, so the fixed server re-crashes instantly and
looks unfixed:

```bash
mkdir -p /root/quarantine && mv -f error_queue.zip queue.zip /root/quarantine/
```

## Launching so it stays up

Startup takes ~3 minutes before it prints anything (GGUF kernels, int8 Quanto
injection, frpc tunnel download). Silence is not a hang.

Use `--share`: RunPod's HTTP proxy drops Gradio's websocket and the UI
reconnect-loops, while the `*.gradio.live` tunnel bypasses it and works from a
phone. See the `runpod-pods` skill for the tmux launch pattern and the
`pkill -f wgp.py` self-kill trap — both were hit here.

## Getting the score out

Enable `save_score` (`custom_settings: {"save_score": 1}`). Outputs land in
`/workspace/Wan2GP/outputs/` with matching basenames:

```
<timestamp>_seed<N>_<lyric-prefix>.wav     the audio
<timestamp>_seed<N>_<lyric-prefix>.abc     ABC notation
<timestamp>_seed<N>_<lyric-prefix>.mid     MIDI, format 1
```

The ABC header is the useful part even when the audio disappoints — it reports
the tempo, key and chord progression YuE2 inferred from the source, e.g.
`Q:1/4=130`, `K:D#m`, with chord symbols inline. That transfers directly into
another tool's prompt. The MIDI is skeletal (tens of notes, not a full
arrangement): good as a harmonic guide, not as a finished part.

## Running a cover

In the web UI: pick **Music YuE2 3B**, choose the cover/melody mode, select the
source audio, paste lyrics, set a style prompt.

Defaults from `defaults/yue2.json`:

```
duration        120 s
steps           32
guidance        1.0
top_k / top_p   100 / 0.95
save_score      emits the ABC + MIDI the cover was built from
```

`save_score` is worth enabling — the ABC is editable, so a bad transcription
can be fixed and re-rendered instead of regenerated blind.

Style prompts work like genre tags: `"lo-fi synthwave, crisp drums, 90 bpm,
dreamy female vocals"`.

## Teardown

```bash
python3 pod.py terminate $POD
```

The volume keeps the weights and the install. **Always terminate** — an idle
pod bills the full hourly rate. Report actual spend afterwards.

Delete the volume only when the project ends; it bills while it exists.

## Pitfalls

- **"Video generation error" on the music tab** is the int8 Triton crash — see
  the fix section above. The label is shared across all models.
- **`enable_int8_kernels=0` alone does not fix it** — the weights are int8; the
  quantization keys must change too.
- **`error_queue.zip` replays the crashed task on every boot**, making a good
  fix look broken. Quarantine it.
- **Reading a stale log after a failed restart** — `rm` the log before
  relaunching, or the old traceback reads as a new failure.
- **Installing outside `/workspace`** — lost on terminate. The venv too.
- **Forgetting `HF_HOME`** — weights land on container disk and re-download
  every session, defeating the volume.
- **No `--listen`/`--share`** — Gradio binds localhost, or the proxy drops the
  websocket and the UI reconnect-loops.
- **~3 minutes of silent startup** — not a hang.
- **Expecting the original instrumental** — covers regenerate it. Wrong tool if
  that matters.
- **Volume/GPU datacenter mismatch** — pod will not start.
- **Stock is `Low` on most GPU types**; fallbacks RTX 4090, A6000, 3090 Ti all
  work at ~$0.27-0.34.
- **CC BY-NC weights** — flag before any commercial use.

## Driving it programmatically — don't, yet

Gradio auto-exposes every handler, but Wan2GP declares no `api_name=` on any of
them, so `/info` returns **404** and the generate endpoint is `/submit_20` with
**113 unnamed positional inputs**. One wrong index silently renders with wrong
settings rather than erroring. `wgp.py --help` has no queue/batch/headless
flags either — the UI is the intended interface.

If automation is needed: read `/config`, reconstruct all 113 defaults from the
component list, override only the fields you want, and validate against a
known-good manual render first.

## Verified facts

- `fofr/yue` on Replicate: exists, **text-only**, cannot cover (checked live)
- `fofr/sheetsage`: **404, does not exist**
- `minimax/music-1.5`: 4-min songs but **no audio input** — text-to-music only
- Wan2GP bundles SheetSage2 under `DeepBeepMeep/TTS/sheetsage2/`
- ComfyUI-FL-YuE2 exists but its README calls 24 GB configs **unvalidated**;
  Wan2GP's int8 build is lighter and the better route
