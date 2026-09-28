#!/usr/bin/env bash
# Local check of the tar-over-ssh transfer forms used by refswap_up.sh (push),
# batch_push.sh (push batch) and batch_sync.py (pull). "ssh" is replaced by
# `sh -c` so it runs without a pod. No network, no spend.
set -u
T=$(mktemp -d); PASS=0; FAIL=0
ok()  { echo "  PASS $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }
SSH="sh -c"

# 1) refswap_up push: pod/ tree + secrets.env, secrets must land 600
mkdir -p "$T/src/pod/comfy_node/h3" "$T/remote"
echo a > "$T/src/pod/x.py"; echo b > "$T/src/pod/comfy_node/h3/y.py"
( umask 077; echo "K=1" > "$T/src/secrets.env" )
tar -C "$T/src" -czf - pod secrets.env | $SSH "umask 077; mkdir -p $T/remote && tar -C $T/remote -xzf -"
[ -f "$T/remote/pod/comfy_node/h3/y.py" ] && ok "push: nested tree" || bad "push: nested tree"
[ "$(stat -c %a "$T/remote/secrets.env")" = 600 ] && ok "push: secrets 600" || bad "push: secrets $(stat -c %a "$T/remote/secrets.env")"

# 2) batch_push: inputs + manifest only, results dirs excluded
L="$T/batch_local"; mkdir -p "$L/sources" "$L/refs" "$L/renders"
echo m > "$L/manifest.csv"; echo s > "$L/sources/src_a.mp4"; echo r > "$L/refs/ref_a.png"; echo x > "$L/renders/old.mp4"
tar -C "$L" -czf - --exclude renders --exclude upscaled --exclude compare --exclude sidecars \
  --exclude upscale_queue --exclude '*.csv.synced' . | $SSH "mkdir -p $T/rb && tar -C $T/rb -xzf -"
[ -f "$T/rb/manifest.csv" ] && [ -f "$T/rb/sources/src_a.mp4" ] && [ -f "$T/rb/refs/ref_a.png" ] && ok "batch push: inputs" || bad "batch push: inputs"
[ ! -e "$T/rb/renders" ] && ok "batch push: renders excluded" || bad "batch push: renders excluded"

# 3) batch_sync pull, the exact Python code path, with upscaled/ missing
R="$T/rb"; mkdir -p "$R/renders" "$R/sidecars"; echo v > "$R/renders/J01.mp4"; echo j > "$R/sidecars/J01.json"; echo job > "$R/results.csv"
mkdir -p "$T/pulled"
python3 - "$R" "$T/pulled" <<'EOF'
import subprocess, sys
src, dst = sys.argv[1], sys.argv[2]
remote = (f"cd {src} && "
          "tar -czf - $(ls -d renders upscaled sidecars results.csv upscale_results.csv 2>/dev/null)")
p1 = subprocess.Popen(["sh", "-c", remote], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
r = subprocess.run(["tar", "-C", dst, "-xzf", "-"], stdin=p1.stdout, capture_output=True, text=True)
p1.stdout.close()
sys.exit(0 if p1.wait() == 0 and r.returncode == 0 else 1)
EOF
[ $? = 0 ] && ok "pull: exit 0 with upscaled/ missing" || bad "pull: exit"
[ -f "$T/pulled/renders/J01.mp4" ] && [ -f "$T/pulled/sidecars/J01.json" ] && [ -f "$T/pulled/results.csv" ] && ok "pull: files" || bad "pull: files"

rm -rf "$T"
echo "RESULT: $PASS passed, $FAIL failed"
[ $FAIL = 0 ]
