#!/usr/bin/env python3
"""Surgically edit a single chapter slide using gpt-image-2 on a cropped region.

Use this for in-place edits like "change the big number from X to Y" or
"fix a typo in the title" where the full-slide gpt-image-2 approach reframes
and ruins the composition.

The trick: crop a NARROW region around just the element you want to edit
(typically the left third of the slide), send only that to gpt-image-2 with
a tightly scoped prompt, then paste the result back into the original. The
rest of the slide is untouched.

Usage:
    surgical_slide_edit.py SRC.png DST.png \\
        --crop X0,Y0,X1,Y1 \\
        --prompt "Change the chapter number 5 to 4..." \\
        [--aspect 2:3]
"""
import os, json, base64, time, urllib.request, argparse
from PIL import Image

def call_gpt(crop_path, dst_path, prompt, target_size, aspect="2:3"):
    token = os.environ["REPLICATE_API_TOKEN"]
    with open(crop_path, "rb") as f:
        data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    body = json.dumps({
        "input": {
            "prompt": prompt,
            "input_images": [data_uri],
            "aspect_ratio": aspect,
            "output_format": "png",
            "number_of_images": 1,
            "quality": "high",
        }
    }).encode()
    req = urllib.request.Request(
        "https://api.replicate.com/v1/models/openai/gpt-image-2/predictions",
        data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "Prefer": "wait=60"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    pid = resp["id"]; status = resp.get("status"); output = resp.get("output")
    deadline = time.time() + 240
    while status not in ("succeeded","failed","canceled") and time.time() < deadline:
        time.sleep(3)
        poll = urllib.request.Request(
            f"https://api.replicate.com/v1/predictions/{pid}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(poll, timeout=30) as r:
            pd = json.loads(r.read())
        status = pd.get("status"); output = pd.get("output")
    if status != "succeeded":
        raise RuntimeError(f"failed: {status} {pd.get('error')}")
    url = output if isinstance(output, str) else output[0]
    img_bytes = urllib.request.urlopen(url, timeout=60).read()
    tmp = dst_path + ".raw.png"
    with open(tmp, "wb") as f: f.write(img_bytes)
    gen = Image.open(tmp).convert("RGB")
    tw, th = target_size
    gw, gh = gen.size
    scale = max(tw/gw, th/gh)
    new_size = (int(gw*scale), int(gh*scale))
    gen = gen.resize(new_size, Image.LANCZOS)
    left = (gen.width - tw) // 2
    top = (gen.height - th) // 2
    gen = gen.crop((left, top, left+tw, top+th))
    gen.save(dst_path)
    os.remove(tmp)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--crop", required=True, help="X0,Y0,X1,Y1")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--aspect", default="2:3", help="gpt-image-2 aspect ratio (1:1, 3:2, 2:3)")
    args = ap.parse_args()

    x0,y0,x1,y1 = [int(v) for v in args.crop.split(",")]
    img = Image.open(args.src).convert("RGB")
    crop = img.crop((x0,y0,x1,y1))
    crop_w, crop_h = x1-x0, y1-y0
    crop_path = args.dst + ".crop.png"
    crop.save(crop_path)
    fixed_path = args.dst + ".fixed.png"
    call_gpt(crop_path, fixed_path, args.prompt, (crop_w, crop_h), aspect=args.aspect)
    out = img.copy()
    out.paste(Image.open(fixed_path).convert("RGB"), (x0,y0))
    out.save(args.dst)
    os.remove(crop_path); os.remove(fixed_path)
    print(f"✓ Saved: {args.dst}")

if __name__ == "__main__":
    main()
