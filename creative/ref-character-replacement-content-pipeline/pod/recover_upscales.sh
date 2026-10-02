#!/usr/bin/env bash
# Pod-side: re-ticket upscales a batch is missing, from renders already on the
# volume (no re-render). Also adopts a finished upscale that ComfyUI saved but
# the crashed worker never copied (the 2026-09-28 4K), instead of redoing it.
#   bash /root/pod/recover_upscales.sh /workspace/batches/<batch> 1440 2160
set -u
B=$1; shift
OUT=${REFSWAP_COMFY:-/workspace/ComfyUI}/output/refswap_up/$(basename "$B")
mkdir -p "$B/upscale_queue" "$B/upscaled"
declare -A LABEL=([1080]=1080p [1440]=2k [2160]=4k)
for r in "$B"/renders/*.mp4; do
  [ -e "$r" ] || continue
  stem=$(basename "$r" .mp4)
  res=$(echo "$stem" | grep -oE '_[0-9]+p$' | tr -dc 0-9)
  # only rows that asked for upscales: read the manifest's upscale column for this job
  job=${stem%%_*}
  want=$(python3 -c "
import csv,sys
for row in csv.DictReader(open('$B/manifest.csv')):
    if row['job']=='$job': print(row.get('upscale') or '')" )
  for th in "$@"; do
    adopt_only=0; case "$th" in @*) adopt_only=1; th=${th#@};; esac
    case ";$want;" in *";$th;"*) ;; *) continue;; esac
    lab=${LABEL[$th]:-${th}p}; name=${stem}_${lab}; dst=$B/upscaled/$name.mp4
    [ -s "$dst" ] && { echo "have   $name"; continue; }
    done_file=$(ls -t "$OUT/${name}"_*.mp4 2>/dev/null | head -1)
    if [ -n "$done_file" ]; then
      cp "$done_file" "$dst"; echo "adopted $name  <- $(basename "$done_file") (saved by ComfyUI, never copied)"
      continue
    fi
    [ $adopt_only = 1 ] && { echo "skip   $name (adopt-only; no saved file to adopt)"; continue; }
    python3 - "$B" "$stem" "$r" "$res" "$th" "$lab" "$dst" <<'EOF'
import json, sys, time
B, stem, src, res, th, lab, dst = sys.argv[1:]
t = {"batch": B, "stem": stem, "src": src, "src_res": int(res), "target_h": int(th),
     "label": lab, "out": dst, "tag": "R", "created": time.time()}
open(f"{B}/upscale_queue/{stem}__{th}.json", "w").write(json.dumps(t))
print(f"ticket {stem} -> {th}p")
EOF
  done
done
