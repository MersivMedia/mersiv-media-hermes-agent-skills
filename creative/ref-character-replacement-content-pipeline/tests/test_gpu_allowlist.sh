#!/usr/bin/env bash
# "PRO 6000 only": with ALLOW_GPUS="" the poller must never restart the stopped
# H100 pod and never request anything but the two RTX PRO 6000 ids.
#  part 1: poll_and_run.sh -> the exact args it passes to refswap_up (stub UP)
#  part 2: real refswap_up.sh allow-list logic against a stub pod.py
set -u
SK="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); P=0; F=0
ok(){ P=$((P+1)); echo "  PASS $1"; }; bad(){ F=$((F+1)); echo "  FAIL $1"; }
mkdir -p $T/data $T/bin $T/hermes-agent
echo "ct39rg2rkwto8r" > $T/data/pod_id; : > $T/data/comfy_login.env; : > $T/hermes-agent/.env

# ---- part 1: poller args
cat > $T/bin/up_stub.sh <<EOF
printf '%s\n' "\$@" > $T/up_args; exit 1      # rc 1 + no pod_created = clean bring-up failure
EOF
poll_args() {
  rm -f $T/up_args
  env ${1+ALLOW_GPUS="$1"} REFSWAP_TEST=1 REFSWAP_DATA=$T/data REFSWAP_UP=$T/bin/up_stub.sh \
    REFSWAP_POD_PY=/bin/true POLL_S=0 timeout 20 bash $SK/scripts/poll_and_run.sh a b >/dev/null 2>&1
}
poll_args ""
! grep -q -- "--allow-gpu" $T/up_args && ok "poller, ALLOW_GPUS=\"\": no --allow-gpu passed" || bad "args: $(tr '\n' ' ' < $T/up_args)"
env -u ALLOW_GPUS true; unset ALLOW_GPUS
rm -f $T/up_args
REFSWAP_TEST=1 REFSWAP_DATA=$T/data REFSWAP_UP=$T/bin/up_stub.sh REFSWAP_POD_PY=/bin/true POLL_S=0 \
  timeout 20 bash $SK/scripts/poll_and_run.sh a b >/dev/null 2>&1
[ "$(grep -c -- '--allow-gpu' $T/up_args)" = 2 ] && ok "poller, ALLOW_GPUS unset: default H100 fallbacks kept" || bad "default args: $(tr '\n' ' ' < $T/up_args)"

# ---- part 2: refswap_up allow-list vs the stopped H100 pod
cat > $T/bin/pod.py <<EOF
import json, sys
a = sys.argv[1:]
open("$T/calls", "a").write(" ".join(a) + "\\n")
if a[0] == "info":
    print(json.dumps({"id": a[1], "gpuCount": 1, "desiredStatus": "EXITED",
                      "machine": {"gpuTypeId": "NVIDIA H100 80GB HBM3"}}))
elif a[0] == "create":
    sys.exit("no instances currently available")
elif a[0] == "wait":
    sys.exit("stub: stop here")                 # don't go on to ssh
EOF
sed -e "s#^DATA=.*#DATA=$T/data#" -e "s#^POD_PY=.*#POD_PY=$T/bin/pod.py#" \
    -e "s#~/.hermes/.env#$T/hermes-agent/.env#" $SK/scripts/refswap_up.sh > $T/up.sh
: > $T/calls; timeout 30 bash $T/up.sh --layout serial --sage 0 > $T/up.log 2>&1
! grep -q "^start " $T/calls && ok "PRO-only: stopped H100 pod NOT restarted" || bad "restarted H100: $(grep start $T/calls)"
[ "$(grep -c '^create ' $T/calls)" = 2 ] && ! grep '^create ' $T/calls | grep -q H100 && ok "PRO-only: only the 2 PRO 6000 ids requested" || bad "creates: $(grep create $T/calls)"
grep -q "NO GPU AVAILABLE" $T/up.log && ok "PRO-only: clean 'no GPU' exit" || bad "up.log: $(tail -2 $T/up.log)"
: > $T/calls; timeout 30 bash $T/up.sh --layout serial --sage 0 --allow-gpu "NVIDIA H100 80GB HBM3" > $T/up.log 2>&1
grep -q "^start ct39rg2rkwto8r" $T/calls && ok "H100 allowed: existing H100 pod IS restarted" || bad "calls: $(cat $T/calls)"
echo "RESULT: $P passed, $F failed"; rm -rf $T; [ $F = 0 ]
