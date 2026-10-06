#!/usr/bin/env bash
# smoke_test.sh — free end-to-end test (no Replicate spend): scaffold on the pinned engine -> page from our template
# using the engine's sample model -> gen3d.py --dry-run -> optimize.sh on a copy -> vite build -> headless screenshots
# at 3 scroll stops (SwiftShader software WebGL on this GPU-less box: correct pixels, low fps).
# Usage: bash smoke_test.sh [workdir]
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
W=${1:-$(mktemp -d)}
bash "$SK/scripts/new_diorama.sh" "$W/d" demo
cd "$W/d"
mkdir -p assets/raw public/models/demo
cp public/models/sucre/macaron-lo.glb assets/raw/hero.glb            # stand-in for a generated GLB
python3 "$SK/scripts/gen3d.py" assets/jobs-demo.json --dry-run | tail -3
bash "$SK/scripts/optimize.sh" demo --tex 1024 --q 80
ls -la public/models/demo/
npx vite build --logLevel error > build.log 2>&1 && echo "vite build OK ($(du -sh dist | cut -f1))" || { tail -20 build.log; exit 1; }
node "$SK/scripts/shoot.mjs" dist "examples/demo/" qa --stops 0,0.4,0.85
echo "DIORAMA SMOKE DONE: $W/d"
