#!/usr/bin/env python3
"""Build a character reference sheet + reference pack from an authored spec.

  build_sheet.py init   <slug> --name "Mara Voss" [--anchor photo.jpg]   # write a spec template
  build_sheet.py plan   <spec.yaml>                                     # dry run: plates, prompts, cost
  build_sheet.py run    <spec.yaml> [--only turn_front,expr_happy] [--force] [--yes]
  build_sheet.py qc     <spec.yaml>                                     # re-run gates, no spend
  build_sheet.py compose <spec.yaml>                                    # re-lay the sheet, no spend
  build_sheet.py pack   <spec.yaml>                                     # rebuild pack + manifest

Workdir: ~/.hermes/data/character-reference-sheet/<slug>/
  spec.yaml   _raw/<plate>.<sha8>.png   plates/<plate>.png   pack/   sheet.jpg
  manifest.json   qc.json   prompts.json

Rules this script enforces (each one cost a real session before it was code):
  - one prediction per plate, never a batched "N images" call
  - the anchor exists before anything else and every plate is i2i from it
  - returned-count asserted, provider error + logs surfaced
  - text, swatches and hex codes are drawn by rs_layout, never generated
  - reference plates carry no cinematic grade
  - real identifiable people require consent: 'self' or 'consented'
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rs_layout  # noqa: E402
import rs_qc      # noqa: E402

ROOT = Path(os.environ.get("RS_DATA", Path.home() / ".hermes/data/character-reference-sheet"))
API = "https://api.replicate.com/v1"
UA = "Hermes-RefSheet/1.0"          # default Python-urllib UA is 403'd by Replicate

MODELS = {   # verified live 2026-09-28: existence, input names, per-image price
    "seedream": {"id": "bytedance/seedream-4.5", "refs": "image_input", "max_refs": 14,
                 "price": 0.04, "fixed": {"size": "2K", "sequential_image_generation": "disabled"}},
    "nano": {"id": "google/nano-banana-pro", "refs": "image_input", "max_refs": 14,
             "price": 0.15, "fixed": {"resolution": "2K", "output_format": "png"}},
    "flux": {"id": "black-forest-labs/flux-2-pro", "refs": "input_images", "max_refs": 8,
             "price": 0.06, "fixed": {"resolution": "2 MP", "output_format": "png"}},
}

REF_LIGHT = ("Neutral light-grey seamless studio backdrop (#E8E8E8), flat even white-balanced "
             "front lighting, no coloured gels, no warm or teal cast, no directional shadows, "
             "no vignette, no film grain, no cinematic colour grading. Clean technical reference "
             "plate. One single image, no collage, no grid, no panels, no text, no labels, "
             "no watermark.")
KEEP = ("THIS EXACT PERSON from the reference image: identical face, identical age (no older, "
        "do not add wrinkles or deepen lines), identical hair, build, skin tone, costume, "
        "accessories and footwear. Change nothing except what is described.")

EXPR = {   # physical muscle action, never emotion labels (labels drift to placid)
    "neutral": "relaxed face, lips closed and soft, brows level, eyes open and calm, looking straight into the lens",
    "happy": "genuine smile, cheeks raised, crow's-feet creases at the outer eyes, teeth lightly showing",
    "angry": "brows pulled down and together with a vertical crease, narrowed hard stare, lips pressed thin, nostrils slightly flared, mouth closed",
    "sad": "inner brow ends raised, upper eyelids heavy, mouth corners turned down, lips closed, gaze slightly lowered; under-eye skin clean and even, no tears, no redness",
    "surprised": "eyebrows raised high, eyes wide with white visible above the iris, jaw dropped, mouth open in an O",
    "worried": "inner brows pulled up and together, forehead creased, lips pressed and pulled slightly sideways",
    "confident": "slight closed-mouth smile on one side, chin slightly lifted, steady direct gaze, relaxed brows",
    "determined": "brows lowered and level, jaw set, lips pressed into a firm flat line, focused unblinking stare",
}
POSE = {
    "neutral_stand": "standing straight, weight even, arms relaxed at the sides",
    "walking": "mid-stride walking toward the camera, natural arm swing",
    "sitting": "seated on a plain white cube, relaxed upright posture, hands resting on the knees",
    "relaxed": "casual stance, weight on one leg, one hand in a pocket or resting on the hip",
    "tense": "arms crossed tight, shoulders raised, weight shifted back",
    "action_ready": "wide athletic stance, knees bent, arms out, ready to move",
}
TURN = {
    "front": "full body, facing the camera squarely, head to toe in frame with space above the head and below the feet",
    "three_quarter": "full body, body turned about 45 degrees to the camera's left, both eyes still visible, head to toe in frame",
    "side": "full body, exact 90-degree side profile facing left, head to toe in frame",
    "back": "full body, seen directly from behind, back of the head and heels visible, head to toe in frame",
}
FACE = {
    "front": "head-and-shoulders portrait, facing the camera squarely, eyes directly into the lens",
    "profile": "head-and-shoulders, exact 90-degree side profile facing left",
    "three_quarter": "head-and-shoulders, head turned about 45 degrees, both eyes visible",
}


# ---------------------------------------------------------------- spec ---------
def workdir(spec_path):
    return Path(spec_path).resolve().parent


def load(spec_path):
    s = yaml.safe_load(open(spec_path))
    for k in ("name", "slug", "subject_type", "consent", "profile", "costume"):
        if k not in s:
            sys.exit(f"spec missing '{k}'")
    if s["subject_type"] not in ("fictional", "real_person"):
        sys.exit("subject_type must be fictional or real_person")
    if s["subject_type"] == "real_person" and s["consent"] not in ("self", "consented"):
        sys.exit("REFUSED: a real, identifiable person needs consent: 'self' (the user) or 'consented' "
                 "(they agreed). Public figures and celebrities without consent are not supported; "
                 "make a fictional character instead.")
    if s["subject_type"] == "real_person" and not s.get("anchor", {}).get("from_photo"):
        sys.exit("real_person sheets must start from the person's own photo (anchor.from_photo)")
    s["_expressions"] = s.get("sheet", {}).get("expressions", list(EXPR))
    s["_poses"] = s.get("sheet", {}).get("poses", list(POSE))
    return s


def describe(s):
    p, c, f = s.get("profile", {}), s.get("costume", {}), s.get("face", {})
    bits = [s.get("look") or "", f"{p.get('age', '')} {p.get('body_type', '')}".strip()]
    for k in ("structure", "eyes", "hair", "skin_tone", "makeup"):
        if f.get(k):
            bits.append(f"{k.replace('_', ' ')}: {f[k]}")
    bits.append(f"wearing {c.get('summary', '')}")
    if c.get("accessories"):
        bits.append("accessories: " + ", ".join(c["accessories"]))
    if c.get("footwear"):
        bits.append("footwear: " + c["footwear"])
    return ". ".join(b for b in bits if b)


def plan(s):
    """Ordered plate list. Every plate after the anchor is i2i from the anchor."""
    desc, out = describe(s), []
    sheet = s.get("sheet", {})
    out.append({"key": "anchor", "group": "anchor", "refs": ["_photo"] if s["anchor"].get("from_photo") else [],
                "prompt": (f"{KEEP} " if s["anchor"].get("from_photo") else "") +
                          f"Full-body character reference, standing facing the camera, head to toe in frame. "
                          f"{desc}. {REF_LIGHT}", "aspect": "2:3"})
    for k in sheet.get("turnaround", list(TURN)):
        out.append({"key": f"turn_{k}", "group": "turnaround", "refs": ["anchor"],
                    "prompt": f"{KEEP} {TURN[k]}. {REF_LIGHT}", "aspect": "2:3"})
    for k in sheet.get("face", list(FACE)):
        out.append({"key": f"face_{k}", "group": "face", "refs": ["anchor"],
                    "prompt": f"{KEEP} {FACE[k]}. {REF_LIGHT}", "aspect": "3:4"})
    for k in s["_expressions"]:
        out.append({"key": f"expr_{k}", "group": "expressions", "refs": ["anchor"],
                    "prompt": f"{KEEP} Head-and-shoulders, facing the camera. Expression: {EXPR.get(k, k)}. {REF_LIGHT}",
                    "aspect": "1:1"})
    for k in s["_poses"]:
        out.append({"key": f"pose_{k}", "group": "poses", "refs": ["anchor"],
                    "prompt": f"{KEEP} Full body, {POSE.get(k, k)}, head to toe in frame. {REF_LIGHT}", "aspect": "2:3"})
    for i, d in enumerate((s.get("costume") or {}).get("details") or []):
        out.append({"key": f"costume_{i:02d}", "group": "costume", "refs": ["anchor"],
                    "prompt": f"{KEEP} Tight close-up detail shot of the costume only: {d['describe']}. "
                              "Sharp focus on the material and construction. No face in frame. "
                              "Flat even lighting, no colour grading, no text.", "aspect": "1:1"})
    for i, m in enumerate(s.get("materials") or []):
        out.append({"key": f"material_{i:02d}", "group": "materials", "refs": ["anchor"],
                    "prompt": f"Macro texture swatch filling the whole frame: {m['describe']}, matching the "
                              "reference image exactly in colour and finish. Flat even lighting, no object, "
                              "no background, no text.", "aspect": "1:1"})
    return out


# ------------------------------------------------------------- replicate ------
def curl_json(args, timeout=120):
    r = subprocess.run(["curl", "-s", "-A", UA, "-H", f"Authorization: Bearer {os.environ['REPLICATE_API_TOKEN']}"]
                       + args, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"non-JSON from Replicate: {r.stdout[:300]} {r.stderr[:200]}")


_UP = {}


def upload(p):
    """Files API once per file (data URIs of 2K PNGs blow the ~10 MB body limit)."""
    key = str(Path(p).resolve())
    if key not in _UP:
        d = curl_json(["-F", f"content=@{key}", f"{API}/files"])
        if "urls" not in d:
            raise RuntimeError(f"upload failed for {p}: {d}")
        _UP[key] = d["urls"]["get"]
    return _UP[key]


def predict(model, prompt, refs, aspect, out_raw):
    M = MODELS[model]
    inp = {"prompt": prompt, "aspect_ratio": aspect, **M["fixed"]}
    if refs:
        inp[M["refs"]] = [upload(r) for r in refs][:M["max_refs"]]
    d = curl_json(["-X", "POST", "-H", "Content-Type: application/json",
                   "-d", json.dumps({"input": inp}), f"{API}/models/{M['id']}/predictions"])
    if "id" not in d:
        raise RuntimeError(f"{M['id']} submit failed: {json.dumps(d)[:400]}")
    pid, pd, t0 = d["id"], d, time.time()
    while pd.get("status") not in ("succeeded", "failed", "canceled"):
        if time.time() - t0 > 420:
            raise RuntimeError(f"{M['id']} timed out, id {pid}")
        time.sleep(3)
        pd = curl_json([f"{API}/predictions/{pid}"])
    if pd["status"] != "succeeded":
        raise RuntimeError(f"{M['id']} {pd['status']}\n  error: {pd.get('error')}\n"
                           f"  logs: {(pd.get('logs') or '')[-600:]}\n  id: {pid}")
    urls = pd["output"] if isinstance(pd["output"], list) else [pd["output"]]
    if len(urls) != 1:                                   # under-delivery is silent
        raise RuntimeError(f"expected 1 image, got {len(urls)} (id {pid})")
    tmp = out_raw.with_suffix(".dl")
    subprocess.run(["curl", "-s", "-L", "-o", str(tmp), urls[0]], check=True, timeout=120)
    h = hashlib.sha1(tmp.read_bytes()).hexdigest()[:8]
    final = out_raw.parent / f"{out_raw.stem}.{h}.png"
    from PIL import Image
    Image.open(tmp).convert("RGB").save(final)
    tmp.unlink()
    return final, pid


# ---------------------------------------------------------------- commands ----
def latest_raw(W, key):
    c = sorted((W / "_raw").glob(f"{key}.*.png"), key=lambda p: p.stat().st_mtime)
    return c[-1] if c else None


def cmd_init(a):
    W = ROOT / a.slug
    W.mkdir(parents=True, exist_ok=True)
    tpl = (HERE.parent / "templates" / "spec.yaml").read_text()
    tpl = tpl.replace("__NAME__", a.name).replace("__SLUG__", a.slug)
    if a.anchor:
        dst = W / ("photo" + Path(a.anchor).suffix.lower())
        shutil.copyfile(a.anchor, dst)
        tpl = tpl.replace("from_photo: null", f"from_photo: {dst.name}")
    (W / "spec.yaml").write_text(tpl)
    print(f"spec: {W / 'spec.yaml'}  (fill it in, then `plan`)")


def cmd_plan(a):
    s = load(a.spec); W = workdir(a.spec); P = plan(s)
    M = MODELS[s.get("model", "seedream")]
    todo = [p for p in P if not (W / "plates" / f"{p['key']}.png").exists()]
    print(f"{s['name']}  model={M['id']}  plates={len(P)}  to render={len(todo)}")
    for p in P:
        mark = " " if p in todo else "✓"
        print(f"  {mark} {p['key']:<22} {p['group']:<11} {p['aspect']:<4} refs={p['refs']}")
    est = len(todo) * M["price"]
    print(f"estimate: {len(todo)} × ${M['price']:.3f} = ${est:.2f}  (+ ~15% for re-rolls → ${est * 1.15:.2f})")
    (W / "prompts.json").write_text(json.dumps(P, indent=1))
    print(f"prompts: {W / 'prompts.json'}")
    return s, W, P, todo, est


def cmd_run(a):
    s, W, P, todo, est = cmd_plan(a)
    if a.only:
        want = set(a.only.split(","))
        todo = [p for p in P if p["key"] in want]
    if a.force and not a.only:
        todo = P
    if not todo:
        print("nothing to render"); return
    if not a.yes:
        sys.exit("dry run only. Re-run with --yes after the user approves the estimate.")
    (W / "_raw").mkdir(exist_ok=True); (W / "plates").mkdir(exist_ok=True)
    model = s.get("model", "seedream")
    anchor = W / "plates" / "anchor.png"
    ids = json.loads((W / "prediction_ids.json").read_text()) if (W / "prediction_ids.json").exists() else {}
    for p in todo:
        if p["key"] != "anchor" and not anchor.exists():
            sys.exit("anchor plate missing: render and approve `anchor` first (--only anchor)")
        refs = []
        for r in p["refs"]:
            refs.append(W / s["anchor"]["from_photo"] if r == "_photo" else W / "plates" / f"{r}.png")
        print(f"→ {p['key']:<22}", end="", flush=True)
        raw, pid = predict(model, p["prompt"], refs, p["aspect"], W / "_raw" / f"{p['key']}.png")
        shutil.copyfile(raw, W / "plates" / f"{p['key']}.png")
        ids[p["key"]] = pid
        print(f" ok  {raw.name}")
        if p["key"] == "anchor" and len(todo) > 1:
            print("anchor rendered. Stopping so it can be approved before the rest is built from it.")
            break
    (W / "prediction_ids.json").write_text(json.dumps(ids, indent=1))
    cmd_qc(a)


def cmd_qc(a):
    s = load(a.spec); W = workdir(a.spec)
    plates = []
    for p in plan(s):
        raw = latest_raw(W, p["key"])
        if raw and p["group"] != "anchor":
            plates.append({"key": p["key"], "group": p["group"], "raw": raw, "out": W / "plates" / f"{p['key']}.png"})
    if not plates:
        print("no plates to QC yet"); return
    rep = rs_qc.run(plates, correct=True)
    rs_qc.print_report(rep)
    (W / "qc.json").write_text(json.dumps(rep, indent=1, default=str))
    cmd_compose(a, rep)
    cmd_pack(a, rep)


def cmd_compose(a, rep=None):
    s = load(a.spec); W = workdir(a.spec)
    rep = rep or (json.loads((W / "qc.json").read_text()) if (W / "qc.json").exists() else {"regenerate": []})
    ok = {p.stem: p for p in (W / "plates").glob("*.png") if p.stem not in rep.get("regenerate", [])}
    out = rs_layout.compose(s, ok, W / "sheet.jpg")
    print(f"sheet: {out}  ({len(ok)} verified plates)")


def cmd_pack(a, rep=None):
    """The model-facing pack. The composed sheet is for humans; video models get
    individual plates, ranked, because a collage as a reference teaches a video
    model to render a collage and its labels."""
    s = load(a.spec); W = workdir(a.spec)
    rep = rep or (json.loads((W / "qc.json").read_text()) if (W / "qc.json").exists() else {"regenerate": []})
    bad = set(rep.get("regenerate", []))
    rank = ["face_front", "turn_front", "turn_side", "turn_back", "face_profile", "expr_neutral",
            "turn_three_quarter", "face_three_quarter", "pose_walking", "pose_neutral_stand"]
    pk = W / "pack"
    if pk.exists():
        shutil.rmtree(pk)
    pk.mkdir()
    have = [k for k in rank if (W / "plates" / f"{k}.png").exists() and k not in bad]
    extras = sorted(p.stem for p in (W / "plates").glob("*.png")
                    if p.stem not in have and p.stem not in bad and p.stem != "anchor"
                    and not p.stem.startswith(("material_",)))
    order = have + extras
    for i, k in enumerate(order, 1):
        shutil.copyfile(W / "plates" / f"{k}.png", pk / f"{i:02d}_{k}.png")
    man = {"character": s["name"], "slug": s["slug"], "subject_type": s["subject_type"],
           "consent": s["consent"], "identity_text": describe(s),
           "costume_canon": s.get("costume"), "palette": s.get("palette"),
           "pack_order": [f"{i:02d}_{k}.png" for i, k in enumerate(order, 1)],
           "top_refs": {"1": order[:1], "3": order[:3], "4": order[:4], "9": order[:9]},
           "sheet": "sheet.jpg", "qc_pass": rep.get("pass"), "excluded_by_qc": sorted(bad)}
    (W / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"pack: {pk}  ({len(order)} plates; top-4 = {order[:4]})")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("init"); i.add_argument("slug"); i.add_argument("--name", required=True); i.add_argument("--anchor")
    for c in ("plan", "qc", "compose", "pack"):
        sp.add_parser(c).add_argument("spec")
    r = sp.add_parser("run"); r.add_argument("spec"); r.add_argument("--only"); r.add_argument("--force", action="store_true")
    r.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    {"init": cmd_init, "plan": cmd_plan, "run": cmd_run, "qc": cmd_qc,
     "compose": cmd_compose, "pack": cmd_pack}[a.cmd](a)


if __name__ == "__main__":
    main()
