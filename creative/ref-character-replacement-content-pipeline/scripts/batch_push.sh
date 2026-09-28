#!/usr/bin/env bash
# Local: push a batch to the pod and start its runner in tmux.
#   scripts/batch_push.sh <batch-name> [--tag A] [--only J01,J02] [--force]
set -euo pipefail
B=$1; shift
DATA=~/.hermes/data/ref-character-replacement
LOCAL="$DATA/batches/$B"
[ -f "$LOCAL/manifest.csv" ] || { echo "no manifest at $LOCAL"; exit 1; }
read -r IP PORT < "$DATA/pod_ssh"
E="ssh -p $PORT -o StrictHostKeyChecking=no -o ConnectTimeout=20 -i $HOME/.ssh/id_ed25519"
# tar over ssh (no rsync on the RunPod image). Inputs + manifest only.
# --no-same-owner: root on the pod + MooseFS volume refuses chown to uid 1000
# ("Cannot change ownership", tar exit 2) - killed the 2026-09-28 session.
tar -C "$LOCAL" -czf - --exclude renders --exclude upscaled --exclude compare --exclude sidecars \
  --exclude upscale_queue --exclude '*.csv.synced' . | $E "root@$IP" "mkdir -p /workspace/batches/$B && tar --no-same-owner -C /workspace/batches/$B -xzf -"
SESSION="run_${B//[^a-zA-Z0-9]/_}"
$E "root@$IP" "rm -f /root/STOP_REQUESTED; tmux kill-session -t $SESSION 2>/dev/null; \
  tmux new-session -d -s $SESSION '/workspace/venv-clean/bin/python -u /root/pod/batch_runner.py /workspace/batches/$B $* >> /root/batch_$B.log 2>&1'; \
  sleep 3; tail -3 /root/batch_$B.log"
echo "runner started: tmux $SESSION, log /root/batch_$B.log"
