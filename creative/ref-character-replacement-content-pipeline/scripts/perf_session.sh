#!/usr/bin/env bash
# Local: the v1.1 perf test session. Assumes refswap_up.sh already ran
# (serial layout, sage off) and autostop_watch.sh is running in the background.
#   scripts/perf_session.sh <source.mp4> <reference.png>
# Phases (each its own batch so results stay separable):
#   A  serial, sage off : J01 480p->1440;2160  J02 768p->1440;2160  J03 768p 3 steps
#   B  sage on          : J01 = A.J02 settings (render lane restarted with sage)
#   C  shared layout    : J01, J02 768p->2160 with render+upscale lanes overlapping
# Budget guard: aborts before a phase if the session has run past MAX_GPU_MIN.
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
DATA=~/.hermes/data/ref-character-replacement
SRC=$1; REF=$2; MAX_GPU_MIN=${MAX_GPU_MIN:-90}
D=${PERF_DATE:-$(date +%F)}; T0=$(date +%s)
read -r IP PORT < "$DATA/pod_ssh"
SSH="ssh -p $PORT -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o ServerAliveInterval=20 -i $HOME/.ssh/id_ed25519 root@$IP"
guard() { local m=$(( ($(date +%s)-T0)/60 )); [ $m -lt "$MAX_GPU_MIN" ] || { echo "BUDGET: ${m} min used, cap ${MAX_GPU_MIN}; stopping here"; exit 4; }; }
wait_batch() {   # batch -> waits for its runner AND its upscale tickets
  local b=$1
  while $SSH "pgrep -f '[b]atch_runner.py /workspace/batches/$b' >/dev/null || ls /workspace/batches/$b/upscale_queue/*.json /workspace/batches/$b/upscale_queue/*.working >/dev/null 2>&1"; do
    sleep 30; $SSH "tail -1 /root/batch_$b.log; tail -1 /root/upworker.log" 2>/dev/null | sed 's/^/   /'
    guard
  done
  $SSH "grep -E '^\[J|RUNNER_DONE' /root/batch_$b.log | tail -8"
}
mk() { python3 "$SK/scripts/batch_new.py" "$@"; }
# Hold autostop for the whole session: lane restarts between phases look idle.
$SSH "touch /root/SESSION_HOLD"
trap '$SSH "rm -f /root/SESSION_HOLD" 2>/dev/null' EXIT

# ---- A: serial baseline -------------------------------------------------------
A="${D}_perf-a-serial"
mk "$A" --sources "$SRC" --refs "$REF" --pairs 1:1,1:1,1:1 --replace-bg 1 --duration 5
python3 - "$DATA/batches/$A/manifest.csv" <<'EOF'
import csv,sys
p=sys.argv[1]; rows=list(csv.DictReader(open(p)))
rows[0].update(res="480", upscale="1440;2160")
rows[1].update(res="768", upscale="1440;2160")
rows[2].update(res="768", steps="3", upscale="")
w=csv.DictWriter(open(p,"w",newline=""),fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
EOF
python3 "$SK/scripts/show_manifest.py" "$DATA/batches/$A/manifest.csv"
guard; bash "$SK/scripts/batch_push.sh" "$A" --tag A; wait_batch "$A"

# ---- B: SageAttention -----------------------------------------------------------
guard
$SSH "SAGE=1 LANE_LAYOUT=serial bash /root/pod/bootstrap.sh --restart-render"
B="${D}_perf-b-sage"
mk "$B" --sources "$SRC" --refs "$REF" --pairs 1:1 --replace-bg 1 --duration 5 --res 768
bash "$SK/scripts/batch_push.sh" "$B" --tag B; wait_batch "$B"
SAGE_OK=$($SSH "grep -ci sage /root/comfy_render.log" || echo 0)
echo "sage mentions in render log: $SAGE_OK"

# ---- C: shared-GPU lanes ------------------------------------------------------
guard
KEEP_SAGE=$( [ "${SAGE_KEEP:-auto}" = auto ] && echo 0 || echo "$SAGE_KEEP" )
$SSH "LANE_LAYOUT=shared SAGE=$KEEP_SAGE bash /root/pod/bootstrap.sh" | tail -6
C="${D}_perf-c-shared"
mk "$C" --sources "$SRC" --refs "$REF" --pairs 1:1,1:1 --replace-bg 1 --duration 5 --res 768 --upscale 2160
python3 - "$DATA/batches/$C/manifest.csv" <<'EOF'
import csv,sys
p=sys.argv[1]; rows=list(csv.DictReader(open(p))); rows[1]["seed"]="777"   # distinct renders, no cache hit
w=csv.DictWriter(open(p,"w",newline=""),fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
EOF
python3 "$SK/scripts/show_manifest.py" "$DATA/batches/$C/manifest.csv"
bash "$SK/scripts/batch_push.sh" "$C" --tag C; wait_batch "$C"

# ---- report -----------------------------------------------------------------------
for b in "$A" "$B" "$C"; do python3 "$SK/scripts/batch_sync.py" "$b" --no-drive; done
scp -q -P "$PORT" -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 "root@$IP:/root/gpu.csv" "$DATA/batches/$C/gpu.csv" || true
python3 "$SK/scripts/perf_report.py" "$A" "$B" "$C" | tee "$DATA/batches/${D}_perf_report.md"
echo "PERF_SESSION_DONE after $(( ($(date +%s)-T0)/60 )) min"
