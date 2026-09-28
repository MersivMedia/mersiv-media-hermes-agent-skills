# ComfyUI + LTX-2.5 on a Rented GPU Pod

Verified end-to-end on a RunPod L40S (48 GB) with a 100 GB network volume,
Sept 2026. Every command here was actually run; the pitfalls are failures
that occurred, not hypotheticals.

Total wall time on first run: ~2 hours, most of it the torch reinstall loop
documented below. Following this file should cut it to ~40 minutes.

## Why a network volume

Put ComfyUI, the venv, AND the models on the persistent volume
(`/workspace`). Terminating the pod then costs nothing but the volume, and
redeploying is a ~3-minute reattach with zero rebuild. Container disk is
wiped on termination — never install there.

## Provisioning (RunPod GraphQL)

```graphql
mutation {
  podFindAndDeployOnDemand(input: {
    cloudType: SECURE
    gpuCount: 1
    volumeInGb: 0
    containerDiskInGb: 40
    gpuTypeId: "NVIDIA L40S"
    name: "comfy"
    imageName: "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
    dataCenterId: "EU-NL-1"
    networkVolumeId: "<volume-id>"
    volumeMountPath: "/workspace"
    ports: "8188/http,22/tcp"
    env: [{ key: "PUBLIC_KEY", value: "<your ssh public key>" }]
  }) { id name costPerHr }
}
```

Two provisioning traps, both hit on the first attempt:

- **`env: PUBLIC_KEY` is mandatory for SSH.** API-deployed pods do NOT
  inherit the account SSH key the way console-deployed pods do. Without it
  every connection is `Connection refused` forever and the pod is unusable.
- **Do not pass `dockerArgs`.** Overriding the command (e.g.
  `bash -c 'sleep infinity'`) replaces the image start script that launches
  sshd. The pod runs but you can't get in.

The network volume is pinned to one data center — the pod must be deployed
in the same `dataCenterId` or it cannot attach.

## Model download (gated repo)

Check gate access with a **real file HEAD**, not the metadata endpoint:

```bash
curl -sIL -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $HF_TOKEN" \
  "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-audio-vae-bf16.safetensors"
```

`403` means the license has not been accepted — the account owner must click
accept at the repo page. A fine-grained token with `canReadGatedRepos: true`
does not bypass this, and `GET /api/models/<repo>` returns 200 regardless.

Store the token in a file (`/workspace/.hf_token`, `umask 077`) rather than
passing it on a command line where it lands in shell history and logs.

### LTX-2.5 file sizes (full repo is 201 GB — do not clone it)

| File | Size |
|---|---|
| `diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot` | 21.5 GB |
| `text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot` | 15.4 GB |
| `loras/ltx-2.5-22b-distilled-lora-450-bf16` | 8.9 GB |
| `vae/` (video + conv + audio) | 3.3 GB |
| `latent_upscale_models/` (spatial + temporal) | 1.3 GB |
| `model_patches/ltx-2.5-duration-head-bf16` | ~4 MB |
| **total** | **~47 GB** |

Pick **distilled** over **dev** for demos — far fewer steps per clip, so
screen recordings aren't dominated by a progress bar. Downloading both
transformers wastes 21.5 GB. The bf16 transformer (42 GB) is unnecessary
when the int8 fits comfortably in 48 GB VRAM.

Download into ComfyUI's folder layout directly:

```
/workspace/ComfyUI/models/{diffusion_models,text_encoders,vae,loras,
                           latent_upscale_models,model_patches}/
```

## The venv (this is where the time goes)

```bash
# NO --system-site-packages. See pitfall 13 in SKILL.md.
python3 -m venv /workspace/venv
source /workspace/venv/bin/activate
pip install --upgrade pip wheel

# torch FIRST, and NEW. cu128 wheels.
pip install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu128

# Verify resolution + CUDA BEFORE installing anything else.
python -c "import torch; print(torch.__version__, torch.__file__, torch.cuda.is_available())"
# Path must be inside /workspace/venv. Must print True.

cd /workspace/ComfyUI
pip install -r requirements.txt

# The gate that decides whether the server will boot at all:
python -c "import comfy_kitchen; print('KITCHEN_OK')"
```

Verified compatibility:

| torch | `import comfy_kitchen` |
|---|---|
| 2.4.1+cu124 (image default) | FAILS |
| 2.6.0+cu124 | FAILS |
| 2.11.0+cu128 | **OK** |

Both failures raise the identical `infer_schema ... stride has unsupported
type list[int]` ValueError. The error looks like an incompatibility with a
too-new torch; it is the opposite.

## Launch

Always truncate the log first — a stale traceback after a failed start is
indistinguishable from a fresh one:

```bash
pkill -f "main.py --listen"; sleep 3
: > /workspace/comfy.log
cd /workspace/ComfyUI
setsid nohup /workspace/venv/bin/python main.py \
  --listen 0.0.0.0 --port 8188 > /workspace/comfy.log 2>&1 < /dev/null &
```

Confirm it is genuinely up — process AND health, not one or the other:

```bash
pgrep -af "main.py --listen"
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8188/system_stats
```

Model loading takes 60-90 s after the process appears. An empty `pgrep`
means the launch never ran — check the boot log, not `comfy.log`.

## Verify models are actually registered

Server booting proves nothing about the models. Enumerate them:

```bash
for f in diffusion_models text_encoders vae loras latent_upscale_models model_patches; do
  echo "[$f]"; curl -s "http://127.0.0.1:8188/models/$f"
done
```

Each folder must list its expected files. Empty output means a wrong path or
a partial download.

## Browser access

RunPod exposes HTTP ports through a proxy — no ufw changes, no tunnel:

```
https://<pod-id>-8188.proxy.runpod.net
```

Confirm from outside the pod with a `curl` on `/system_stats` before handing
the URL to anyone. The internal `100.65.x.x` address in the ports list is not
reachable from your machine.

## Cost discipline

The pod bills whenever it exists, including while you debug a venv. Check
uptime and spend from the API rather than guessing:

```graphql
query { pod(input:{podId:"<id>"}) { costPerHr runtime { uptimeInSeconds } } }
```

Terminate as soon as recording/generation is done. The volume retains
ComfyUI, the venv, and all models, so the next session is a reattach.
