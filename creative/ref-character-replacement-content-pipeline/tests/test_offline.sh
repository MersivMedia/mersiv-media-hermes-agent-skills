#!/usr/bin/env bash
# Offline end-to-end test of the batch path (no GPU, no pod, no spend).
# Mock ComfyUI on :18189 (render) and :18190 (upscale lane). Checks:
#  - UI->API conversion validates against the schema (incl. V3 SaveVideo keys)
#  - batch_runner: per-job overrides, dims from source aspect, audio fallback,
#    naming, sidecars, results.csv, upscale tickets
#  - upscale_worker + upscale_run.py --host/--target-height, sidecars, csv
#  - batch_sync compare step (Drive skipped)
#  - autostop idle -> STOP_REQUESTED in batch mode
#   bash tests/test_offline.sh
set -uo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d /tmp/refswap_test.XXXX)
export REFSWAP_COMFY=$T/ComfyUI REFSWAP_RUNDIR=$T/root REFSWAP_BATCHES=$T/batches
export REFSWAP_WORKFLOW=$SK/workflows/h3_refswap.json REFSWAP_UPSCALE=$HOME/.hermes/skills/creative/comfyui/scripts/upscale_run.py
mkdir -p $T/ComfyUI/{input,output} $T/root $T/batches
echo '{"layout":"shared","sage":0,"gpu":"MOCK","gpu_rate_per_hr":2.09}' > $T/root/refswap_state.json
PASS=0; FAIL=0
ok()   { echo "  PASS $*"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL $*"; FAIL=$((FAIL+1)); }
check(){ if eval "$2"; then ok "$1"; else bad "$1"; fi; }

python3 $SK/tests/mock_comfy.py 18189 $T/ComfyUI & M1=$!
python3 $SK/tests/mock_comfy.py 18190 $T/ComfyUI & M2=$!
trap 'kill $M1 $M2 $W1 2>/dev/null; rm -rf $T' EXIT
sleep 1.5

# ---- fixture batch: silent 16:9 source + a 9:16 source with audio ------------
B=$T/batches/2026-09-28_offline
mkdir -p $B/sources $B/refs
ffmpeg -v error -f lavfi -i testsrc2=s=1920x1080:r=24:d=6 -pix_fmt yuv420p $B/sources/src_wide.mp4
ffmpeg -v error -f lavfi -i testsrc2=s=1080x1920:r=24:d=4 -f lavfi -i sine=f=440:d=4 -shortest -pix_fmt yuv420p -c:a aac $B/sources/src_tall.mp4
cp $HOME/.hermes/data/ref-character-replacement/test_assets/reference_complex.png $B/refs/ref_market.png
cat > $B/manifest.csv <<'CSV'
job,source,reference,replace_bg,audio,duration,turbo,steps,res,upscale,seed,instruction
J01,src_wide.mp4,ref_market.png,1,source,5,1,,768,1440;2160,4242,Keep his motion
J02,src_tall.mp4,ref_market.png,0,source,15,1,3,480,,99,
J03,src_wide.mp4,ref_market.png,0,off,5,0,,768,,4242,
CSV

echo "== batch_runner"
python3 $SK/pod/batch_runner.py $B --host http://127.0.0.1:18189 --tag T > $T/runner.log 2>&1; rc=$?
check "runner exit 0" "[ $rc = 0 ]"
[ $rc = 0 ] || tail -30 $T/runner.log
check "3 renders" "[ \$(ls $B/renders/*.mp4 2>/dev/null | wc -l) = 3 ]"
check "naming J01" "[ -f $B/renders/J01_wide__market_bg_768p.mp4 ]"
check "naming J02" "[ -f $B/renders/J02_tall__market_char_480p.mp4 ]"
check "results.csv 3 rows" "[ \$(tail -n +2 $B/results.csv | wc -l) = 3 ]"
check "2 upscale tickets" "[ \$(ls $B/upscale_queue/*.json 2>/dev/null | wc -l) = 2 ]"
python3 - "$B" "$T" <<'EOF' && ok "per-job overrides in submitted graphs" || bad "per-job overrides"
import json, sys, urllib.request
B, T = sys.argv[1], sys.argv[2]
log = json.load(urllib.request.urlopen("http://127.0.0.1:18189/_log"))
assert len(log) == 3, len(log)
def by(api, cls): return [n for n in api.values() if n["class_type"] == cls]
j1, j2, j3 = log
h = lambda a: by(a, "MiniMaxH3ReferenceToVideo")[0]["inputs"]
assert (h(j1)["width"], h(j1)["height"]) == (1344, 768), h(j1)            # 16:9 @768
assert (h(j2)["width"], h(j2)["height"]) == (480, 864), h(j2)             # 9:16 @480, /32
assert (h(j3)["width"], h(j3)["height"]) == (1344, 768)
ar = lambda a: by(a, "H3AudioRoute")[0]["inputs"]["mode"]
assert ar(j1) == "generated", ar(j1)       # silent source asked for 'source' -> falls back
assert ar(j2) == "source" and ar(j3) == "off"
bools = lambda a: {n["inputs"]["value"] for n in by(a, "PrimitiveBoolean")}
prim = {k: [n for n in a.values() if n["class_type"] == "PrimitiveFloat"][0]["inputs"]["value"] for k, a in (("1", j1), ("2", j2))}
assert prim["1"] == 5.0 and abs(prim["2"] - 4.0) < 0.05, prim            # J02 clamped to source length
ints = sorted(n["inputs"]["value"] for n in by(j2, "PrimitiveInt"))
assert 3 in ints, ints                                                      # turbo steps override
assert by(j2, "RandomNoise")[0]["inputs"]["noise_seed"] == 99
sv = by(j1, "SaveVideo")[0]["inputs"]
assert "format.codec" in sv and sv["filename_prefix"].endswith("J01_wide__market_bg_768p"), sv
d = by(j1, "H3PromptDirector")[0]["inputs"]
assert d["instruction"] == "Keep his motion" and isinstance(d["replace_background"], list)
sc = json.load(open(f"{B}/sidecars/J02_tall__market_char_480p.json"))
assert sc["params"]["audio"] == "source" and sc["inputs_sha256"]["source"] and sc["cost_usd"] >= 0
assert sc["timing"]["exec_s"] > 0
EOF

echo "== skip-if-done"
python3 $SK/pod/batch_runner.py $B --host http://127.0.0.1:18189 > $T/runner2.log 2>&1
check "rerun skips finished jobs" "[ \$(grep -c 'already done' $T/runner2.log) = 3 ]"

echo "== upscale_worker (lane 2)"
python3 $SK/pod/upscale_worker.py --host http://127.0.0.1:18190 --idle-exit 8 > $T/up.log 2>&1; rc=$?
check "worker exit 0" "[ $rc = 0 ]"
check "2 upscales" "[ \$(ls $B/upscaled/*.mp4 2>/dev/null | wc -l) = 2 ]"
check "labels 2k/4k" "[ -f $B/upscaled/J01_wide__market_bg_768p_2k.mp4 ] && [ -f $B/upscaled/J01_wide__market_bg_768p_4k.mp4 ]"
check "tickets marked done" "[ \$(ls $B/upscale_queue/*.done 2>/dev/null | wc -l) = 2 ]"
python3 - <<'EOF' && ok "upscale graph: exact target + audio passthrough + V3 save" || bad "upscale graph"
import json, urllib.request
log = json.load(urllib.request.urlopen("http://127.0.0.1:18190/_log"))
assert len(log) == 2, len(log)
dims = sorted((n["inputs"]["width"], n["inputs"]["height"]) for a in log for n in a.values() if n["class_type"] == "ImageScale")
assert dims == [(2512, 1440), (3776, 2160)], dims       # 1344x768 * 1.875 / 2.8125, floored to /16
for a in log:
    cv = [n for n in a.values() if n["class_type"] == "CreateVideo"][0]["inputs"]
    assert cv.get("audio") == ["2", 1], cv
    sv = [n for n in a.values() if n["class_type"] == "SaveVideo"][0]["inputs"]
    assert "format.codec" in sv, sv
EOF
check "upscale_results.csv 2 rows" "[ \$(tail -n +2 $B/upscale_results.csv | wc -l) = 2 ]"
[ $FAIL = 0 ] || tail -15 $T/up.log

echo "== autostop (batch mode, fast timers)"
touch $T/root/batch_session
cp $SK/pod/autostop.py $T/autostop.py
sed -i "s#\"/root/#\"$T/root/#g; s#/workspace/batches#$T/batches#g" $T/autostop.py
AUTOSTOP_TICK_S=1 AUTOSTOP_LOG=$T/root/autostop.log AUTOSTOP_IDLE_S=2 LANE_PORTS=18189,18190 python3 $T/autostop.py & W1=$!
for i in $(seq 1 15); do [ -f $T/root/STOP_REQUESTED ] && break; sleep 1; done
check "STOP_REQUESTED written when idle" "[ -f $T/root/STOP_REQUESTED ]"
kill $W1 2>/dev/null

echo "== compare (local make_compare on a mock render)"
bash $SK/scripts/make_compare.sh $B/sources/src_tall.mp4 $B/refs/ref_market.png $B/renders/J02_tall__market_char_480p.mp4 $T/cmp.mp4 >/dev/null 2>&1
check "side-by-side built" "[ -s $T/cmp.mp4 ]"

echo "== perf_report parses sidecars"
mkdir -p ~/.hermes/data/ref-character-replacement/batches/_selftest_A
cp -r $B/sidecars ~/.hermes/data/ref-character-replacement/batches/_selftest_A/
python3 $SK/scripts/perf_report.py _selftest_A _selftest_A _selftest_A > $T/report.md 2>&1; rc=$?
rm -rf ~/.hermes/data/ref-character-replacement/batches/_selftest_A
check "report exit 0" "[ $rc = 0 ]"
check "report has upscale rows" "grep -q '768p | 4k' $T/report.md"
[ $rc = 0 ] || cat $T/report.md | tail -15

echo "RESULT: $PASS passed, $FAIL failed"
[ $FAIL = 0 ]
