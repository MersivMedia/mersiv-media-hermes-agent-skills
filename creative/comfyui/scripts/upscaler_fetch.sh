#!/usr/bin/env bash
# Upscalers: SeedVR2 (video) + ESRGAN-family (image).
#
# SeedVR2 is the top-ranked video upscaler for temporal consistency —
# ComfyUI's own upscaling guide puts it first for realism and character
# consistency, which matters when the subject is a replaced character.
# Its nodes are already native (SeedVR2Preprocess / Conditioning /
# TemporalChunk / TemporalMerge / PostProcessing); only weights were missing.
#
# Taking 7b_int8_convrot (8.33 GB) over fp16 (16.48 GB): same model quantized,
# and fp16 would not fit the remaining ~18 GB alongside the image upscalers.
#
# Disk (quota 200, ~182 used): +8.7 GB -> ~191 GB.
set -uo pipefail

export HF_TOKEN="$(cat /workspace/.hf_token)"
PY=/workspace/venv-clean/bin/python
R=/workspace/ComfyUI/models
mkdir -p "$R"/{diffusion_models,upscale_models}

# repo|path_in_repo|dest_subdir|final_name
JOBS="
Comfy-Org/SeedVR2|diffusion_models/seedvr2_7b_sharp_int8_convrot.safetensors|diffusion_models|seedvr2_7b_sharp_int8_convrot.safetensors
Kim2091/UltraSharp|4x-UltraSharp.pth|upscale_models|4x-UltraSharp.pth
ai-forever/Real-ESRGAN|RealESRGAN_x4.pth|upscale_models|RealESRGAN_x4.pth
ai-forever/Real-ESRGAN|RealESRGAN_x2.pth|upscale_models|RealESRGAN_x2.pth
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
done

rm -rf "$R"/*/__stg
echo "UPSCALER_FETCH_COMPLETE"
du -sh /workspace
