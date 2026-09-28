#!/usr/bin/env bash
# Fetch SCAIL-2 — the node actually built for in-video character replacement.
#
# Four of six required files are already on disk from earlier work:
#   text_encoders/umt5_xxl_fp8_e4m3fn_scaled, clip_vision/clip_vision_h,
#   vae/wan_2.1_vae, diffusion_models/sam3.1_multiplex_fp16
#
# Taking int8_convrot (16.65 GB) over the docs' fp16 (32.79 GB): same model
# quantized, and fp16 would land at exactly 200/200 GB with zero margin.
#
# Disk (quota 200, ~164 used): +19.85 GB -> ~184 GB, 16 GB free.
set -uo pipefail

export HF_TOKEN="$(cat /workspace/.hf_token)"
PY=/workspace/venv-clean/bin/python
R=/workspace/ComfyUI/models
mkdir -p "$R"/{diffusion_models,loras}

# repo|path_in_repo|dest_subdir|final_name
JOBS="
Comfy-Org/SCAIL-2|diffusion_models/wan2.1_14B_SCAIL_2_int8_convrot.safetensors|diffusion_models|wan2.1_14B_SCAIL_2_int8_convrot.safetensors
Comfy-Org/SCAIL-2|loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors|loras|wan2.1_SCAIL_2_DPO_lora_bf16.safetensors
Comfy-Org/SCAIL-2|loras/wan2.1_SCAIL_2_relight_lora_bf16.safetensors|loras|wan2.1_SCAIL_2_relight_lora_bf16.safetensors
Kijai/WanVideo_comfy|Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors|loras|lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors
"

for job in $JOBS; do
  [ -z "$job" ] && continue
  repo="${job%%|*}"; r1="${job#*|}"
  src="${r1%%|*}";   r2="${r1#*|}"
  dst="${r2%%|*}";   name="${r2##*|}"
  target="$R/$dst/$name"

  if [ -f "$target" ]; then echo "SKIP (exists): $name"; continue; fi
  echo "FETCH: $name -> $dst/"
  "$PY" - "$repo" "$src" "$R/$dst" "$name" <<'PYEOF'
import os, shutil, sys
from huggingface_hub import hf_hub_download
repo, path, outdir, finalname = sys.argv[1:5]
p = hf_hub_download(repo_id=repo, filename=path, local_dir=outdir + "/__stg")
final = os.path.join(outdir, finalname)
shutil.move(p, final)
print("OK", final, os.path.getsize(final))
PYEOF
  [ $? -ne 0 ] && echo "FAILED: $src"
  du -sh /workspace 2>/dev/null | tail -1
done

rm -rf "$R"/*/__stg
echo "SCAIL_FETCH_COMPLETE"
du -sh /workspace
