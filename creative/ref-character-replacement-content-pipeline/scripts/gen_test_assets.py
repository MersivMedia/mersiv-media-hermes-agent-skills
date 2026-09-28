#!/usr/bin/env python3
"""Generate a test source video + replacement character for the H3 refswap pipeline.

Colour choices are deliberate: the source performer wears grey, the replacement
character wears TEAL with COPPER hair. Those signatures are absent from the
source, so their share of output pixels is an objective identity-transfer
measurement (see video-character-replacement skill).
"""
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

OUT = Path.home() / ".hermes/data/ref-character-replacement/test_assets"
OUT.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ["REPLICATE_API_TOKEN"]

opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "Hermes-RefSwap/1.0")]
urllib.request.install_opener(opener)

JOBS = {
    "source": ("bytedance/seedance-1-lite", {
        "prompt": ("A man in a plain grey hoodie and black jeans stands in the centre of an "
                   "empty concrete warehouse, full body visible head to toe for the entire shot. "
                   "He raises his right hand and waves at the camera, lowers it, then takes one "
                   "step to his left and turns his body three-quarters to the side. "
                   "Wide shot, eye level, static locked-off camera, soft even overhead daylight, "
                   "photorealistic, natural motion."),
        "duration": 5, "resolution": "720p", "aspect_ratio": "16:9",
        "camera_fixed": True, "fps": 24, "seed": 4242,
    }, "source_raw.mp4"),
    "character": ("black-forest-labs/flux-2-pro", {
        "prompt": ("Full-body photograph of a fictional woman, head to toe fully in frame, standing "
                   "facing the camera in a relaxed neutral pose, arms at her sides. Shoulder-length "
                   "copper-red hair. Teal utility jacket, dark grey cargo trousers, black boots. "
                   "Plain seamless light-grey studio backdrop, even soft lighting, no props, "
                   "no text, photorealistic."),
        "aspect_ratio": "2:3", "output_format": "png", "seed": 4242,
    }, "character.png"),
}
results = {}


def run(name, model, inp, fname):
    t0 = time.time()
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{model}/predictions",
        data=json.dumps({"input": inp}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    pid, pd = d["id"], d
    while pd.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > 900:
            results[name] = f"TIMEOUT id={pid}"
            return
        time.sleep(5)
        with urllib.request.urlopen(urllib.request.Request(
                f"https://api.replicate.com/v1/predictions/{pid}",
                headers={"Authorization": f"Bearer {TOKEN}"}), timeout=30) as r:
            pd = json.load(r)
    if pd["status"] != "succeeded":
        results[name] = (f"{pd['status']} error={pd.get('error')} "
                         f"logs={(pd.get('logs') or '')[-400:]} id={pid}")
        return
    out = pd["output"]
    url = out if isinstance(out, str) else out[0]
    data = urllib.request.urlopen(url, timeout=120).read()
    (OUT / fname).write_bytes(data)
    m = pd.get("metrics") or {}
    results[name] = (f"OK {fname} {len(data)/1e6:.2f}MB in {time.time()-t0:.0f}s "
                     f"(predict_time={m.get('predict_time')}) id={pid}")


threads = [threading.Thread(target=run, args=(n, *j)) for n, j in JOBS.items()]
for t in threads:
    t.start()
for t in threads:
    t.join()
for k, v in results.items():
    print(f"{k:<10} {v}")
sys.exit(0 if all(v.startswith("OK") for v in results.values()) else 1)
