#!/usr/bin/env bash
# Smoke test for motion-remake: synthetic reference -> analyse -> stub -> real shots -> compare -> full -> encode -> split
# -> stacked -> QA -> audio analyse + fit -> mix. Usage: bash smoke_test.sh [workdir]
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
W=${1:-$(mktemp -d)}
PY=${PYTHON:-/usr/bin/python3}
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
# 1) synthetic REF (4 s, 24 fps, 960x540): orange OLDCO card slides in (0-1 s) then holds, hard cut at 2 s to a dark title.
#    (overlay x is evaluated per frame; drawbox x is NOT, it froze the card in an earlier version of this test)
mkdir -p "$W"; cd "$W"
ffmpeg -y -loglevel error -f lavfi -i "color=c=white:s=960x540:d=2:r=24" -f lavfi -i "color=c=0xF26B1D:s=400x200:d=2:r=24" \
  -f lavfi -i "color=c=0x111827:s=960x540:d=2:r=24" \
  -filter_complex "[1:v]drawtext=fontfile=$FONT:text='OLDCO':fontcolor=white:fontsize=56:x=(w-text_w)/2:y=(h-text_h)/2[card];\
[0:v][card]overlay=x='if(lt(t,1),-400+t*580,180)':y=170:eval=frame[a];\
[2:v]drawtext=fontfile=$FONT:text='Ship faster':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2[b];[a][b]concat=n=2:v=1[v]" \
  -map "[v]" -c:v libx264 -pix_fmt yuv420p ref_src.mp4
ffmpeg -y -loglevel error -f lavfi -i "sine=f=1000:d=0.03,apad=pad_dur=0.47" -t 0.5 click.wav
ffmpeg -y -loglevel error -stream_loop 7 -i click.wav -t 4 -ac 2 -ar 48000 clicks.wav
ffmpeg -y -loglevel error -i ref_src.mp4 -i clicks.wav -map 0:v -map 1:a -c:v copy -c:a aac -shortest reference.mp4
# 2) scaffold + configure
bash "$SK/scripts/new_remake.sh" "$W/rm" "$W/reference.mp4"
cd "$W/rm"
$PY - <<'EOF'
import json; p = json.load(open("project.json"))
p.update(fps=24, w=960, h=540, ref_brand="OLDCO", brand="NEWCO", groups={"G1": [0, 48], "G2": [48, 96]})
p["tokens"]["a1"] = "#38bdf8"
json.dump(p, open("project.json", "w"), indent=1)
EOF
$PY remake_analyze.py --fps 24 --width 960
$PY remake_stub.py
node remake_render.mjs stills out/stub 10 60
# 3) a build agent's work: G1 measured from REF (card x = -400 + 580*t until 1 s), brand swapped; G2 the title shot
cat > shots/G1.js <<'EOF'
(function () {
  const C = CORE;
  SHOT({ id: 'G1_card', f0: 0, f1: 48, render: (lf, F) => {
    const x = F < 24 ? -400 + 580 * F / 24 : 180;                 // measured from ref/full (linear slide, then hold)
    // REF orange is #F26B1D; we write it on purpose here to prove the palette filter re-hues leftovers to the new accent
    return `<div style="position:absolute;inset:0;background:#ffffff"></div>
      <div style="position:absolute;left:${x}px;top:170px;width:400px;height:200px;background:#F26B1D;display:flex;align-items:center;justify-content:center;color:#fff;font:700 56px DejaVu Sans, sans-serif">NEWCO</div>`;
  }});
})();
EOF
cat > shots/G2.js <<'EOF'
(function () {
  const C = CORE;
  SHOT({ id: 'G2_title', f0: 48, f1: 96, render: (lf, F) =>
    `<div style="position:absolute;inset:0;background:#111827;display:flex;align-items:center;justify-content:center;color:#fff;font:700 64px DejaVu Sans, sans-serif">Ship faster</div>` });
})();
EOF
node remake_render.mjs compare out/G1 0 12 24 47
# frame-lock check: the card's bounding box (non-white, saturated pixels) must match REF within 2% of frame width
$PY - <<'EOF'
import numpy as np
from PIL import Image
def box(p):
    a = np.asarray(Image.open(p).convert("RGB").resize((960, 540)), dtype=np.int16)
    sat = (a.max(2) - a.min(2)) > 60
    xs = np.where(sat.any(0))[0]
    return (int(xs[0]), int(xs[-1])) if len(xs) else None
worst = 0
for F in (0, 6, 12, 18, 24, 36, 47):
    r, o = box(f"ref/full/f{F:04d}.jpg"), box(f"out/G1/o_f{F:04d}.png") if F in (0, 12, 24, 47) else None
    if o is None and F not in (0, 12, 24, 47):
        continue
    if r is None and o is None:
        print(f"F{F}: both off-screen"); continue
    if (r is None) != (o is None):
        raise SystemExit(f"F{F}: visibility differs REF {r} OURS {o}")
    err = max(abs(r[0] - o[0]), abs(r[1] - o[1])) / 960
    worst = max(worst, err)
    print(f"F{F}: REF x {r}  OURS x {o}  err {err:.2%}")
if worst > 0.02:
    raise SystemExit(f"frame-lock FAILED: worst error {worst:.2%}")
print(f"frame-lock OK: worst card-edge error {worst:.2%} of frame width")
EOF
node remake_render.mjs full out/full 0 96
$PY remake_sync.py encode
$PY remake_audio.py analyse
$PY remake_audio.py fit "$W/clicks.wav" --track-drop 0.0 --ref-drop 0.0 --track-bpm 120 --ref-bpm 120
$PY mix.py
cp out/mix.wav out/mix.wav.bak && $PY remake_sync.py encode
for f in out/remake_silent.mp4 out/remake.mp4; do echo "duration $f $(ffprobe -v error -show_entries format=duration -of csv=p=0 $f)"; done
VD=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/remake.mp4)
$PY -c "import sys; d=float('$VD'); sys.exit(0 if abs(d-4.0)<0.06 else 'remake.mp4 truncated: %.3fs' % d)"
$PY remake_sync.py split
$PY remake_sync.py stacked
$PY remake_qa.py
$PY qc.py out/remake_silent.mp4 --cuts 2.0 || true
ffprobe -v error -show_entries stream=codec_name,width,height,sample_aspect_ratio,r_frame_rate -of compact out/split_screen.mp4
echo "REMAKE SMOKE OK: $W/rm"
