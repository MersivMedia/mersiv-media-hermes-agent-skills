#!/usr/bin/env python3
"""gen.py - motion-site asset pipeline on Replicate: plan.json -> keyframe stills -> image-to-video clips.

    python3 gen.py plan.json --dry-run          # print every request + cost estimate, spend nothing
    python3 gen.py plan.json --max-usd 3        # run; stops before any job that would exceed the cap
    python3 gen.py plan.json --only hero        # one section (test-of-one before the batch)
    python3 gen.py plan.json --stage stills     # stills only (review them before paying for video)
    python3 gen.py plan.json --force hero       # regenerate a section even if outputs exist

Resumable: every prediction id is written to <site>/assets/ledger.json BEFORE polling, so a crash
resumes the same prediction instead of paying twice. Outputs:
    <site>/assets/stills/<section>.png  and  <section>_end.png (if the section has an end frame)
    <site>/assets/clips/<section>.mp4
Prices are the live Replicate model-page prices read on 2026-10-03; re-check before big runs.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "hermes-motion-site/1.0"
API = "https://api.replicate.com/v1"

# model -> (kind, price function(params) -> USD, builder(params) -> input dict)
STILL_MODELS = {
    "black-forest-labs/flux-2-pro": 0.015 * 4,   # ~$0.015/MP in + out; 16:9 at "2 MP" ~ 2 MP out -> budget $0.06
    "google/nano-banana-pro": 0.15,              # 2K tier
    "google/nano-banana": 0.039,
}
VIDEO_PRICE = {  # $ per second of output video, by resolution
    "bytedance/seedance-1-lite": {"480p": 0.018, "720p": 0.036, "1080p": 0.072},
    "bytedance/seedance-1-pro": {"480p": 0.03, "720p": 0.06, "1080p": 0.15},
    "kwaivgi/kling-v2.1": {"720p": 0.05, "1080p": 0.09},
}


def load_token():
    tok = os.environ.get("REPLICATE_API_TOKEN")
    if not tok:
        for envf in (Path.home() / ".hermes/.env", Path.cwd() / ".env"):
            if envf.exists():
                m = re.search(r"^REPLICATE_API_TOKEN=(.+)$", envf.read_text(), re.M)
                if m:
                    tok = m.group(1).strip().strip('"').strip("'")
                    break
    if not tok:
        sys.exit("REPLICATE_API_TOKEN not set (env or ~/.hermes/.env)")
    return tok


def call(method, url, tok, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def upload(path, tok):
    """Replicate files API -> URL usable as a model input (keeps request bodies small)."""
    import uuid
    p = Path(path)
    b = f"----hermes{uuid.uuid4().hex}"
    ctype = "image/png" if p.suffix.lower() == ".png" else "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/webp"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"content\"; filename=\"{p.name}\"\r\nContent-Type: {ctype}\r\n\r\n").encode() \
        + p.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"{API}/files", data=body, method="POST", headers={
        "Authorization": f"Bearer {tok}", "Content-Type": f"multipart/form-data; boundary={b}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["urls"]["get"]


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        dest.write_bytes(r.read())
    return dest


def still_cost(model):
    return STILL_MODELS.get(model, 0.15)


def video_cost(model, res, secs):
    return VIDEO_PRICE.get(model, {}).get(res, 0.10) * secs


def still_input(model, prompt, aspect, ref_urls):
    if model.startswith("google/nano-banana"):
        d = {"prompt": prompt, "aspect_ratio": aspect, "output_format": "png"}
        if model.endswith("-pro"):
            d["resolution"] = "2K"
        if ref_urls:
            d["image_input"] = ref_urls
        return d
    d = {"prompt": prompt, "aspect_ratio": aspect, "output_format": "png", "resolution": "2 MP"}
    if ref_urls:
        d["input_images"] = ref_urls
    return d


def video_input(model, prompt, first_url, last_url, secs, res, aspect):
    if model.startswith("kwaivgi/kling"):
        d = {"prompt": prompt, "start_image": first_url, "duration": 5 if secs <= 5 else 10,
             "mode": "pro" if res == "1080p" else "standard",
             "negative_prompt": "text, watermark, logo distortion, flicker, jump cut, morphing face"}
        if last_url:
            d["end_image"] = last_url
        return d
    d = {"prompt": prompt, "image": first_url, "duration": int(secs), "resolution": res, "aspect_ratio": aspect,
         "fps": 24, "camera_fixed": False}
    if last_url:
        d["last_frame_image"] = last_url
    return d


class Ledger:
    def __init__(self, path):
        self.path = path
        self.d = json.loads(path.read_text()) if path.exists() else {"spent": 0.0, "jobs": {}}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.d, indent=1))


def run_prediction(ledger, key, model, inp, cost, tok, max_usd, dry):
    """Submit (or resume) one prediction; returns the output URL. Writes the id before polling."""
    job = ledger.d["jobs"].get(key)
    if job and job.get("status") == "succeeded" and job.get("output"):
        return job["output"]
    if dry:
        print(f"  DRY {key}: {model}  ~${cost:.3f}\n      {json.dumps(inp)[:300]}")
        return None
    if not (job and job.get("id") and job.get("status") not in ("failed", "canceled")):
        if ledger.d["spent"] + cost > max_usd:
            sys.exit(f"STOP: {key} (~${cost:.2f}) would exceed --max-usd {max_usd} (spent ${ledger.d['spent']:.2f})")
        r = call("POST", f"{API}/models/{model}/predictions", tok, {"input": inp})
        job = {"id": r["id"], "model": model, "cost": cost, "status": r.get("status"), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        ledger.d["jobs"][key] = job
        ledger.d["spent"] = round(ledger.d["spent"] + cost, 4)
        ledger.save()
        print(f"  submitted {key}: {r['id']} (~${cost:.3f}, running total ~${ledger.d['spent']:.2f})")
    deadline = time.time() + 900
    pd = {}
    while time.time() < deadline:
        pd = call("GET", f"{API}/predictions/{job['id']}", tok)
        if pd.get("status") in ("succeeded", "failed", "canceled"):
            break
        time.sleep(4)
    job["status"] = pd.get("status")
    if pd.get("status") != "succeeded":
        job["error"] = str(pd.get("error"))[:400]
        ledger.save()
        raise RuntimeError(f"{key} {pd.get('status')}: {pd.get('error')}\n  logs: {(pd.get('logs') or '')[-500:]}\n  id: {job['id']}")
    out = pd["output"]
    job["output"] = out if isinstance(out, str) else out[0]
    job["predict_time"] = (pd.get("metrics") or {}).get("predict_time")
    ledger.save()
    return job["output"]


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    plan_path = Path(argv[0]).resolve()
    plan = json.loads(plan_path.read_text())
    site = (plan_path.parent / plan.get("site_dir", ".")).resolve()

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default
    dry = "--dry-run" in argv
    max_usd = float(opt("--max-usd", 0 if not dry else 1e9))
    only = set(opt("--only", "").split(",")) - {""}
    force = set(opt("--force", "").split(",")) - {""}
    stage = opt("--stage", "all")
    if not dry and max_usd <= 0:
        sys.exit("refusing to spend without --max-usd (run --dry-run first to see the estimate)")

    style = plan.get("style", "")
    still_model = plan.get("still_model", "black-forest-labs/flux-2-pro")
    video_model = plan.get("video_model", "bytedance/seedance-1-lite")
    res, aspect = plan.get("resolution", "720p"), plan.get("aspect_ratio", "16:9")
    tok = None if dry else load_token()
    ledger = Ledger(site / "assets/ledger.json")
    for k in force:
        for key in [x for x in ledger.d["jobs"] if x.split(":")[0] == k]:
            ledger.d["jobs"].pop(key)
    refs = [str((plan_path.parent / r).resolve()) for r in plan.get("brand_refs", [])]
    ref_urls_cache = {}

    def ref_urls():
        if dry or not refs:
            return [f"<upload {Path(r).name}>" for r in refs] if dry else []
        if "u" not in ref_urls_cache:
            ref_urls_cache["u"] = [upload(r, tok) for r in refs]
        return ref_urls_cache["u"]

    total = 0.0
    for s in plan["sections"]:
        sid = s["id"]
        if only and sid not in only:
            continue
        secs = int(s.get("seconds", 5))
        print(f"[{sid}] {s.get('role', '')}  {secs}s")
        # per-section overrides: a phone-only variant (e.g. "hero_m", 9:16) can use its own model, aspect and refs.
        # "refs": image paths (relative to plan.json) sent as image references, e.g. the user's photo, to recompose it.
        s_model = s.get("still_model", still_model)
        s_aspect = s.get("aspect_ratio", aspect)
        s_refs = [str((plan_path.parent / r).resolve()) for r in s.get("refs", [])]
        stills = {"start": s["still"], **({"end": s["end_still"]} if s.get("end_still") else {})}
        urls = {}
        for which, prompt in stills.items():
            dest = site / "assets/stills" / (f"{sid}.png" if which == "start" else f"{sid}_end.png")
            full = f"{prompt.strip()} {style}".strip()
            cost = still_cost(s_model)
            if dest.exists() and sid not in force and not dry:
                print(f"  have {dest.name}")
            else:
                total += cost
                if s_refs:
                    use_refs = [f"<upload {Path(r).name}>" for r in s_refs] if dry else [upload(r, tok) for r in s_refs]
                else:
                    use_refs = ref_urls() if s.get("use_brand_refs") else []
                out = run_prediction(ledger, f"{sid}:{which}", s_model, still_input(s_model, full, s_aspect, use_refs),
                                     cost, tok, max_usd, dry)
                if out:
                    download(out, dest)
                    print(f"  saved {dest.relative_to(site)}")
            urls[which] = dest
        if stage == "stills":
            continue
        clip = site / "assets/clips" / f"{sid}.mp4"
        vcost = video_cost(video_model, res, secs)
        if clip.exists() and sid not in force and not dry:
            print(f"  have {clip.name}")
            continue
        total += vcost
        motion = f"{s['motion'].strip()} Single continuous shot, no cuts, no text, no captions, no watermark."
        first = "<upload start>" if dry else upload(urls["start"], tok)
        last = ("<upload end>" if dry else upload(urls["end"], tok)) if "end" in urls else None
        vinp = video_input(video_model, motion, first, last, secs, res, s_aspect)
        if "camera_fixed" in s and "camera_fixed" in vinp:   # per-section: lock the camera (stops drift into bright sky)
            vinp["camera_fixed"] = bool(s["camera_fixed"])
        out = run_prediction(ledger, f"{sid}:clip", video_model, vinp,
                             vcost, tok, max_usd, dry)
        if out:
            download(out, clip)
            print(f"  saved {clip.relative_to(site)}")
    print(f"\nestimate for this run: ~${total:.2f}  (ledger spent so far: ~${ledger.d['spent']:.2f})")


if __name__ == "__main__":
    main(sys.argv[1:])
