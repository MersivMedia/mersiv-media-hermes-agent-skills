#!/usr/bin/env python3
"""Generate a match-cut relay keyframe chain on Replicate, then QC it.

Each keyframe after the first is an image EDIT of its predecessor, so the relay
object keeps its screen position while the world changes (see
references/match-cut-relay-transitions.md). Resumable: existing <out>/<id>.png
files are skipped, so to regenerate one frame, move it to <out>/_rejected/ and
rerun. Uses curl, since Replicate filters urllib's default UA. Inputs go
through the files API. Every call is appended to <out>/spend.jsonl.

plan.json: [{"id":"K0","from":"-","model":"black-forest-labs/flux-2-pro",
             "prompt":"...","desc":"short label"},
            {"id":"K1","from":"K0","model":"google/nano-banana","prompt":"..."}]

  keyframe_chain.py gen plan.json --out DIR [--only K0] [--max-usd 1.0]
  keyframe_chain.py qc  plan.json --out DIR [--hue red]   # drift table + contact sheet

Prices (live 2026-09-29): flux-2-pro 16:9 2 MP ~$0.045, nano-banana $0.039.
Start with `--only K0` and look at it before chaining the rest.
"""
import argparse, json, os, subprocess, sys, time

PRICE = {"black-forest-labs/flux-2-pro": 0.045, "google/nano-banana": 0.039}


def curl(*a, timeout=200):
    r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), *a], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"curl rc={r.returncode}: {r.stderr[:300]}")
    return r.stdout


def upload(tok, path):
    d = json.loads(curl("-H", f"Authorization: Bearer {tok}", "-F", f"content=@{path};type=image/png",
                        "https://api.replicate.com/v1/files"))
    return d["urls"]["get"]


def predict(tok, model, inp):
    d = json.loads(curl("-H", f"Authorization: Bearer {tok}", "-H", "Content-Type: application/json",
                        "-H", "Prefer: wait=60", "-d", json.dumps({"input": inp}),
                        f"https://api.replicate.com/v1/models/{model}/predictions"))
    if "id" not in d:
        raise RuntimeError(f"create failed: {json.dumps(d)[:400]}")
    t0 = time.time()
    while d.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > 600:
            raise RuntimeError(f"timeout {d['id']}")
        time.sleep(3)
        d = json.loads(curl("-H", f"Authorization: Bearer {tok}", f"https://api.replicate.com/v1/predictions/{d['id']}"))
    if d["status"] != "succeeded":
        raise RuntimeError(f"{d['id']} {d['status']}: {str(d.get('error'))[:400]}")
    o = d["output"]
    return d["id"], (o if isinstance(o, str) else o[0])


def gen(plan, out, only, max_usd):
    tok = os.environ["REPLICATE_API_TOKEN"]
    spent = 0.0
    for k in plan:
        dst = os.path.join(out, f"{k['id']}.png")
        if (only and k["id"] not in only) or os.path.exists(dst):
            continue
        price = PRICE.get(k["model"], 0.05)
        if spent + price > max_usd:
            sys.exit(f"STOP: would pass --max-usd {max_usd} (spent ${spent:.3f})")
        if k.get("from", "-") == "-":
            inp = {"prompt": k["prompt"], "aspect_ratio": "16:9", "resolution": "2 MP",
                   "output_format": "png", "safety_tolerance": 2}
        else:
            src = os.path.join(out, f"{k['from']}.png")
            if not os.path.exists(src):
                sys.exit(f"STOP: {k['id']} needs {k['from']}.png first")
            inp = {"prompt": k["prompt"], "image_input": [upload(tok, src)],
                   "aspect_ratio": "match_input_image", "output_format": "png"}
        pid, url = predict(tok, k["model"], inp)
        curl("-L", "-o", dst, url, timeout=120)
        spent += price
        with open(os.path.join(out, "spend.jsonl"), "a") as f:
            f.write(json.dumps({"t": time.time(), "item": k["id"], "model": k["model"], "pred": pid, "usd": price}) + "\n")
        print(f"{k['id']}: ok pred={pid} ${price:.3f} (run ${spent:.3f})", flush=True)
    print(f"DONE spent ${spent:.3f}")


def blob_centroid(im, hue):
    """Densest saturated-colour blob. False positives when the WORLD shares the
    object's hue (anime fire vs a red crane): treat drift as 'look at it'."""
    import numpy as np
    a = np.asarray(im.convert("HSV")).astype(int)
    h, s, v = a[..., 0], a[..., 1], a[..., 2]
    rng = {"red": ((h < 8) | (h > 245)), "blue": (h > 140) & (h < 180), "green": (h > 60) & (h < 110)}[hue]
    m = rng & (s > 140) & (v > 70)
    H, W = m.shape
    ys, xs = np.nonzero(m)
    if len(xs) < 50:
        return None
    c = 16
    g = np.zeros((H // c + 1, W // c + 1), int)
    np.add.at(g, (ys // c, xs // c), 1)
    stack, seen, blob = [np.unravel_index(np.argmax(g), g.shape)], set(), []
    while stack:
        y, x = stack.pop()
        if (y, x) in seen or not (0 <= y < g.shape[0] and 0 <= x < g.shape[1]) or g[y, x] < c * c * 0.15:
            continue
        seen.add((y, x)); blob.append((y, x))
        stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    by = [b[0] for b in blob]; bx = [b[1] for b in blob]
    return ((min(bx) + max(bx) + 1) * c / 2 / W, (min(by) + max(by) + 1) * c / 2 / H)


def qc(plan, out, hue):
    from PIL import Image, ImageDraw, ImageFont
    prev, rows = None, []
    for k in plan:
        p = os.path.join(out, f"{k['id']}.png")
        if not os.path.exists(p):
            print(f"{k['id']}: MISSING"); continue
        im = Image.open(p).convert("RGB")
        c = blob_centroid(im, hue)
        d = ((c[0] - prev[0]) ** 2 + (c[1] - prev[1]) ** 2) ** 0.5 if (c and prev) else None
        flag = "  <-- LOOK" if d is not None and d > 0.03 else ""
        print(f"{k['id']:<5} {im.size}  " + (f"c=({c[0]:.2f},{c[1]:.2f})" if c else "object NOT FOUND")
              + (f" drift={d:.3f}" if d is not None else "") + flag)
        rows.append((k, im)); prev = c
    tw, th, pad, cols = 480, 270, 34, 4
    sheet = Image.new("RGB", (cols * tw, ((len(rows) + cols - 1) // cols) * (th + pad)), (18, 18, 18))
    dr = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(os.path.expanduser("~/.fonts/Inter-Bold.ttf"), 20)
    except Exception:
        f = ImageFont.load_default()
    for i, (k, im) in enumerate(rows):
        x, y = (i % cols) * tw, (i // cols) * (th + pad)
        sheet.paste(im.resize((tw, th)), (x, y + pad))
        dr.text((x + 8, y + 6), f"{k['id']}  {k.get('desc', '')[:40]}", font=f, fill=(235, 235, 235))
        cx, cy = x + tw / 2, y + pad + th / 2
        dr.line((cx - 10, cy, cx + 10, cy), fill=(0, 255, 200), width=2)
        dr.line((cx, cy - 10, cx, cy + 10), fill=(0, 255, 200), width=2)
    dst = os.path.join(out, "contact_sheet.jpg")
    sheet.save(dst, quality=88)
    print("contact sheet:", dst, "(view it; centre crosshair on every tile)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "qc"])
    ap.add_argument("plan")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--hue", default="red", choices=["red", "blue", "green"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    plan = json.load(open(a.plan))
    if a.cmd == "gen":
        gen(plan, a.out, set(filter(None, a.only.split(","))), a.max_usd)
    else:
        qc(plan, a.out, a.hue)
