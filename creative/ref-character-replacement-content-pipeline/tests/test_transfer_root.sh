#!/usr/bin/env bash
# Reproduces the 2026-09-28 pod failure locally: tar extracting AS ROOT onto a
# filesystem that refuses chown (RunPod's MooseFS network volume; here a vfat
# loop image, which returns EPERM for chown the same way). Needs passwordless sudo.
#   tests/test_transfer_root.sh
# Asserts the OLD form fails (so the test really exercises the failure) and the
# NEW form (--no-same-owner) succeeds.
set -u
command -v mkfs.vfat >/dev/null || { echo "SKIP: no mkfs.vfat"; exit 0; }
sudo -n true 2>/dev/null || { echo "SKIP: needs passwordless sudo"; exit 0; }
T=$(mktemp -d); IMG=$T/vol.img; MNT=$T/mnt; PASS=0; FAIL=0
ok()  { echo "  PASS $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }
cleanup() { sudo -n umount "$MNT" 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT

truncate -s 16M "$IMG"; mkfs.vfat "$IMG" >/dev/null
mkdir -p "$MNT"; sudo -n mount -o loop "$IMG" "$MNT" || { echo "SKIP: cannot loop-mount (NOT a pass)"; exit 3; }

# payload shaped like a batch push, owned by this (non-root) user, uid != 0
mkdir -p "$T/src/sources" "$T/src/refs"
echo m > "$T/src/manifest.csv"; echo s > "$T/src/sources/src_a.mp4"; echo r > "$T/src/refs/ref_a.png"
tar -C "$T/src" -czf "$T/p.tgz" .

# OLD form (what batch_push.sh ran on the pod)
sudo -n mkdir -p "$MNT/old"
if sudo -n tar -C "$MNT/old" -xzf "$T/p.tgz" 2>"$T/old.err"; then
  bad "old form should fail as root on a chown-refusing fs (test not reproducing)"
else
  grep -q "Cannot change ownership" "$T/old.err" && ok "old form reproduces 'Cannot change ownership'" \
    || bad "old form failed differently: $(head -c 200 "$T/old.err")"
fi

# NEW form: the exact extract command the scripts now send to the pod
EXTRACT=$(grep -o 'tar --no-same-owner[^"]*-xzf -' "$(dirname "$0")/../scripts/batch_push.sh" | head -1)
[ -n "$EXTRACT" ] && ok "batch_push.sh uses --no-same-owner" || bad "batch_push.sh extract lacks --no-same-owner"
sudo -n mkdir -p "$MNT/new"
if sudo -n sh -c "cd $MNT/new && tar --no-same-owner -xzf -" < "$T/p.tgz" 2>"$T/new.err"; then
  ok "new form extracts as root"
else
  bad "new form failed: $(head -c 200 "$T/new.err")"
fi
[ -f "$MNT/new/sources/src_a.mp4" ] && [ -f "$MNT/new/manifest.csv" ] && ok "new form: files present" || bad "new form: files missing"

for f in scripts/refswap_up.sh scripts/batch_push.sh; do
  n=$(grep -c 'tar .*-xzf -' "$(dirname "$0")/../$f"); m=$(grep -c 'tar --no-same-owner.*-xzf -' "$(dirname "$0")/../$f")
  [ "$n" = "$m" ] && ok "$f: every remote extract has --no-same-owner ($m)" || bad "$f: $m of $n extracts have --no-same-owner"
done

echo "RESULT: $PASS passed, $FAIL failed"
[ $FAIL = 0 ]
