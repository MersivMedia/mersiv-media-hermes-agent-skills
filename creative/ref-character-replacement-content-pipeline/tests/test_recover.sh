#!/usr/bin/env bash
# recover_upscales.sh against the real 09-28 batch shape: J01 has 2k, its 4k was
# saved by ComfyUI but never copied; J02 has none; J03 asked for none.
set -u
SK="$(cd "$(dirname "$0")/.." && pwd)"
SRC=~/.hermes/data/ref-character-replacement/batches/2026-09-28_perf-a-serial
T=$(mktemp -d); P=0; F=0
ok(){ P=$((P+1)); echo "  PASS $1"; }; bad(){ F=$((F+1)); echo "  FAIL $1"; }
B=$T/batches/2026-09-28_perf-a-serial; mkdir -p $B/renders $B/upscaled
cp $SRC/manifest.csv $B/
for f in $SRC/renders/*.mp4; do : > $B/renders/$(basename $f); done
: > $B/upscaled/J01_source__reference-complex_bg_480p_2k.mp4; echo x > $B/upscaled/J01_source__reference-complex_bg_480p_2k.mp4
O=$T/ComfyUI/output/refswap_up/2026-09-28_perf-a-serial; mkdir -p $O
echo 4k > $O/J01_source__reference-complex_bg_480p_4k_00001_.mp4
out=$(REFSWAP_COMFY=$T/ComfyUI bash $SK/pod/recover_upscales.sh $B 1440 2160); echo "$out" | sed 's/^/    /'
echo "$out" | grep -q "have   J01_source__reference-complex_bg_480p_2k" && ok "J01 2k kept" || bad "J01 2k"
[ -s $B/upscaled/J01_source__reference-complex_bg_480p_4k.mp4 ] && ok "J01 4k adopted from ComfyUI output, not redone" || bad "J01 4k"
[ ! -e $B/upscale_queue/J01_source__reference-complex_bg_480p__2160.json ] && ok "no ticket for adopted 4k" || bad "duplicate 4k ticket"
[ -e $B/upscale_queue/J02_source__reference-complex_bg_768p__1440.json ] && [ -e $B/upscale_queue/J02_source__reference-complex_bg_768p__2160.json ] && ok "J02 2k+4k ticketed" || bad "J02 tickets: $(ls $B/upscale_queue)"
[ -z "$(ls $B/upscale_queue | grep J03)" ] && ok "J03 (no upscale requested) left alone" || bad "J03 ticketed"
python3 -c "import json;t=json.load(open('$B/upscale_queue/J02_source__reference-complex_bg_768p__2160.json'));assert t['src_res']==768 and t['label']=='4k' and t['out'].endswith('_768p_4k.mp4'),t" && ok "ticket fields match batch_runner's shape" || bad "ticket fields"
out2=$(REFSWAP_COMFY=$T/ComfyUI bash $SK/pod/recover_upscales.sh $B 1440 2160)
[ "$(ls $B/upscale_queue | wc -l)" = 2 ] && ok "idempotent re-run (still 2 tickets)" || bad "rerun: $(ls $B/upscale_queue)"
# adopt-only: "@2160" must adopt a saved file but never ticket a new 4K job
rm -f $B/upscale_queue/* $B/upscaled/J01_source__reference-complex_bg_480p_4k.mp4
rm -f $O/*
out3=$(REFSWAP_COMFY=$T/ComfyUI bash $SK/pod/recover_upscales.sh $B 1440 @2160)
[ -e $B/upscale_queue/J02_source__reference-complex_bg_768p__1440.json ] && [ ! -e $B/upscale_queue/J02_source__reference-complex_bg_768p__2160.json ] && ok "@2160 never tickets a new 4K job" || bad "adopt-only tickets: $(ls $B/upscale_queue)"
echo 4k > $O/J01_source__reference-complex_bg_480p_4k_00001_.mp4
REFSWAP_COMFY=$T/ComfyUI bash $SK/pod/recover_upscales.sh $B 1440 @2160 >/dev/null
[ -s $B/upscaled/J01_source__reference-complex_bg_480p_4k.mp4 ] && ok "@2160 still adopts a saved 4K" || bad "adopt-only didn't adopt"
echo "RESULT: $P passed, $F failed"; rm -rf $T; [ $F = 0 ]
