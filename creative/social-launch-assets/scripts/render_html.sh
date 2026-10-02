#!/usr/bin/env bash
# Render an HTML poster to PNG at exact size, 2x density.
# Usage: render_html.sh in.html out.png [width=1080] [height=1350] [scale=2]
# Uses chrome-headless-shell: the full Chrome "--headless=new" reserves ~87px
# of the window for browser chrome, so the bottom of a poster gets cut off.
set -euo pipefail
in="$(realpath "$1")"; out="$(realpath -m "$2")"
w="${3:-1080}"; h="${4:-1350}"; s="${5:-2}"
shell="$(ls -d "$HOME"/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell 2>/dev/null | sort -V | tail -1)"
if [ -z "$shell" ]; then
  echo "chrome-headless-shell not found; install with: npx playwright install chromium-headless-shell" >&2
  exit 1
fi
"$shell" --no-sandbox --hide-scrollbars --force-device-scale-factor="$s" \
  --window-size="$w,$h" --virtual-time-budget=3000 \
  --screenshot="$out" "file://$in" 2>/dev/null
python3 - "$out" "$w" "$h" "$s" <<'EOF'
import struct, sys
p, w, h, s = sys.argv[1], *map(int, sys.argv[2:])
W, H = struct.unpack(">II", open(p, "rb").read(24)[16:24])
ok = (W, H) == (w * s, h * s)
print(f"{p}: {W}x{H} {'OK' if ok else 'UNEXPECTED SIZE'}")
sys.exit(0 if ok else 2)
EOF
