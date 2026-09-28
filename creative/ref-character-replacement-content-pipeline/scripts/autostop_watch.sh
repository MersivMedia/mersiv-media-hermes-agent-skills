#!/usr/bin/env bash
# Local auto-stop watcher: run in the background (terminal background=true,
# notify=true) for the whole pod session.
#   scripts/autostop_watch.sh [batch-name ...]
# Every 60 s: if the pod has written /root/STOP_REQUESTED, sync every named
# batch (renders, upscales, sidecars, results, Drive), touch /root/SYNCED,
# stop the pod, print the balance. Sync first because the EU-NL-1 volume has
# no S3 endpoint: once the pod is stopped the outputs can't be reached.
# Hard cap: stops the pod after MAX_MIN minutes regardless (default 120).
set -uo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
DATA=~/.hermes/data/ref-character-replacement
POD_PY=~/.hermes/skills/mlops-cloud/runpod-pods/scripts/pod.py
MAX_MIN=${MAX_MIN:-120}
set -a; . ~/.hermes/.env; set +a
POD_ID=$(cat "$DATA/pod_id" 2>/dev/null || echo "${REFSWAP_POD_ID:?no pod id: set REFSWAP_POD_ID or write $DATA/pod_id}")
read -r IP PORT < "$DATA/pod_ssh"
SSH="ssh -p $PORT -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $HOME/.ssh/id_ed25519 root@$IP"
T0=$(date +%s)
stop_now() {
  for b in "$@"; do echo "== sync $b"; python3 "$SK/scripts/batch_sync.py" "$b" || echo "   sync FAILED for $b (outputs remain on the volume)"; done
  $SSH "touch /root/SYNCED" 2>/dev/null
  python3 "$POD_PY" stop "$POD_ID"
  python3 "$POD_PY" balance
}
while true; do
  if $SSH "test -f /root/STOP_REQUESTED" 2>/dev/null; then
    echo "pod reports all work done ($(( ($(date +%s)-T0)/60 )) min into session)"
    stop_now "$@"; exit 0
  fi
  if [ $(( ($(date +%s)-T0)/60 )) -ge "$MAX_MIN" ]; then
    echo "HARD CAP ${MAX_MIN} min reached: syncing and stopping regardless"
    stop_now "$@"; exit 3
  fi
  sleep 60
done
