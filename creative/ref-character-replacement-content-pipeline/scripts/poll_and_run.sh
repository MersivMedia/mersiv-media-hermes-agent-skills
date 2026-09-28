#!/usr/bin/env bash
# Poll for an approved GPU every POLL_S seconds; when one is placed, run the
# whole perf session unattended and stop the pod.
#   scripts/poll_and_run.sh <source.mp4> <reference.png>
# Approved order (user, 2026-09-28): RTX PRO 6000 -> H100 PCIe -> H100 SXM.
# Status lines go to $DATA/poll.log; final state in $DATA/poll.status.
#
# STOP GUARANTEE (after the 2026-09-28 idle-H100 incident, $4.48 lost):
#   once a pod exists, EVERY exit path of this script stops it: session
#   failure, session success, watcher death, signal, or `set -e` style abort.
#   A best-effort sync runs first under a hard timeout; the stop never waits
#   on anything unbounded.
# Script paths are overridable (env) only so tests/test_failpath.sh can stub them.
set -uo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
DATA=${REFSWAP_DATA:-~/.hermes/data/ref-character-replacement}
SRC=$1; REF=$2; POLL_S=${POLL_S:-60}; MAX_HOURS=${MAX_HOURS:-24}
UP=${REFSWAP_UP:-"$SK/scripts/refswap_up.sh"}
PERF=${REFSWAP_PERF:-"$SK/scripts/perf_session.sh"}
SYNC=${REFSWAP_SYNC:-"$SK/scripts/batch_sync.py"}
POD_PY=${REFSWAP_POD_PY:-~/.hermes/skills/mlops-cloud/runpod-pods/scripts/pod.py}
SYNC_TIMEOUT=${SYNC_TIMEOUT:-600}
LOG=$DATA/poll.log; ST=$DATA/poll.status
[ -z "${REFSWAP_TEST:-}" ] && { set -a; . ~/.hermes/.env; set +a; }
T0=$(date +%s); n=0; POD_LIVE=0; STOPPED=0

stop_pod() {   # idempotent; called from every exit path once a pod exists
  [ "$POD_LIVE" = 1 ] && [ "$STOPPED" = 0 ] || return 0
  STOPPED=1
  local id; id=$(cat "$DATA/pod_id" 2>/dev/null)
  echo "$(date -u +%H:%M:%S) stopping pod $id ($1)" >> "$LOG"
  for i in 1 2 3; do
    python3 "$POD_PY" stop "$id" >> "$LOG" 2>&1 && break
    echo "  stop attempt $i failed; retrying" >> "$LOG"; sleep 10
  done
  # verify: never trust the stop call alone
  local s; s=$(python3 "$POD_PY" info "$id" 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('desiredStatus','?'))" 2>/dev/null)
  echo "  pod $id desiredStatus=$s" >> "$LOG"
  [ "$s" = EXITED ] || echo "  WARNING: pod $id NOT confirmed stopped (status=$s) - stop it by hand" | tee -a "$LOG" >> "$ST"
}
sync_batches() {   # best effort, bounded; outputs stay on the volume if it fails
  for b in "$@"; do
    [ -d "$DATA/batches/$b" ] || continue
    timeout "$SYNC_TIMEOUT" python3 "$SYNC" "$b" >> "$LOG" 2>&1 || echo "  sync $b failed/timed out (outputs remain on the volume)" >> "$LOG"
  done
}
trap 'stop_pod "exit trap"' EXIT
trap 'stop_pod "signal"; exit 130' INT TERM HUP

echo "POLLING since $(date -u +%FT%TZ)" > "$ST"
while :; do
  n=$((n+1))
  if [ $(( ($(date +%s)-T0)/3600 )) -ge "$MAX_HOURS" ]; then
    echo "GAVE UP after ${MAX_HOURS}h, $n attempts, no approved GPU" | tee -a "$LOG" > "$ST"; exit 2
  fi
  rm -f "$DATA/pod_created"
  bash "$UP" --layout serial --sage 0 \
       --allow-gpu "NVIDIA H100 PCIe" --allow-gpu "NVIDIA H100 80GB HBM3" > "$DATA/up_attempt.log" 2>&1
  rc=$?
  # refswap_up writes pod_created the moment a pod is placed/started, so a
  # later bring-up failure still counts as a live, billing pod.
  [ -f "$DATA/pod_created" ] && POD_LIVE=1
  if [ $rc = 2 ] && [ "$POD_LIVE" = 0 ]; then
    [ $((n % 15)) = 1 ] && echo "$(date -u +%H:%M) attempt $n: no approved GPU" >> "$LOG"
    sleep "$POLL_S"; continue
  fi
  cat "$DATA/up_attempt.log" >> "$LOG"
  if [ $rc != 0 ]; then
    echo "BRING-UP FAILED rc=$rc on attempt $n" | tee -a "$LOG" > "$ST"
    exit 1            # EXIT trap stops the pod
  fi
  break
done

D=$(date +%F); export PERF_DATE=$D
BATCHES=("${D}_perf-a-serial" "${D}_perf-b-sage" "${D}_perf-c-shared")
GPU=$(grep -m1 "^== pod" "$DATA/up_attempt.log")
echo "RUNNING session on: $GPU (placed after $n attempts)" > "$ST"
MAX_GPU_MIN=${MAX_GPU_MIN:-90} bash "$PERF" "$SRC" "$REF" >> "$LOG" 2>&1
PS=$?
echo "$(date -u +%H:%M:%S) perf_session exit $PS; syncing (max ${SYNC_TIMEOUT}s/batch) then stopping NOW" >> "$LOG"
sync_batches "${BATCHES[@]}"
stop_pod "session finished rc=$PS"
python3 "$POD_PY" balance >> "$LOG" 2>&1
{ echo "DONE perf_session=$PS on $GPU"; tail -4 "$LOG"; } > "$ST"
[ "$PS" = 0 ]
