#!/usr/bin/env bash
# Local: bring the refswap pod up, ready to take batches.
#   scripts/refswap_up.sh [--layout serial|shared|split] [--sage 0|1] [--allow-gpu "<RunPod GPU id>"]
# Order: start the existing pod -> if RunPod can't place it, create a new one
# on the same volume with the preferred GPU list -> push secrets + scripts ->
# run pod/bootstrap.sh. Refuses a GPU pricier than the preferred list unless
# --allow-gpu names it (the user's rule: ask before substituting a pricier card).
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
DATA=~/.hermes/data/ref-character-replacement
POD_PY=~/.hermes/skills/mlops-cloud/runpod-pods/scripts/pod.py
VOLUME="${REFSWAP_VOLUME:?set REFSWAP_VOLUME to your RunPod network volume id}"; DC="${REFSWAP_DC:-EU-NL-1}"
PREFERRED=("NVIDIA RTX PRO 6000 Blackwell Server Edition" "NVIDIA RTX PRO 6000 Blackwell Workstation Edition")
LAYOUT=serial; SAGE=0; ALLOW=()
while [ $# -gt 0 ]; do case "$1" in
  --layout) LAYOUT=$2; shift 2;; --sage) SAGE=$2; shift 2;; --allow-gpu) ALLOW+=("$2"); shift 2;;
  *) echo "unknown arg $1"; exit 1;; esac; done
[ "$LAYOUT" = split ] && GPUS=2 || GPUS=1

set -a; . ~/.hermes/.env; set +a
mkdir -p "$DATA"; chmod 700 "$DATA"
[ -f "$DATA/comfy_login.env" ] || { echo "missing $DATA/comfy_login.env"; exit 1; }
POD_ID=$(cat "$DATA/pod_id" 2>/dev/null || echo "${REFSWAP_POD_ID:-}")

python3 "$POD_PY" balance
started=0
if python3 "$POD_PY" info "$POD_ID" 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get('id') and d.get('gpuCount',1)>=$GPUS else 1)"; then
  echo "== starting existing pod $POD_ID"
  python3 "$POD_PY" start "$POD_ID" && { started=1; touch "$DATA/pod_created"; } || echo "   start failed (host has no free GPU?)"
fi
if [ $started = 0 ]; then
  CANDS=("${PREFERRED[@]}" "${ALLOW[@]}")
  for g in "${CANDS[@]}"; do
    echo "== creating on $VOLUME ($DC) with: $g x$GPUS"
    if out=$(python3 "$POD_PY" create --gpu "$g" --gpu-count $GPUS --name h3-refswap --volume $VOLUME --dc $DC \
             --ports "8188/http,22/tcp" --disk 40 --json 2>&1); then
      NEW_ID=$(echo "$out" | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
      # Superseded pod (stopped, host out of GPUs): terminate so stale EXITED
      # pods don't pile up on the volume. Only ours, only when not running.
      if [ -n "$POD_ID" ] && [ "$POD_ID" != "$NEW_ID" ]; then
        st=$(python3 "$POD_PY" info "$POD_ID" 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('desiredStatus',''))" 2>/dev/null)
        [ "$st" = "EXITED" ] && python3 "$POD_PY" terminate "$POD_ID" >/dev/null 2>&1 && echo "   terminated superseded pod $POD_ID"
      fi
      POD_ID=$NEW_ID
      echo "$POD_ID" > "$DATA/pod_id"; touch "$DATA/pod_created"; started=1; break
    fi
    echo "   no: $(echo "$out" | tail -1 | cut -c1-160)"
  done
fi
[ $started = 1 ] || { echo "NO GPU AVAILABLE on the preferred list. Re-run with --allow-gpu \"<id>\" after the user OKs the price."; exit 2; }

python3 "$POD_PY" wait "$POD_ID" --timeout 600
INFO=$(python3 "$POD_PY" info "$POD_ID")
read -r IP PORT RATE GPU <<<"$(echo "$INFO" | python3 -c "
import json,sys; d=json.load(sys.stdin); pm=d.get('portMappings') or {}
print(d.get('publicIp'), pm.get('22'), d.get('costPerHr') or 0, (d.get('machine') or {}).get('gpuTypeId','?').replace(' ','_'))")"
echo "== pod $POD_ID  $GPU  \$$RATE/hr  ssh $IP:$PORT"
echo "$IP $PORT" > "$DATA/pod_ssh"
SSH="ssh -p $PORT -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=20 -i $HOME/.ssh/id_ed25519 root@$IP"
for i in $(seq 1 24); do $SSH true 2>/dev/null && break; sleep 5; done

# ---- push: secrets (container disk only, never /workspace) + scripts ---------
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
( umask 077
  { echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY_REFSWAP"; grep -E '^COMFY_(USER|PASS)=' "$DATA/comfy_login.env"; } > "$TMP/secrets.env" )
mkdir -p "$TMP/pod"; cp "$SK"/pod/*.py "$SK"/pod/*.sh "$TMP/pod/"
cp -r "$SK/comfy_node" "$TMP/pod/"; cp "$SK/workflows/h3_refswap.json" "$TMP/pod/"
cp ~/.hermes/skills/creative/comfyui/scripts/upscale_run.py "$TMP/pod/"
# tar over ssh, NOT rsync: the RunPod base image has no rsync (placed pod died
# here on 2026-09-28 with "rsync: command not found", rc 12).
tar -C "$TMP" -czf - pod secrets.env | $SSH "umask 077; mkdir -p /root && tar --no-same-owner -C /root -xzf -"
$SSH "chmod 600 /root/secrets.env; LANE_LAYOUT=$LAYOUT SAGE=$SAGE GPU_NAME='${GPU//_/ }' GPU_RATE=$RATE bash /root/pod/bootstrap.sh"
echo "== URL: https://$POD_ID-8188.proxy.runpod.net   (login in $DATA/comfy_login.env)"
