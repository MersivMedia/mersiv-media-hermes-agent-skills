#!/usr/bin/env bash
# Offline test: consent gate, plan/cost, QC gates (incl. a planted bad plate),
# layout, pack. No API calls, no spend.
set -u
SK="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); export RS_DATA=$T
PASS=0; FAIL=0
ok()  { echo "  PASS $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }
B="python3 $SK/scripts/build_sheet.py"

$B init testchar --name "Mara Voss" >/dev/null
S=$T/testchar/spec.yaml
[ -f "$S" ] && ok "init writes spec" || bad "init"

echo "== consent gate"
sed -i 's/^subject_type: fictional/subject_type: real_person/; s/^consent: n\/a/consent: public_figure/' "$S"
$B plan "$S" > $T/o 2>&1; grep -q "REFUSED" $T/o && ok "real person without consent refused" || bad "consent gate: $(head -c 200 $T/o)"
sed -i 's/^consent: public_figure/consent: self/' "$S"
$B plan "$S" > $T/o 2>&1; grep -q "must start from the person's own photo" $T/o && ok "real person needs own photo" || bad "photo gate"
sed -i 's/^subject_type: real_person/subject_type: fictional/; s/^consent: self/consent: n\/a/' "$S"

echo "== plan"
$B plan "$S" > $T/o 2>&1
grep -q "plates=31" $T/o && ok "31 plates planned (anchor 1 + turn 4 + face 3 + expr 8 + pose 6 + costume 4 + material 5)" || bad "plate count: $(grep plates= $T/o)"
grep -q 'estimate: 31 × \$0.040 = \$1.24' $T/o && ok "cost estimate \$1.24 on seedream" || bad "estimate: $(grep estimate $T/o)"
$B run "$S" > $T/o 2>&1; grep -q "dry run only" $T/o && ok "run without --yes spends nothing" || bad "run gate"
python3 - "$T/testchar/prompts.json" <<'EOF' && ok "every non-anchor plate is i2i from the anchor; no grade words" || bad "prompt rules"
import json, sys
P = json.load(open(sys.argv[1]))
assert P[0]["key"] == "anchor"
for p in P[1:]:
    assert p["refs"] == ["anchor"], p
for p in P:
    t = p["prompt"].lower()
    assert "cinematic" not in t.replace("no cinematic", ""), p["key"]
    if p["group"] == "expressions":
        for lab in ("happy", "angry", "sad", "worried"):
            assert f"expression: {lab}" not in t, p["key"]      # muscle action, not labels
EOF

echo "== QC + layout on synthetic plates (correctable cast, uncorrectable dark studio, duplicate)"
python3 - "$T/testchar" <<'EOF'
import sys, hashlib, random
from pathlib import Path
from PIL import Image, ImageDraw
W = Path(sys.argv[1]); (W / "_raw").mkdir(); (W / "plates").mkdir()
import json
P = json.load(open(W / "prompts.json"))
random.seed(1)
for i, p in enumerate(P):
    k = p["key"]
    bg = (232, 232, 232)
    if k == "turn_side": bg = (236, 214, 180)            # planted warm cast: white balance should FIX it
    if k == "turn_back": bg = (40, 40, 40)               # planted dark studio: gamma can't rescue -> regenerate
    im = Image.new("RGB", (512, 768), bg); d = ImageDraw.Draw(im)
    r = random.Random(i if k != "expr_sad" else [q["key"] for q in P].index("expr_happy"))  # planted duplicate
    for _ in range(12):
        x, y = r.randint(120, 380), r.randint(160, 600)
        d.ellipse((x, y, x + r.randint(40, 140), y + r.randint(40, 140)), fill=(r.randint(0, 200),) * 3)
    raw = W / "_raw" / f"{k}.{hashlib.sha1(k.encode()).hexdigest()[:8]}.png"
    im.save(raw); im.save(W / "plates" / f"{k}.png")
EOF
$B qc "$S" > $T/o 2>&1; rc=$?
grep -q "QC: FAIL" $T/o && ok "QC fails the set" || bad "QC verdict: $(grep QC: $T/o)"
python3 - "$T/testchar/qc.json" <<'EOF' && ok "warm cast corrected, not re-rolled (raw >12 -> fixed <=12)" || bad "cast correction"
import json, sys
r = json.load(open(sys.argv[1]))["plates"]["turn_side"]
assert r["raw_neutrality"] > 12 and r["neutrality"] <= 12 and r["ok"], r
EOF
grep -q "regenerate:.*turn_back" $T/o && ok "flags the uncorrectable dark-studio plate" || bad "dark studio not flagged: $(grep QC: $T/o)"
grep -q "regenerate:.*expr_happy\|regenerate:.*expr_sad" $T/o && ok "flags the duplicate expression pair" || bad "duplicate not flagged"
[ -f $T/testchar/sheet.jpg ] && ok "sheet composed" || bad "no sheet"
python3 -c "from PIL import Image; im=Image.open('$T/testchar/sheet.jpg'); assert im.size==(2400,3300), im.size" && ok "sheet 2400x3300" || bad "sheet size"
python3 - "$T/testchar" <<'EOF' && ok "pack ranks face_front first, excludes QC failures + materials" || bad "pack"
import json, sys
m = json.load(open(sys.argv[1] + "/manifest.json"))
assert m["pack_order"][0] == "01_face_front.png", m["pack_order"][:3]
assert not any("turn_back" in x for x in m["pack_order"]), "QC-failed plate in pack"
assert any("turn_side" in x for x in m["pack_order"]), "corrected plate wrongly dropped"
assert not any("material_" in x for x in m["pack_order"])
assert m["qc_pass"] is False and "turn_back" in m["excluded_by_qc"]
assert len(m["top_refs"]["4"]) == 4
EOF
cp $T/testchar/sheet.jpg /tmp/rs_test_sheet.jpg
rm -rf "$T"
echo "RESULT: $PASS passed, $FAIL failed"
[ $FAIL = 0 ]
