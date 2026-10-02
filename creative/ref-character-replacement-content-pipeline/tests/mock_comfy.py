#!/usr/bin/env python3
"""Mock ComfyUI for offline tests of the refswap pod scripts.

Serves /object_info (schemas for every node type in the refswap workflow +
upscale graph, including the V3 nested SaveVideo dropdown), accepts /prompt,
validates required inputs against the schema the way ComfyUI does, "executes"
by writing a real tiny mp4 via ffmpeg, and reports /history with
execution_start/success timestamps and /queue. Websocket is not mocked, so
clients exercise their HTTP-polling fallback.

  python3 mock_comfy.py <port> <comfy_root>
"""
import json
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT, ROOT = int(sys.argv[1]), Path(sys.argv[2])
S = lambda *a, **k: [a[0], k] if k else [a[0]]  # noqa: E731
W = {"INT": S("INT"), "FLOAT": S("FLOAT"), "STRING": S("STRING"), "BOOL": S("BOOLEAN")}
codec = S("COMFY_DYNAMICCOMBO_V3", options=[{"key": "auto", "inputs": {"required": {}}},
                                             {"key": "h264", "inputs": {"required": {}}}])
SCHEMA = {
    "UNETLoader": {"required": {"unet_name": [[]], "weight_dtype": [[]]}},
    "CLIPLoader": {"required": {"clip_name": [[]], "type": [[]], "device": [[]]}},
    "VAELoader": {"required": {"vae_name": [[]]}},
    "LoraLoaderModelOnly": {"required": {"model": S("MODEL"), "lora_name": [[]], "strength_model": W["FLOAT"]}},
    "ComfySwitchNode": {"required": {"switch": W["BOOL"], "on_false": S("*"), "on_true": S("*")}},
    "PrimitiveBoolean": {"required": {"value": W["BOOL"]}},
    "PrimitiveInt": {"required": {"value": W["INT"]}},
    "PrimitiveFloat": {"required": {"value": W["FLOAT"]}},
    "PrimitiveStringMultiline": {"required": {"value": W["STRING"]}},
    "ComfyMathExpression": {"required": {"expression": W["STRING"]}, "optional": {"a": S("*"), "b": S("*"), "c": S("*")}},
    "ResolutionSelector": {"required": {"aspect_ratio": [[]], "megapixels": W["FLOAT"], "multiple": W["INT"]}},
    "VHS_LoadVideo": {"required": {"video": [[]], "force_rate": W["FLOAT"], "custom_width": W["INT"],
                                   "custom_height": W["INT"], "frame_load_cap": W["INT"],
                                   "skip_first_frames": W["INT"], "select_every_nth": W["INT"]},
                      "optional": {"meta_batch": S("VHS_BatchManager"), "vae": S("VAE"), "format": [[]]}},
    "LoadImage": {"required": {"image": [[]]}},
    "ImageFromBatch": {"required": {"image": S("IMAGE"), "batch_index": W["INT"], "length": W["INT"]}},
    "CheckpointLoaderSimple": {"required": {"ckpt_name": [[]]}},
    "CLIPTextEncode": {"required": {"text": W["STRING"], "clip": S("CLIP")}},
    "SAM3_Detect": {"required": {"model": S("MODEL"), "image": S("IMAGE"), "threshold": W["FLOAT"],
                                 "refine_iterations": W["INT"], "individual_masks": W["BOOL"]},
                    "optional": {"conditioning": S("CONDITIONING"), "bboxes": S("BOUNDING_BOX"),
                                 "positive_coords": W["STRING"], "negative_coords": W["STRING"]}},
    "GrowMask": {"required": {"mask": S("MASK"), "expand": W["INT"], "tapered_corners": W["BOOL"]}},
    "GetImageSize": {"required": {"image": S("IMAGE")}},
    "EmptyImage": {"required": {"width": W["INT"], "height": W["INT"], "batch_size": W["INT"], "color": W["INT"]}},
    "ImageCompositeMasked": {"required": {"destination": S("IMAGE"), "source": S("IMAGE"), "x": W["INT"],
                                          "y": W["INT"], "resize_source": W["BOOL"]}, "optional": {"mask": S("MASK")}},
    "H3PromptDirector": {"required": {"source_video": S("IMAGE"), "character_image": S("IMAGE"),
                                      "instruction": W["STRING"], "replace_background": W["BOOL"],
                                      "duration_seconds": W["FLOAT"], "frames_to_analyse": W["INT"],
                                      "model": W["STRING"]}, "optional": {"manual_override": W["STRING"]}},
    "H3AudioRoute": {"required": {"mode": [["source", "generated", "off"]]},
                     "optional": {"generated_audio": S("AUDIO"), "source_audio": S("AUDIO")}},
    "PreviewAny": {"required": {"source": S("*")}},
    "MiniMaxH3ReferenceToVideo": {"required": {"clip": S("CLIP"), "vae": S("VAE"), "prompt": W["STRING"],
                                               "width": W["INT"], "height": W["INT"], "length": W["INT"],
                                               "ref_image_size": [["match", "max"]]},
                                  "optional": {"audio_vae": S("VAE")}},
    "RandomNoise": {"required": {"noise_seed": W["INT"]}},
    "KSamplerSelect": {"required": {"sampler_name": [[]]}},
    "BasicScheduler": {"required": {"model": S("MODEL"), "scheduler": [[]], "steps": W["INT"], "denoise": W["FLOAT"]}},
    "BasicGuider": {"required": {"model": S("MODEL"), "conditioning": S("CONDITIONING")}},
    "CFGGuider": {"required": {"model": S("MODEL"), "positive": S("CONDITIONING"), "negative": S("CONDITIONING"), "cfg": W["FLOAT"]}},
    "SamplerCustomAdvanced": {"required": {"noise": S("NOISE"), "guider": S("GUIDER"), "sampler": S("SAMPLER"),
                                           "sigmas": S("SIGMAS"), "latent_image": S("LATENT")}},
    "VAEDecode": {"required": {"samples": S("LATENT"), "vae": S("VAE")}},
    "VAEDecodeAudio": {"required": {"samples": S("LATENT"), "vae": S("VAE")}},
    "CreateVideo": {"required": {"images": S("IMAGE"), "fps": W["FLOAT"]},
                    "optional": {"audio": S("AUDIO"), "bit_depth": [[]], "color_space": [[]], "codec": [[]]}},
    "SaveVideo": {"required": {"video": S("VIDEO"), "filename_prefix": W["STRING"],
                               "format": S("COMFY_DYNAMICCOMBO_V3", options=[
                                   {"key": k, "inputs": {"required": {"codec": codec}}} for k in ("auto", "mp4", "mkv")])},
                  "optional": {"codec": codec}},
    # upscale graph
    "LoadVideo": {"required": {"file": [[]]}},
    "GetVideoComponents": {"required": {"video": S("VIDEO")}},
    "ImageScale": {"required": {"image": S("IMAGE"), "upscale_method": [[]], "width": W["INT"], "height": W["INT"], "crop": [[]]}},
    "SeedVR2Preprocess": {"required": {"resized_images": S("IMAGE")}},
    "VAEEncode": {"required": {"pixels": S("IMAGE"), "vae": S("VAE")}},
    "SeedVR2TemporalChunk": {"required": {"latent": S("LATENT"), "temporal_overlap": W["INT"], "chunking_mode": [[]]}},
    "SeedVR2Conditioning": {"required": {"model": S("MODEL"), "vae_conditioning": S("LATENT")}},
    "KSamplerAdvanced": {"required": {"model": S("MODEL")}},
    "SeedVR2TemporalMerge": {"required": {"latents": S("LATENT"), "temporal_overlap": S("INT")}},
    "SeedVR2PostProcessing": {"required": {"images": S("IMAGE"), "original_resized_images": S("IMAGE"),
                                           "color_correction_method": [[]]}},
}
INFO = {k: {"input": v, "output": [], "name": k} for k, v in SCHEMA.items()}
HIST, QUEUE, LOCK = {}, [], threading.Lock()
LOG = []   # every accepted prompt, for assertions


def validate(api):
    errs = []
    for nid, n in api.items():
        spec = SCHEMA.get(n["class_type"])
        if spec is None:
            errs.append(f"{nid}: unknown {n['class_type']}")
            continue
        for name in spec.get("required", {}):
            if name not in n["inputs"]:
                errs.append(f"{nid} {n['class_type']}: missing required '{name}'")
        for k, v in n["inputs"].items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in api:
                errs.append(f"{nid}.{k}: link to missing node {v[0]}")
    return errs


def execute(pid, api):
    time.sleep(0.5)
    t0 = time.time() * 1000
    saves = [n for n in api.values() if n["class_type"] == "SaveVideo"]
    outs = {}
    for i, n in enumerate(saves):
        prefix = n["inputs"]["filename_prefix"]
        sub, _, stem = prefix.rpartition("/")
        d = ROOT / "output" / sub
        d.mkdir(parents=True, exist_ok=True)
        fn = f"{stem}_00001_.mp4"
        # size: H3 width/height if present, else upscale ImageScale target
        w = h = None
        for m in api.values():
            if m["class_type"] == "MiniMaxH3ReferenceToVideo":
                w, h = m["inputs"]["width"], m["inputs"]["height"]
            if m["class_type"] == "ImageScale":
                w, h = m["inputs"]["width"], m["inputs"]["height"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={w or 320}x{h or 240}:r=24:d=1",
                        "-pix_fmt", "yuv420p", str(d / fn)], check=True)
        outs[str(i)] = {"videos": [{"filename": fn, "subfolder": sub, "type": "output"}]}
    # Real ComfyUI also lists the LOADED video in history outputs, typed "input"
    # (a load-node preview), after the SaveVideo entry. Taking vids[-1] without
    # checking type picked the input and crashed the upscale lane on 2026-09-28.
    for n in api.values():
        src = n["inputs"].get("file") if n["class_type"] == "LoadVideo" else \
              n["inputs"].get("video") if n["class_type"] == "VHS_LoadVideo" else None
        if isinstance(src, str):
            outs["zz_input_preview"] = {"videos": [{"filename": src, "subfolder": "", "type": "input"}]}
    for n in api.values():
        if n["class_type"] == "PreviewAny":
            outs["p"] = {"text": ["subject_definitions: mock\nretention_analysis: mock"]}
    t1 = time.time() * 1000
    with LOCK:
        HIST[pid] = {"status": {"status_str": "success", "completed": True, "messages": [
            ["execution_start", {"prompt_id": pid, "timestamp": t0}],
            ["execution_success", {"prompt_id": pid, "timestamp": t1}]]}, "outputs": outs}
        QUEUE.remove(pid)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/object_info":
            return self.send(200, INFO)
        if p.startswith("/object_info/"):
            k = p.rsplit("/", 1)[1]
            return self.send(200, {k: INFO[k]} if k in INFO else {})
        if p == "/system_stats":
            return self.send(200, {"ok": True})
        if p == "/queue":
            with LOCK:
                return self.send(200, {"queue_running": [[0, x] for x in QUEUE[:1]],
                                       "queue_pending": [[0, x] for x in QUEUE[1:]]})
        if p.startswith("/history/"):
            pid = p.rsplit("/", 1)[1]
            with LOCK:
                return self.send(200, {pid: HIST[pid]} if pid in HIST else {})
        if p == "/_log":
            return self.send(200, LOG)
        self.send(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/prompt":
            api = body["prompt"]
            errs = validate(api)
            if errs:
                return self.send(400, {"error": "prompt_outputs_failed_validation", "details": errs})
            pid = str(uuid.uuid4())
            with LOCK:
                QUEUE.append(pid); LOG.append(api)
            threading.Thread(target=execute, args=(pid, api), daemon=True).start()
            return self.send(200, {"prompt_id": pid})
        self.send(404, {})


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
