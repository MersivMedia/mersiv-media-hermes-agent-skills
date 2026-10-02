# RunPod: inspecting an existing volume and bringing up large models

Companion to `runpod-preflight-queries.md`. Covers step 5 ("verify the target
artifact") on RunPod specifically, plus the setup traps hit while adding ~67 GB
of MiniMax H3 weights to an existing ComfyUI volume. (Belongs conceptually in
`runpod-pods`, which is user-owned; filed here instead.)

## Inspecting a volume without booting a pod

**Walk prefixes with `Delimiter="/"`; never paginate the whole bucket.** A full
`list_objects_v2` paginate over a ~200 GB ComfyUI volume ran past 180 s.
One-level prefix walks return in seconds:

```python
def ls(s3, bucket, prefix=""):
    r = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter="/", MaxKeys=200)
    return ([p["Prefix"] for p in r.get("CommonPrefixes", [])],
            [(o["Key"], o["Size"]) for o in r.get("Contents", [])])
```

Endpoint is `https://s3api-<dc-lowercase>.runpod.io`, bucket = volume id. Some
storage datacenters have no S3 endpoint we can resolve (`s3api-eu-nl-1` failed
DNS). Then the first pod boot is the inspection — say so in the plan.

## First-boot inspection over SSH

```bash
du -sh --apparent-size /workspace                 # compare to the volume quota
find /workspace -maxdepth 3 -name main.py -path "*ComfyUI*"
cd /workspace/ComfyUI && git log -1 --format="%h %ci %s"
grep -rl "<NodeClass>" --include=*.py comfy_extras comfy_api_nodes nodes.py
find -L models -type f -size +3G -printf "%s %P\n" | sort -rn
grep -h main.py /workspace/*.sh                   # which venv was actually used
```

- Core ComfyUI may already ship the node a workflow needs; a workflow's custom
  node dependency (e.g. `VHS_LoadVideo` → ComfyUI-VideoHelperSuite) may not.
- **Test every venv on the volume.** An older `/workspace/venv` failed
  `import torch` with `libcudnn.so.9` missing while `/workspace/venv-clean`
  ran torch 2.11+cu128 on the GPU. The previous launch script names the good one.

## Quota before download

Compare `du` with the volume size **before** pulling weights; a volume at
190/200 GB cannot take 67 GB. Growing is a REST PATCH (no restart) but it is a
recurring-cost decision the user approves — see SKILL.md pitfalls:

```bash
curl -s -X PATCH -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" -d '{"size":270}' \
  https://rest.runpod.io/v1/networkvolumes/<id>
```

## Downloading weights

- tmux + script file + log in `/root`; stage on the volume, then move into
  `models/<type>/`; skip existing files >100 MB so re-runs resume.
- Throughput observed: 34 GB in 77 s, 27 GB in ~60 s. Downloads are not the
  slow part — do not pad estimates for them.
- `HF_HUB_ENABLE_HF_TRANSFER` is deprecated and ignored in current
  `huggingface_hub`; `HF_XET_HIGH_PERFORMANCE=1` replaces it.
- Pin `"huggingface_hub<2.0"` in ComfyUI venvs. `pip install -U` pulled 2.0,
  which `tokenizers` rejects, and the text encoders load through tokenizers.

## Quantisation follows the GPU

NVFP4 files are Blackwell-native (RTX 5090 / RTX PRO 6000 / B200). On Hopper
(H100) or Ampere (A40) use the int8/fp8 variant. A GPU substitution therefore
changes the download list — one more reason a substitution needs the user's yes.

## Secrets on a rented pod

Writing an API key to a pod or volume is the user's call, not a setup step. An
approval timeout on it counts as a no: stop, and don't retry by another route.
Recommend a dedicated revocable key. Write it via stdin to a `chmod 600` file
on the **container disk (`/root`)**, not the volume. The MooseFS volume ignores
chmod, so a 600 file read back as 666. Read the key from the environment at
runtime, and never put it in workflow JSON or widgets.

CPU pods, moving a volume to another DC, and stuck placements are in
`runpod-cpu-pods-and-volume-moves.md`.
