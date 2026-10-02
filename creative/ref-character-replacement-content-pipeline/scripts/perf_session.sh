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
# wait_batch: waits for the batch's runner AND its upscale tickets. On
# 2026-09-28 the upscale worker died mid-batch and this loop kept waiting on
# its orphaned tickets for ~25 min until the budget cap. Now each tick asks the
# pod for a status word; a dead worker (no process, or heartbeat >120 s old)
# with tickets still pending is restarted ONCE, then the batch is abandoned.
# Log lines are printed only when they change.
WAIT_TICK=${WAIT_TICK:-30}
pod_status() { $SSH "bash /root/pod/batch_status.sh $1" 2>/dev/null || echo "SSH_FAIL"; }
wait_batch() {
  local b=$1 restarted=0 last="" st line
  while :; do
    st=$(pod_status "$b")
    case "$st" in
      DONE) break ;;
      WORKER_DEAD*)
        echo "   !! upscale worker dead ($st)"
        $SSH "tail -15 /root/upworker.log" 2>/dev/null | sed 's/^/   | /'
        if [ $restarted = 0 ]; then
          restarted=1; $SSH "bash /root/pod/bootstrap.sh --restart-upworker" | sed 's/^/   /'
        else
          echo "   !! worker died twice on $b; abandoning its remaining upscales"
          $SSH "for f in /workspace/batches/$b/upscale_queue/*.json /workspace/batches/$b/upscale_queue/*.json.working; do [ -e \"\$f\" ] && mv \"\$f\" \"\${f%.working}.abandoned\"; done; true"
          break
        fi ;;
    esac
    line=$($SSH "tail -1 /root/batch_$b.log; tail -1 /root/upworker.log" 2>/dev/null | tr '\n' '|')
    [ "$line" != "$last" ] && { echo "   $st :: ${line%|}"; last=$line; }
    guard; sleep "$WAIT_TICK"
  done
  $SSH "grep -E '^\[J|RUNNER_DONE' /root/batch_$b.log | tail -8"
}
mk() { python3 "$SK/scripts/batch_new.py" "$@"; }
# Hold autostop for the whole session: lane restarts between phases look idle.
$SSH "touch /root/SESSION_HOLD"
trap '$SSH "rm -f /root/SESSION_HOLD" 2>/dev/null' EXIT

# PHASES (default ABC): comma-free letters to run, e.g. PHASES=RBC after a partial
# session. R = recover phase A's stranded upscales (re-ticket what's missing from
# the renders already on the volume) instead of re-rendering A.
PHASES=${PHASES:-ABC}
has() { case "$PHASES" in *"$1"*) return 0;; *) return 1;; esac; }

# ---- A: serial baseline -------------------------------------------------------
A="${A_BATCH:-${D}_perf-a-serial}"
# R runs after B and C (see bottom): the missing measurements come first and R
# is what gets cut if the budget runs out. R_TARGETS: heights to re-ticket;
# "@2160" = adopt an already-saved file only, never start a new 4K job.
R_TARGETS=${R_TARGETS:-1440 @2160}
if has A; then
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
fi

# ---- B: SageAttention -----------------------------------------------------------
B=""; C=""
if has B; then
guard
$SSH "SAGE=1 LANE_LAYOUT=serial bash /root/pod/bootstrap.sh --restart-render"
B="${D}_perf-b-sage"
mk "$B" --sources "$SRC" --refs "$REF" --pairs 1:1 --replace-bg 1 --duration 5 --res 768
bash "$SK/scripts/batch_push.sh" "$B" --tag B; wait_batch "$B"
SAGE_OK=$($SSH "grep -ci sage /root/comfy_render.log" || echo 0)
echo "sage mentions in render log: $SAGE_OK"
fi

# ---- C: shared-GPU lanes ------------------------------------------------------
if has C; then
guard
KEEP_SAGE=$( [ "${SAGE_KEEP:-auto}" = auto ] && echo 0 || echo "$SAGE_KEEP" )
$SSH "LANE_LAYOUT=shared SAGE=$KEEP_SAGE bash /root/pod/bootstrap.sh" | tail -6
C="${D}_perf-c-shared"
# 2K, not 4K: SeedVR2 4K measured ~40 min per 5 s clip (2026-09-28). Overlap is
# measured just as well at 2K and the phase fits the budget.
mk "$C" --sources "$SRC" --refs "$REF" --pairs 1:1,1:1 --replace-bg 1 --duration 5 --res 768 --upscale "${C_UPSCALE:-1440}"
python3 - "$DATA/batches/$C/manifest.csv" <<'EOF'
import csv,sys
p=sys.argv[1]; rows=list(csv.DictReader(open(p))); rows[1]["seed"]="777"   # distinct renders, no cache hit
w=csv.DictWriter(open(p,"w",newline=""),fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
EOF
python3 "$SK/scripts/show_manifest.py" "$DATA/batches/$C/manifest.csv"
bash "$SK/scripts/batch_push.sh" "$C" --tag C; wait_batch "$C"
fi

# ---- R: recover phase A's stranded upscales (last; cut first on budget) ----------
if has R; then
  guard
  echo "== R: recover phase A upscales on $A ($R_TARGETS)"
  $SSH "bash /root/pod/recover_upscales.sh /workspace/batches/$A $R_TARGETS"
  wait_batch "$A"
fi

# ---- report -----------------------------------------------------------------------
RAN=$(for b in "$A" "$B" "$C"; do [ -n "$b" ] && [ -d "$DATA/batches/$b" ] && echo "$b"; done)
for b in $RAN; do python3 "$SK/scripts/batch_sync.py" "$b" --no-drive; done
LAST=$(echo "$RAN" | tail -1)
scp -q -P "$PORT" -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 "root@$IP:/root/gpu.csv" "$DATA/batches/$LAST/gpu.csv" || true
python3 "$SK/scripts/perf_report.py" $RAN | tee "$DATA/batches/${D}_perf_report.md"
echo "PERF_SESSION_DONE after $(( ($(date +%s)-T0)/60 )) min"
