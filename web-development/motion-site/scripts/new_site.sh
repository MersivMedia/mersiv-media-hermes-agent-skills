#!/usr/bin/env bash
# new_site.sh — scaffold a motion site: page template + vendored gsap/ScrollTrigger/lenis + plan.json.
# Usage: bash new_site.sh <dir>
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
RT=${MOTION_SITE_RUNTIME:-$HOME/.hermes/data/motion-site/runtime}
DIR=${1:?usage: new_site.sh <dir>}
[ -e "$DIR/site.js" ] && { echo "$DIR already scaffolded; not overwriting"; exit 1; }
if [ ! -f "$RT/node_modules/gsap/dist/gsap.min.js" ] || [ ! -f "$RT/node_modules/lenis/dist/lenis.min.js" ]; then
  mkdir -p "$RT" && (cd "$RT" && { [ -f package.json ] || npm init -y >/dev/null; } && npm i -q gsap@3 lenis@1 playwright-core >/dev/null)
fi
mkdir -p "$DIR"/{vendor,assets/stills,assets/clips,assets/frames,assets/posters,brand,qa}
cp "$SK"/templates/site/{index.html,site.js,motion-site.css,site.json} "$DIR/"
cp "$SK/templates/plan.json" "$DIR/plan.json"
cp "$RT/node_modules/gsap/dist/gsap.min.js" "$RT/node_modules/gsap/dist/ScrollTrigger.min.js" "$RT/node_modules/lenis/dist/lenis.min.js" "$DIR/vendor/"
printf 'qa/\nassets/ledger.json\n.env\n' > "$DIR/.gitignore"
echo "{}" > "$DIR/assets/frames.json"
echo "scaffolded $DIR (gsap $(node -p "require('$RT/node_modules/gsap/package.json').version"), lenis $(grep -m1 '"version"' "$RT/node_modules/lenis/package.json" | grep -oE '[0-9.]+'))"
echo "next: brief -> edit plan.json + site.json -> python3 scripts/gen.py plan.json --dry-run"
