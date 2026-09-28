#!/usr/bin/env bash
# Failure-path test for poll_and_run.sh (no pod, no spend). Stubs refswap_up,
# perf_session, batch_sync and pod.py; asserts the pod is stopped on EVERY exit
# path, and quickly (the 2026-09-28 incident left an H100 idle ~75 min).
set -u
SK="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok()  { echo "  PASS $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }

setup() {   # $1 = up rc, $2 = perf rc, $3 = perf sleep s, $4 = sync sleep s
  T=$(mktemp -d); mkdir -p "$T/data/batches"
  cat > "$T/up.sh" <<EOF
#!/usr/bin/env bash
echo "== pod stubpod  x  \\\$1.00/hr  ssh 1.2.3.4:22"
[ "$1" != nopod ] && { echo stubpod > "$T/data/pod_id"; touch "$T/data/pod_created"; }
exit ${1/nopod/2}
EOF
  cat > "$T/perf.sh" <<EOF
#!/usr/bin/env bash
mkdir -p "$T/data/batches/\${PERF_DATE}_perf-a-serial"
sleep $3; exit $2
EOF
  cat > "$T/sync.py" <<EOF
import time, sys; time.sleep($4); print("synced", sys.argv[1])
EOF
  cat > "$T/pod.py" <<EOF
import sys, json
cmd = sys.argv[1]
open("$T/calls", "a").write(" ".join(sys.argv[1:]) + "\n")
if cmd == "info": print(json.dumps({"desiredStatus": "EXITED"}))
EOF
  export REFSWAP_TEST=1 REFSWAP_DATA="$T/data" REFSWAP_UP="$T/up.sh" REFSWAP_PERF="$T/perf.sh" \
         REFSWAP_SYNC="$T/sync.py" REFSWAP_POD_PY="$T/pod.py" POLL_S=1 MAX_HOURS=1
}
stops() { grep -c "^stop stubpod" "$T/calls" 2>/dev/null || echo 0; }

echo "1) session FAILS (the incident): pod stopped right after, not after a watcher"
setup 0 2 1 0; s=$(date +%s)
bash "$SK/scripts/poll_and_run.sh" src ref >/dev/null 2>&1; rc=$?; el=$(( $(date +%s)-s ))
[ "$(stops)" = 1 ] && ok "stopped exactly once" || bad "stop calls=$(stops)"
[ $el -lt 20 ] && ok "stopped within ${el}s" || bad "took ${el}s"
[ $rc != 0 ] && ok "nonzero exit reported" || bad "exit 0 on failure"
grep -q "desiredStatus=EXITED" "$T/data/poll.log" && ok "stop verified via info" || bad "no stop verification"
grep -q "synced" "$T/data/poll.log" && ok "sync attempted before stop" || bad "no sync"

echo "2) sync HANGS: bounded, pod still stopped"
setup 0 1 0 30; export SYNC_TIMEOUT=3; s=$(date +%s)
bash "$SK/scripts/poll_and_run.sh" src ref >/dev/null 2>&1; el=$(( $(date +%s)-s ))
[ "$(stops)" = 1 ] && ok "stopped despite hung sync" || bad "stop calls=$(stops)"
[ $el -lt 15 ] && ok "sync bounded (${el}s)" || bad "sync not bounded (${el}s)"
unset SYNC_TIMEOUT

echo "3) bring-up FAILS after pod placed (the rsync incident path)"
setup 12 0 0 0
bash "$SK/scripts/poll_and_run.sh" src ref >/dev/null 2>&1
[ "$(stops)" = 1 ] && ok "stopped after failed bring-up" || bad "stop calls=$(stops)"

echo "4) SIGTERM mid-session: trap stops the pod"
setup 0 0 30 0
bash "$SK/scripts/poll_and_run.sh" src ref >/dev/null 2>&1 & P=$!
sleep 3; kill -TERM $P; wait $P 2>/dev/null
[ "$(stops)" -ge 1 ] && ok "stopped on SIGTERM" || bad "not stopped on SIGTERM"

echo "5) session SUCCEEDS: stopped once, exit 0"
setup 0 0 0 0
bash "$SK/scripts/poll_and_run.sh" src ref >/dev/null 2>&1; rc=$?
[ "$(stops)" = 1 ] && ok "stopped exactly once" || bad "stop calls=$(stops)"
[ $rc = 0 ] && ok "exit 0" || bad "exit $rc"

echo "6) no GPU ever: never calls stop (nothing to stop)"
setup nopod 0 0 0; export MAX_HOURS=0
bash "$SK/scripts/poll_and_run.sh" src ref >/dev/null 2>&1
[ "$(stops)" = 0 ] && ok "no stop without a pod" || bad "stop called with no pod"

echo "RESULT: $PASS passed, $FAIL failed"
[ $FAIL = 0 ]
