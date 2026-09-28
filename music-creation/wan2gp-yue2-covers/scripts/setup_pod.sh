#!/usr/bin/env bash
# Bring up Wan2GP + YuE2 on a RunPod pod. Run ON THE POD, not locally.
#
#   curl -sL <raw-url>/setup_pod.sh | bash
#   # or: scp it over and `bash setup_pod.sh`
#
# Everything lands in /workspace so it survives pod termination.
set -euo pipefail

WS=/workspace
export HF_HOME=$WS/hf            # model cache on the persistent volume
export PIP_DISABLE_PIP_VERSION_CHECK=1

if [ ! -d "$WS" ]; then
  echo "ERROR: /workspace missing — no network volume attached."
  echo "Without it the 5.9 GB of weights re-download every session."
  exit 1
fi

echo "==> workspace: $(df -h $WS | awk 'NR==2{print $4}') free"
mkdir -p "$HF_HOME"
cd "$WS"

if [ -d Wan2GP/.git ]; then
  echo "==> Wan2GP present, updating"
  cd Wan2GP && git pull --ff-only || true
else
  echo "==> cloning Wan2GP"
  git clone --depth 1 https://github.com/deepbeepmeep/Wan2GP
  cd Wan2GP
fi

if [ ! -d venv ]; then
  echo "==> creating venv (inside /workspace so it persists)"
  python -m venv venv
fi
# shellcheck disable=SC1091
. venv/bin/activate

echo "==> installing requirements (slow on first run)"
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q yt-dlp            # Wan2GP does not bundle it; needed for YouTube

python - <<'PY'
import torch
print(f"==> torch {torch.__version__}  cuda={torch.cuda.is_available()}")
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"    {p.name}  {p.total_memory/1e9:.1f} GB")
    if p.total_memory/1e9 < 10:
        print("    WARNING: under 10 GB — YuE2 needs ~6 GB plus headroom")
else:
    print("    ERROR: no CUDA device visible")
PY

cat <<'EOF'

==> ready

  fetch a song from YouTube (optional):
      cd /workspace/Wan2GP && . venv/bin/activate
      yt-dlp -x --audio-format mp3 -o "source.%(ext)s" "<url>"

  start the UI (--listen is required for the RunPod proxy):
      python wgp.py --listen --server-port 7860

  then open the proxy URL:
      https://<pod-id>-7860.proxy.runpod.net

  in the UI: model "Music YuE2 3B" -> cover mode -> pick source audio
  -> paste lyrics -> style prompt. Enable save_score to keep the ABC.
  First generation downloads ~5.9 GB into /workspace/hf (once only).

  TERMINATE THE POD when finished — idle pods bill at the full rate.
EOF
