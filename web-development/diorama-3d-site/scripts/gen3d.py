#!/usr/bin/env python3
"""gen3d.py - diorama asset pipeline on Replicate: jobs.json -> product plate (image) -> textured PBR GLB.

Replaces dioramas' fal pipeline (Nano Banana 2 + Meshy 7.1) with Replicate models, same resumable shape.

    python3 gen3d.py jobs.json --dry-run                 # every request + cost, no spend
    python3 gen3d.py jobs.json --stage images --max-usd 1 # plates only: LOOK at them before paying for meshes
    python3 gen3d.py jobs.json --stage meshes --max-usd 3
    python3 gen3d.py jobs.json --only lamp --force lamp   # redo one asset
jobs.json:
    {"site_dir": ".", "image_model": "google/nano-banana-pro", "mesh_model": "tencent/hunyuan-3d-3.1",
     "images": [{"id": "lamp", "prompt": "...", "raw": false, "aspect_ratio": "1:1", "edit_from": ["other-id"]}],
     "meshes": [{"id": "lamp", "image": "lamp", "faces": 200000, "pbr": true}]}
Outputs: <site>/assets/src/<id>.png, <site>/assets/raw/<id>.glb ; ledger <site>/assets/ledger3d.json
Prices (Replicate model pages, 2026-10-03): nano-banana-pro 2K $0.15, flux-2-pro ~$0.06, hunyuan-3d-3.1 $0.50/model,
rodin Gen-2 $0.40/model. Re-check before big runs.
"""
import json
import os
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

UA = "hermes-diorama/1.0"
API = "https://api.replicate.com/v1"
# Same suffix dioramas uses for its plates: a clean object on white is what image-to-3D needs.
STYLE_SUFFIX = (" Single isolated object, centered, full object visible with generous margin, three-quarter view from slightly above, "
                "plain pure white seamless studio background, soft even diffuse lighting, no cast shadows on background, no text, no watermark, "
                "ultra detailed, sharp focus, product-render clarity, physically plausible materials.")
PRICE = {"google/nano-banana-pro": 0.15, "google/nano-banana": 0.039, "black-forest-labs/flux-2-pro": 0.06,
         "tencent/hunyuan-3d-3.1": 0.50, "hyper3d/rodin": 0.40}


def token():
    t = os.environ.get("REPLICATE_API_TOKEN")
    for f in (Path.home() / ".hermes/.env", Path.cwd() / ".env"):
        if t:
            break
        if f.exists():
            m = re.search(r"^REPLICATE_API_TOKEN=(.+)$", f.read_text(), re.M)
            t = m.group(1).strip().strip("\"'") if m else None
    if not t:
        sys.exit("REPLICATE_API_TOKEN not set")
    return t


def call(method, url, tok, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def upload(path, tok):
    p = Path(path)
    b = f"----hermes{uuid.uuid4().hex}"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"content\"; filename=\"{p.name}\"\r\nContent-Type: image/png\r\n\r\n").encode() \
        + p.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"{API}/files", data=body, method="POST", headers={
        "Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={b}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["urls"]["get"]


def fetch(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=600) as r:
        dest.write_bytes(r.read())


def first_url(out):
    if isinstance(out, str):
        return out
    if isinstance(out, list):
        return out[0]
    if isinstance(out, dict):  # trellis-style {"model_file": ...}
        for k in ("model_file", "glb", "mesh", "output"):
            if out.get(k):
                return out[k]
    raise RuntimeError(f"unrecognised output shape: {str(out)[:200]}")


def image_input(model, prompt, aspect, refs):
    if model.startswith("google/nano-banana"):
        d = {"prompt": prompt, "aspect_ratio": aspect, "output_format": "png"}
        if model.endswith("-pro"):
            d["resolution"] = "2K"
        if refs:
            d["image_input"] = refs
        return d
    d = {"prompt": prompt, "aspect_ratio": aspect, "output_format": "png", "resolution": "2 MP"}
    if refs:
        d["input_images"] = refs
    return d


def mesh_input(model, img_url, job):
    if model == "hyper3d/rodin":
        return {"images": [img_url], "tier": job.get("tier", "Gen-2"), "material": "PBR", "mesh_mode": job.get("mesh_mode", "Raw"),
                "quality": job.get("quality", "high"), "geometry_file_format": "glb"}
    return {"image": img_url, "enable_pbr": job.get("pbr", True), "face_count": int(job.get("faces", 200000)), "generate_type": "Normal"}


def predict(ledger, lpath, key, model, inp, cost, tok, cap, dry):
    j = ledger["jobs"].get(key)
    if j and j.get("status") == "succeeded" and j.get("output"):
        return j["output"]
    if dry:
        print(f"  DRY {key}: {model} ~${cost:.2f}  {json.dumps(inp)[:240]}")
        return None
    if not (j and j.get("id") and j.get("status") not in ("failed", "canceled")):
        if ledger["spent"] + cost > cap:
            sys.exit(f"STOP: {key} (~${cost:.2f}) would exceed --max-usd {cap} (spent ~${ledger['spent']:.2f})")
        r = call("POST", f"{API}/models/{model}/predictions", tok, {"input": inp})
        j = ledger["jobs"][key] = {"id": r["id"], "model": model, "cost": cost, "status": r.get("status"), "at": time.strftime("%FT%T")}
        ledger["spent"] = round(ledger["spent"] + cost, 3)
        lpath.write_text(json.dumps(ledger, indent=1))
        print(f"  submitted {key} {r['id']} (~${cost:.2f}; total ~${ledger['spent']:.2f})")
    t0, pd = time.time(), {}
    while time.time() - t0 < 1800:
        pd = call("GET", f"{API}/predictions/{j['id']}", tok)
        if pd.get("status") in ("succeeded", "failed", "canceled"):
            break
        time.sleep(8)
    j["status"] = pd.get("status")
    if j["status"] != "succeeded":
        j["error"] = str(pd.get("error"))[:400]
        lpath.write_text(json.dumps(ledger, indent=1))
        raise RuntimeError(f"{key} {j['status']}: {pd.get('error')}\n logs: {(pd.get('logs') or '')[-400:]}\n id {j['id']}")
    j["output"] = first_url(pd["output"])
    j["predict_time"] = (pd.get("metrics") or {}).get("predict_time")
    lpath.write_text(json.dumps(ledger, indent=1))
    return j["output"]


def main(a):
    if not a or a[0].startswith("-"):
        sys.exit(__doc__)
    jp = Path(a[0]).resolve()
    jobs = json.loads(jp.read_text())
    site = (jp.parent / jobs.get("site_dir", ".")).resolve()
    opt = lambda n, d=None: a[a.index(n) + 1] if n in a else d
    dry, stage = "--dry-run" in a, opt("--stage", "all")
    cap = float(opt("--max-usd", 1e9 if dry else 0))
    if not dry and cap <= 0:
        sys.exit("refusing to spend without --max-usd (run --dry-run first)")
    only = set(opt("--only", "").split(",")) - {""}
    force = set(opt("--force", "").split(",")) - {""}
    im_model = jobs.get("image_model", "google/nano-banana-pro")
    me_model = jobs.get("mesh_model", "tencent/hunyuan-3d-3.1")
    tok = None if dry else token()
    lpath = site / "assets/ledger3d.json"
    lpath.parent.mkdir(parents=True, exist_ok=True)
    ledger = json.loads(lpath.read_text()) if lpath.exists() else {"spent": 0.0, "jobs": {}}
    for k in force:
        for key in [x for x in ledger["jobs"] if x.split(":")[1] == k]:
            ledger["jobs"].pop(key)
    est = 0.0
    if stage in ("images", "all"):
        for j in jobs.get("images", []):
            if only and j["id"] not in only:
                continue
            dest = site / "assets/src" / f"{j['id']}.png"
            cost = PRICE.get(im_model, 0.15)
            est += cost
            if dest.exists() and j["id"] not in force and not dry:
                print(f"  have {dest.name}"); continue
            refs = []
            if j.get("edit_from") and not dry:
                refs = [upload(site / "assets/src" / f"{r}.png", tok) for r in j["edit_from"]]
            prompt = j["prompt"] if j.get("raw") else j["prompt"] + STYLE_SUFFIX
            out = predict(ledger, lpath, f"image:{j['id']}", im_model, image_input(im_model, prompt, j.get("aspect_ratio", "1:1"), refs),
                          cost, tok, cap, dry)
            if out:
                fetch(out, dest); print(f"  saved assets/src/{dest.name}")
    if stage in ("meshes", "all"):
        for j in jobs.get("meshes", []):
            if only and j["id"] not in only:
                continue
            dest = site / "assets/raw" / f"{j['id']}.glb"
            model = j.get("model", me_model)
            cost = PRICE.get(model, 0.5)
            est += cost
            if dest.exists() and j["id"] not in force and not dry:
                print(f"  have {dest.name}"); continue
            src = site / "assets/src" / f"{j.get('image', j['id'])}.png"
            if not dry and not src.exists():
                sys.exit(f"missing plate {src} (run --stage images first)")
            url = "<upload plate>" if dry else upload(src, tok)
            out = predict(ledger, lpath, f"mesh:{j['id']}", model, mesh_input(model, url, j), cost, tok, cap, dry)
            if out:
                fetch(out, dest); print(f"  saved assets/raw/{dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
    print(f"\nestimate for this run: ~${est:.2f}   ledger spent: ~${ledger['spent']:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
