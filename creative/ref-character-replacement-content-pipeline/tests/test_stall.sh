#!/usr/bin/env bash
# Placement stall (2026-09-29): a pod is placed but never gets a container/IP.
#  part 1: refswap_up -> wait fails -> terminate -> verified gone -> rc 3, state cleaned
#          (and rc 1, pod kept "live", when terminate can't be confirmed)
#  part 2: poll_and_run treats rc 3 as "keep polling", gives up after MAX_STALLS,
#          never marks the pod live, and a later good placement still runs.
set -u
SK="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); P=0; F=0
ok(){ P=$((P+1)); echo "  PASS $1"; }; bad(){ F=$((F+1)); echo "  FAIL $1"; }
mkdir -p $T/data $T/bin $T/hermes-agent; : > $T/data/comfy_login.env; : > $T/hermes-agent/.env

# ---- part 1
cat > $T/bin/pod.py <<EOF
import json, os, sys
a = sys.argv[1:]
open("$T/calls", "a").write(" ".join(a) + "\\n")
gone = os.path.exists("$T/terminated")
if a[0] == "create":
    print(json.dumps({"id": "stuck1"}))
elif a[0] == "wait":
    sys.exit("timed out waiting for pod")
elif a[0] == "terminate":
    if os.environ.get("TERM_FAILS") != "1": open("$T/terminated", "w").write("x")
    print("terminated")
elif a[0] == "info":
    print(json.dumps({} if gone else {"id": a[1], "desiredStatus": "RUNNING", "gpuCount": 1, "machine": {}}))
EOF
sed -e "s#^DATA=.*#DATA=$T/data#" -e "s#^POD_PY=.*#POD_PY=$T/bin/pod.py#" \
    -e "s#~/.hermes/.env#$T/hermes-agent/.env#" $SK/scripts/refswap_up.sh > $T/up.sh
rm -f $T/data/pod_id; : > $T/calls
WAIT_S=1 timeout 30 bash $T/up.sh > $T/up.log 2>&1; rc=$?
[ $rc = 3 ] && ok "stall -> rc 3" || bad "rc=$rc: $(tail -3 $T/up.log)"
grep -q "^terminate stuck1" $T/calls && ok "stalled pod terminated (not just stopped)" || bad "calls: $(cat $T/calls)"
[ ! -e $T/data/pod_created ] && [ ! -e $T/data/pod_id ] && ok "pod_created + pod_id cleared (next attempt won't restart the stuck pod)" || bad "state left: $(ls $T/data)"
rm -f $T/terminated $T/data/pod_id; : > $T/calls
WAIT_S=1 TERM_FAILS=1 timeout 30 bash $T/up.sh > $T/up.log 2>&1; rc=$?
[ $rc = 1 ] && [ -e $T/data/pod_created ] && ok "unconfirmed terminate -> rc 1 + still counted live (poller will stop it)" || bad "rc=$rc created=$(ls $T/data)"

# ---- part 2
cat > $T/bin/up_stub.sh <<EOF
n=\$(( \$(cat $T/n 2>/dev/null || echo 0) + 1 )); echo \$n > $T/n
[ \$n -le \${STUB_STALLS:-99} ] && { echo "== pod p\$n never started"; exit 3; }
touch $T/data/pod_created; echo "== pod good $\GPU"; exit 0
EOF
cat > $T/bin/perf_stub.sh <<EOF
echo perf-ran > $T/perf_ran; exit 0
EOF
cat > $T/bin/pod2.py <<EOF
import json, sys
a = sys.argv[1:]; open("$T/calls2", "a").write(" ".join(a) + "\\n")
if a[0] == "info": print(json.dumps({"id": "good", "desiredStatus": "EXITED"}))
EOF
echo good > $T/data/pod_id
run_poll() {
  rm -f $T/n $T/perf_ran; : > $T/calls2
  STUB_STALLS=$1 MAX_STALLS=$2 REFSWAP_TEST=1 REFSWAP_DATA=$T/data REFSWAP_UP=$T/bin/up_stub.sh \
    REFSWAP_PERF=$T/bin/perf_stub.sh REFSWAP_SYNC=/bin/true REFSWAP_POD_PY=$T/bin/pod2.py POLL_S=0 \
    timeout 30 bash $SK/scripts/poll_and_run.sh a b > /dev/null 2>&1
}
run_poll 99 3; rc=$?
[ $rc = 1 ] && [ "$(cat $T/n)" = 3 ] && ok "gives up after MAX_STALLS=3 attempts" || bad "rc=$rc attempts=$(cat $T/n)"
grep -q "GAVE UP after 3 placement stalls" $T/data/poll.status && ok "status says why" || bad "status: $(cat $T/data/poll.status)"
! grep -q "^stop " $T/calls2 && ok "no stop call for terminated pods (nothing live)" || bad "stop called: $(cat $T/calls2)"
run_poll 2 3; rc=$?
[ -e $T/perf_ran ] && [ "$(cat $T/n)" = 3 ] && ok "2 stalls then a good host -> session runs" || bad "rc=$rc attempts=$(cat $T/n) perf=$(ls $T/perf_ran 2>&1)"
grep -q "^stop good" $T/calls2 && ok "...and that pod is stopped at the end" || bad "calls2: $(cat $T/calls2)"
echo "RESULT: $P passed, $F failed"; rm -rf $T; [ $F = 0 ]
