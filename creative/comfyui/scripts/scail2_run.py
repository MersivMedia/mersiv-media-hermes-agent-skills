#!/usr/bin/env python3
"""SCAIL-2 in-video character replacement — the node actually built for this.

Why this differs from every earlier attempt:
  * WanAnimateToVideo ANIMATES a still image from motion. WanSCAILToVideo has
    an explicit replacement_mode and REPLACES a tracked person in a video.
    Four Animate runs failed on identity (best 2.27% teal vs VACE's 10.22%)
    because it was the wrong node for the job.
  * Animate takes a plain binary character_mask. SCAIL-2 wants COLORED
    per-identity masks from SCAIL2ColoredMask, where colour encodes which
    tracked person maps to which reference. No polarity flip could bridge
    that format gap — which is why both invert directions failed.
  * pose_video here is the RAW driving video, NOT a pose skeleton. SCAIL-2
    does its own motion extraction ("no ControlNet, no DWPose, no depth").

Graph:
  source video ─┬→ pose_video (raw frames)
                ├→ RTDETR(person) → SAM3_Detect → SAM3_VideoTrack ┐
                │                                    driving_track_data
  reference img ─→ RTDETR(person) → SAM3_Detect ────→ ref_track_data (MASK)
                                                              │
                              SCAIL2ColoredMask(replacement_mode=True)
                                    ├→ pose_video_mask (white bg)
                                    └→ reference_image_mask (black bg)
                                                              │
  SCAIL model + lightx2v(step-distill) + DPO lora → WanSCAILToVideo
                          → KSampler → VAEDecode → RIFE → SaveVideo
"""

import argparse
import json
import subprocess
import sys
import time

HOST = "http://127.0.0.1:8188"


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


def build(a):
    neg = ("blurry, low quality, distorted, deformed, static, watermark, "
           "text, jpeg artifacts, extra limbs, malformed hands")

    wf = {
        # ---- inputs ----
        "1":  {"class_type": "LoadVideo", "inputs": {"file": a.source_video}},
        "2":  {"class_type": "GetVideoComponents", "inputs": {"video": ["1", 0]}},
        "3":  {"class_type": "LoadImage", "inputs": {"image": a.reference_image}},

        # ---- text / vae ----
        "4":  {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                          "type": "wan", "device": "default"}},
        "5":  {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["4", 0], "text": a.prompt}},
        "6":  {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["4", 0], "text": neg}},
        "7":  {"class_type": "VAELoader",
               "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},

        # ---- clip vision (model trained with it) ----
        "8":  {"class_type": "CLIPVisionLoader",
               "inputs": {"clip_name": "clip_vision_h.safetensors"}},
        "9":  {"class_type": "CLIPVisionEncode",
               "inputs": {"clip_vision": ["8", 0], "image": ["3", 0],
                          "crop": "none"}},

        # ---- detectors ----
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "rt_detr_v4-x-hgnet_fp16.safetensors",
                          "weight_dtype": "default"}},
        "11": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "sam3.1_multiplex_fp16.safetensors",
                          "weight_dtype": "default"}},

        # ---- SAM3 on the DRIVING video ----
        "12": {"class_type": "RTDETR_detect",
               "inputs": {"model": ["10", 0], "image": ["2", 0],
                          "threshold": a.detect_threshold,
                          "class_name": "person",
                          "max_detections": a.max_people}},
        "13": {"class_type": "SAM3_Detect",
               "inputs": {"model": ["11", 0], "image": ["2", 0],
                          "threshold": a.mask_threshold,
                          "refine_iterations": 2,
                          "individual_masks": True,
                          "bboxes": ["12", 0]}},
        "14": {"class_type": "SAM3_VideoTrack",
               "inputs": {"images": ["2", 0], "model": ["11", 0],
                          "detection_threshold": a.mask_threshold,
                          "max_objects": a.max_people,
                          "detect_interval": 5,
                          "initial_mask": ["13", 0]}},

        # ---- SAM3 on the REFERENCE image (plain MASK is accepted) ----
        "15": {"class_type": "RTDETR_detect",
               "inputs": {"model": ["10", 0], "image": ["3", 0],
                          "threshold": a.detect_threshold,
                          "class_name": "person",
                          "max_detections": 1}},
        "16": {"class_type": "SAM3_Detect",
               "inputs": {"model": ["11", 0], "image": ["3", 0],
                          "threshold": a.mask_threshold,
                          "refine_iterations": 2,
                          "individual_masks": False,
                          "bboxes": ["15", 0]}},

        # ---- the colored per-identity masks SCAIL-2 actually wants ----
        "17": {"class_type": "SCAIL2ColoredMask",
               "inputs": {"driving_track_data": ["14", 0],
                          "object_indices": a.object_indices,
                          "sort_by": a.sort_by,
                          "replacement_mode": not a.animation_mode,
                          "ref_track_data": ["16", 0]}},

        # ---- SCAIL-2 model + LoRAs ----
        "18": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "wan2.1_14B_SCAIL_2_int8_convrot.safetensors",
                          "weight_dtype": "default"}},
    }

    model_src = ["18", 0]
    nid = 19
    # lightx2v step-distill LoRA: enables low-step sampling at cfg 1.0
    if a.lightx2v_strength > 0:
        wf[str(nid)] = {"class_type": "LoraLoaderModelOnly",
                        "inputs": {"model": model_src,
                                   "lora_name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                                   "strength_model": a.lightx2v_strength}}
        model_src = [str(nid), 0]; nid += 1
    if a.dpo_strength > 0:
        wf[str(nid)] = {"class_type": "LoraLoaderModelOnly",
                        "inputs": {"model": model_src,
                                   "lora_name": "wan2.1_SCAIL_2_DPO_lora_bf16.safetensors",
                                   "strength_model": a.dpo_strength}}
        model_src = [str(nid), 0]; nid += 1
    if a.relight_strength > 0:
        wf[str(nid)] = {"class_type": "LoraLoaderModelOnly",
                        "inputs": {"model": model_src,
                                   "lora_name": "wan2.1_SCAIL_2_relight_lora_bf16.safetensors",
                                   "strength_model": a.relight_strength}}
        model_src = [str(nid), 0]; nid += 1

    wf["40"] = {"class_type": "ModelSamplingSD3",
                "inputs": {"model": model_src, "shift": a.shift}}

    wf["41"] = {"class_type": "WanSCAILToVideo",
                "inputs": {
                    "positive": ["5", 0], "negative": ["6", 0], "vae": ["7", 0],
                    "width": a.width, "height": a.height, "length": a.length,
                    "batch_size": 1,
                    "pose_strength": a.pose_strength,
                    "pose_start": 0.0, "pose_end": 1.0,
                    "video_frame_offset": 0,
                    "previous_frame_count": 5,
                    "pose_video": ["2", 0],            # RAW driving frames
                    "pose_video_mask": ["17", 0],      # colored, white bg
                    "replacement_mode": not a.animation_mode,
                    "reference_image": ["3", 0],
                    "reference_image_mask": ["17", 1], # colored, black bg
                    "clip_vision_output": ["9", 0],
                }}

    wf["42"] = {"class_type": "KSamplerAdvanced",
                "inputs": {"model": ["40", 0], "add_noise": "enable",
                           "noise_seed": a.seed, "steps": a.steps, "cfg": a.cfg,
                           "sampler_name": a.sampler, "scheduler": a.scheduler,
                           "positive": ["41", 0], "negative": ["41", 1],
                           "latent_image": ["41", 2],
                           "start_at_step": 0, "end_at_step": 10000,
                           "return_with_leftover_noise": "disable"}}
    wf["43"] = {"class_type": "VAEDecode",
                "inputs": {"samples": ["42", 0], "vae": ["7", 0]}}

    frames_src = ["43", 0]
    out_fps = float(a.fps)
    if a.rife_multiplier > 1:
        wf["44"] = {"class_type": "RIFE VFI",
                    "inputs": {"ckpt_name": "rife47.pth", "frames": ["43", 0],
                               "clear_cache_after_n_frames": 10,
                               "multiplier": a.rife_multiplier,
                               "fast_mode": True, "ensemble": True,
                               "scale_factor": 1.0, "dtype": "float32",
                               "torch_compile": False, "batch_size": 1}}
        frames_src = ["44", 0]
        out_fps = float(a.fps) * a.rife_multiplier

    wf["45"] = {"class_type": "CreateVideo",
                "inputs": {"images": frames_src, "fps": out_fps}}
    wf["46"] = {"class_type": "SaveVideo",
                "inputs": {"video": ["45", 0], "filename_prefix": a.prefix,
                           "format": "mp4", "codec": "h264"}}

    # debug: dump the colored masks so failures are diagnosable
    if a.save_masks:
        wf["50"] = {"class_type": "CreateVideo",
                    "inputs": {"images": ["17", 0], "fps": float(a.fps)}}
        wf["51"] = {"class_type": "SaveVideo",
                    "inputs": {"video": ["50", 0],
                               "filename_prefix": a.prefix + "_posemask",
                               "format": "mp4", "codec": "h264"}}
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-video", default="control_video_81f.mp4")
    ap.add_argument("--reference-image", default="reference_complex_832x480.png")
    ap.add_argument("--prompt", default=(
        "a tall woman with long copper-red braided hair wearing a bright teal "
        "weatherproof parka with reflective orange stripes, black utility "
        "trousers and yellow boots, walking forward across a concrete floor, "
        "cinematic lighting, sharp focus, detailed"))
    ap.add_argument("--width", type=int, default=832)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--length", type=int, default=81, help="SCAIL-2 trained at 81")
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--shift", type=float, default=8.0)
    ap.add_argument("--sampler", default="euler")
    ap.add_argument("--scheduler", default="simple")
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--pose-strength", type=float, default=1.0)
    ap.add_argument("--lightx2v-strength", type=float, default=1.0)
    ap.add_argument("--dpo-strength", type=float, default=1.0)
    ap.add_argument("--relight-strength", type=float, default=0.0)
    ap.add_argument("--object-indices", default="",
                    help="which tracked people, e.g. '0,2'. Empty = all")
    ap.add_argument("--sort-by", default="left_to_right",
                    choices=["left_to_right", "area", "none"])
    ap.add_argument("--max-people", type=int, default=1)
    ap.add_argument("--detect-threshold", type=float, default=0.4)
    ap.add_argument("--mask-threshold", type=float, default=0.4)
    ap.add_argument("--animation-mode", action="store_true",
                    help="animate the reference instead of replacing in-video")
    ap.add_argument("--rife-multiplier", type=int, default=2)
    ap.add_argument("--save-masks", action="store_true", default=True)
    ap.add_argument("--prefix", default="scail2")
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--save-only")
    a = ap.parse_args()

    wf = build(a)
    if a.save_only:
        with open(a.save_only, "w") as f:
            json.dump(wf, f, indent=2)
        print(f"wrote {a.save_only} ({len(wf)} nodes)")
        return

    st, body = http("POST", f"{HOST}/prompt", {"prompt": wf})
    if st != 200 or not isinstance(body, dict):
        print(f"SUBMIT FAILED HTTP {st}: {str(body)[:2500]}", file=sys.stderr)
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
