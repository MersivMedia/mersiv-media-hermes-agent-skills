#!/usr/bin/env bash
# Run every offline test suite for the refswap pipeline. No pod, no spend.
#   tests/run_all.sh
cd "$(dirname "$0")/.." || exit 1
fail=0
for f in scripts/*.sh pod/*.sh tests/*.sh; do bash -n "$f" || { echo "SYNTAX FAIL $f"; fail=1; }; done
for f in scripts/*.py pod/*.py tests/*.py; do python3 -m py_compile "$f" || { echo "PY FAIL $f"; fail=1; }; done
run() {   # name cmd...
  local name=$1; shift
  "$@" > "/tmp/refswap_$name.log" 2>&1; local rc=$?
  printf "%-14s rc=%s  %s\n" "$name" "$rc" "$(grep -E 'RESULT|SKIP' "/tmp/refswap_$name.log" | tail -1)"
  [ $rc = 0 ] || fail=1
}
run offline       bash tests/test_offline.sh
run transfer      bash tests/test_transfer.sh
run transfer_root bash tests/test_transfer_root.sh
run failpath      timeout 200 bash tests/test_failpath.sh
run selfstop      timeout 60 python3 tests/test_selfstop.py
echo "ALL: $([ $fail = 0 ] && echo PASS || echo FAIL)"
exit $fail
