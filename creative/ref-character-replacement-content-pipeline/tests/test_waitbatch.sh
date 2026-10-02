#!/usr/bin/env bash
# E2E for perf_session's wait_batch against a fake pod (ssh stubbed to run
# locally): worker dies with a ticket pending -> restarted once -> second death
# -> tickets abandoned and wait returns, well before the budget guard.
set -u
SK="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); P=0; F=0
ok(){ P=$((P+1)); echo "  PASS $1"; }; bad(){ F=$((F+1)); echo "  FAIL $1"; }
mkdir -p $T/batches/bw/upscale_queue $T/root/pod
cp $SK/pod/batch_status.sh $T/root/pod/
# fake bootstrap --restart-upworker: counts restarts, starts a worker that dies in 2s
cat > $T/root/pod/bootstrap.sh <<EOF
echo restart >> $T/restarts
( exec -a upscale_worker.py sleep 2 ) &
echo "[bootstrap] upscale worker (re)started"
EOF
# extract wait_batch + guard from perf_session.sh and run them with ssh -> local bash
python3 - "$SK/scripts/perf_session.sh" > $T/wb.sh <<'EOF'
import re, sys
s = open(sys.argv[1]).read()
g = re.search(r"^guard\(\) \{.*?\n", s, re.M | re.S).group(0)
w = re.search(r"^WAIT_TICK=.*?^\}\n", s, re.M | re.S).group(0)
print(g + w)
EOF
cat > $T/run.sh <<EOF
set -u
T0=\$(date +%s); MAX_GPU_MIN=1; WAIT_TICK=1
SSH="env REFSWAP_BATCHES=$T/batches REFSWAP_RUNDIR=$T/root HB_MAX=120 bash -c"
. $T/wb.sh
# route the /root/pod and /workspace paths used inside wait_batch to the sandbox
wait_batch_local() { SSH_WRAP=1; wait_batch "\$@"; }
EOF
sed -i "s#/root/pod/#$T/root/pod/#g; s#/workspace/batches/#$T/batches/#g; s#/root/upworker.log#$T/up.log#g; s#/root/batch_#$T/batch_#g" $T/wb.sh
touch $T/up.log $T/batch_bw.log
echo '{}' > $T/batches/bw/upscale_queue/J02__2160.json.working    # orphaned ticket, no worker alive
s=$(date +%s)
( . $T/run.sh; wait_batch bw ) > $T/out.log 2>&1; rc=$?
el=$(( $(date +%s) - s ))
cat $T/out.log | sed 's/^/    /'
[ "$(wc -l < $T/restarts 2>/dev/null)" = 1 ] && ok "worker restarted exactly once" || bad "restarts=$(cat $T/restarts 2>/dev/null | wc -l)"
grep -q "abandoning" $T/out.log && ok "second death -> abandon" || bad "no abandon"
ls $T/batches/bw/upscale_queue/*.abandoned >/dev/null 2>&1 && ok "ticket marked .abandoned" || bad "ticket not abandoned: $(ls $T/batches/bw/upscale_queue)"
[ $el -lt 55 ] && ok "returned in ${el}s (before the 60s budget guard)" || bad "took ${el}s"
! grep -q BUDGET $T/out.log && ok "budget guard not hit" || bad "hit budget guard"
echo "RESULT: $P passed, $F failed"; rm -rf $T; [ $F = 0 ]
