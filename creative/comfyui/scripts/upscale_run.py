#!/usr/bin/env python3
"""Standalone upscaler — run on approved clips, independent of generation.

Two engines:
  esrgan  (default for images, fast)  frame-by-frame ESRGAN-family model.
          No temporal awareness: fine for stills, can shimmer on video.
  seedvr2 (for video)                 diffusion upscaler with temporal
          chunk/merge, so neighbouring frames stay consistent. Slower and
          VRAM-hungry but the right tool for a moving subject.

Deliberately a separate script from the generation pipelines so an upscale
never costs compute on a test render, and so approved clips can be batched.

  python3 upscale_run.py --input clip.mp4 --engine seedvr2
  python3 upscale_run.py --input still.png --engine esrgan --model 4x-UltraSharp.pth
  python3 upscale_run.py --input clip.mp4 --engine esrgan --scale-after 0.5
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HOST = "http://127.0.0.1:8188"
COMFY_IN = Path("/workspace/ComfyUI/input")
COMFY_OUT = Path("/workspace/ComfyUI/output")
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def http(method, url, payload=None, timeout=120):
    cmd = ["curl", "-sS", "-X", method, url,
           "-H", "Content-Type: application/json",
           "-w", "\n__S__%{http_code}", "--max-time", str(timeout)]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return 0, f"curl: {r.stderr.strip()}"
    body, _, st = r.stdout.rpartition("\n__S__")
    try:
        return int(st), json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return int(st or 0), body


def probe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
         "-of", "json", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        st = json.loads(r.stdout)["streams"][0]
        num, _, den = st.get("r_frame_rate", "16/1").partition("/")
        return {"width": st.get("width"), "height": st.get("height"),
                "frames": int(st.get("nb_read_frames") or 1),
                "fps": round(float(num) / float(den or 1), 2)}
    except (KeyError, IndexError, ValueError, ZeroDivisionError):
        return None


def build_esrgan(a, is_video, fps):
    """Frame-by-frame ESRGAN. Works for stills and video alike."""
    wf = {}
    if is_video:
        wf["1"] = {"class_type": "LoadVideo", "inputs": {"file": a.staged_name}}
        wf["2"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}}
        src = ["2", 0]
    else:
        wf["1"] = {"class_type": "LoadImage", "inputs": {"image": a.staged_name}}
        src = ["1", 0]

    wf["10"] = {"class_type": "UpscaleModelLoader",
                "inputs": {"model_name": a.model}}
    wf["11"] = {"class_type": "ImageUpscaleWithModel",
                "inputs": {"upscale_model": ["10", 0], "image": src}}
    out = ["11", 0]

    # ESRGAN models have a fixed factor (usually 4x). scale_after lets you
    # land on an arbitrary target, e.g. 4x then 0.5 == net 2x.
    if a.scale_after != 1.0:
        wf["12"] = {"class_type": "ImageScaleBy",
                    "inputs": {"image": out, "upscale_method": "lanczos",
                               "scale_by": a.scale_after}}
        out = ["12", 0]

    if is_video:
        wf["20"] = {"class_type": "CreateVideo",
                    "inputs": {"images": out, "fps": float(fps)}}
        wf["21"] = {"class_type": "SaveVideo",
                    "inputs": {"video": ["20", 0], "filename_prefix": a.prefix,
                               "format": "mp4", "codec": "h264"}}
    else:
        wf["20"] = {"class_type": "SaveImage",
                    "inputs": {"images": out, "filename_prefix": a.prefix}}
    return wf


def build_seedvr2(a, fps, info):
    """Temporal diffusion upscale. Video only."""
    tw = int(info["width"] * a.scale)
    th = int(info["height"] * a.scale)
    tw -= tw % 16
    th -= th % 16

    wf = {
        "1": {"class_type": "LoadVideo", "inputs": {"file": a.staged_name}},
        "2": {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        # SeedVR2 expects the frames pre-resized to the TARGET size, then
        # refines detail at that resolution.
        "3": {"class_type": "ImageScale",
              "inputs": {"image": ["2", 0], "upscale_method": "lanczos",
                         "width": tw, "height": th, "crop": "disabled"}},
        "4": {"class_type": "SeedVR2Preprocess",
              "inputs": {"resized_images": ["3", 0]}},
        "5": {"class_type": "UNETLoader",
              "inputs": {"unet_name": a.seedvr_model, "weight_dtype": "default"}},
        "6": {"class_type": "VAELoader",
              "inputs": {"vae_name": "seedvr2_ema_vae_fp16.safetensors"}},
        "7": {"class_type": "VAEEncode",
              "inputs": {"pixels": ["4", 0], "vae": ["6", 0]}},
        # Chunk FIRST, then build conditioning from the chunked latent.
        # Doing it the other way round gives the sampler full-length
        # conditioning against chunked latents:
        #   "SeedVR2 conditioning shape must match latent batch/temporal/
        #    spatial dimensions; got latent (1,16,37,...) and
        #    conditioning (1,17,41,...)"
        "9": {"class_type": "SeedVR2TemporalChunk",
              "inputs": {"latent": ["7", 0],
                         "temporal_overlap": a.temporal_overlap,
                         "chunking_mode": "auto"}},
        "8": {"class_type": "SeedVR2Conditioning",
              "inputs": {"model": ["5", 0], "vae_conditioning": ["9", 0]}},
        "10": {"class_type": "KSamplerAdvanced",
               "inputs": {"model": ["5", 0], "add_noise": "enable",
                          "noise_seed": a.seed, "steps": a.steps, "cfg": 1.0,
                          "sampler_name": "euler", "scheduler": "simple",
                          "positive": ["8", 0], "negative": ["8", 1],
                          "latent_image": ["9", 0],
                          "start_at_step": 0, "end_at_step": 10000,
                          "return_with_leftover_noise": "disable"}},
        "11": {"class_type": "SeedVR2TemporalMerge",
               "inputs": {"latents": ["10", 0], "temporal_overlap": ["9", 1]}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["6", 0]}},
        # match colours back to the source so the upscale doesn't drift
        "13": {"class_type": "SeedVR2PostProcessing",
               "inputs": {"images": ["12", 0],
                          "original_resized_images": ["3", 0],
                          "color_correction_method": a.color_correction}},
        "20": {"class_type": "CreateVideo",
               "inputs": {"images": ["13", 0], "fps": float(fps)}},
        "21": {"class_type": "SaveVideo",
               "inputs": {"video": ["20", 0], "filename_prefix": a.prefix,
                          "format": "mp4", "codec": "h264"}},
    }
    return wf


def main():
    ap = argparse.ArgumentParser(description="Standalone image/video upscaler")
    ap.add_argument("--input", required=True,
                    help="path on the POD (or a bare filename already in input/)")
    ap.add_argument("--engine", default="auto",
                    choices=["auto", "esrgan", "seedvr2"])
    ap.add_argument("--model", default="4x-UltraSharp.pth",
                    help="ESRGAN model name")
    ap.add_argument("--seedvr-model",
                    default="seedvr2_7b_sharp_int8_convrot.safetensors")
    ap.add_argument("--scale", type=float, default=2.0,
                    help="seedvr2 target multiplier")
    ap.add_argument("--scale-after", type=float, default=1.0,
                    help="esrgan: resize after the fixed-factor model")
    ap.add_argument("--steps", type=int, default=6)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--temporal-overlap", type=int, default=2)
    ap.add_argument("--color-correction", default="lab")
    ap.add_argument("--prefix", default="upscaled")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--save-only")
    a = ap.parse_args()

    src = Path(a.input)
    if src.is_absolute() or src.exists():
        if not src.exists():
            print(f"ERROR: not found: {src}", file=sys.stderr); sys.exit(1)
        staged = COMFY_IN / src.name
        if not staged.exists() or staged.stat().st_size != src.stat().st_size:
            COMFY_IN.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", str(src), str(staged)], check=True)
        probe_path = staged
    else:
        staged = COMFY_IN / src.name
        if not staged.exists():
            print(f"ERROR: {src.name} not in {COMFY_IN}", file=sys.stderr); sys.exit(1)
        probe_path = staged
    a.staged_name = staged.name

    is_video = staged.suffix.lower() in VIDEO_EXT
    info = probe(probe_path) or {"width": 0, "height": 0, "frames": 1, "fps": 16}
    fps = info["fps"] if is_video else 16

    engine = a.engine
    if engine == "auto":
        engine = "seedvr2" if is_video else "esrgan"
    if engine == "seedvr2" and not is_video:
        print("seedvr2 is video-only; falling back to esrgan", file=sys.stderr)
        engine = "esrgan"

    print(f"input : {staged.name}  {info['width']}x{info['height']} "
          f"{info['frames']}f @{fps}")
    print(f"engine: {engine}")
    if engine == "seedvr2":
        print(f"target: ~{int(info['width']*a.scale)}x{int(info['height']*a.scale)}")

    wf = (build_seedvr2(a, fps, info) if engine == "seedvr2"
          else build_esrgan(a, is_video, fps))

    if a.save_only:
        Path(a.save_only).write_text(json.dumps(wf, indent=2))
        print(f"wrote {a.save_only} ({len(wf)} nodes)")
        return

    st, body = http("POST", f"{HOST}/prompt", {"prompt": wf})
    if st != 200 or not isinstance(body, dict):
        print(f"SUBMIT FAILED HTTP {st}: {str(body)[:2000]}", file=sys.stderr)
        sys.exit(1)
    pid = body.get("prompt_id")
    print(f"prompt_id: {pid}", flush=True)

    t0 = time.time()
    while time.time() < t0 + a.timeout:
        time.sleep(10)
        st, hist = http("GET", f"{HOST}/history/{pid}")
        if st == 200 and isinstance(hist, dict) and pid in hist:
            e = hist[pid]
            status = (e.get("status") or {}).get("status_str")
            print(f"status: {status} ({round(time.time()-t0)}s)")
            if status == "error":
                for m in (e.get("status") or {}).get("messages", []):
                    print("  ", json.dumps(m)[:900])
                sys.exit(2)
            outs = [it for nd in (e.get("outputs") or {}).values()
                    for k in ("videos", "gifs", "images")
                    for it in (nd.get(k) or [])]
            print(json.dumps({"prompt_id": pid,
                              "seconds": round(time.time()-t0),
                              "outputs": outs}, indent=2))
            return
        el = round(time.time() - t0)
        if el % 60 < 11:
            print(f"  running… {el}s", flush=True)
    print("TIMEOUT", file=sys.stderr)
    sys.exit(3)


if __name__ == "__main__":
    main()
