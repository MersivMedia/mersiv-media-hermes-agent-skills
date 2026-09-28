#!/usr/bin/env python3
"""
Cover-song pipeline via Replicate. No local GPU required.

Routes:
  voice  - RVC voice conversion; keeps the original instrumental (default)
  style  - reference-conditioned regeneration via minimax/music-01

Run from `terminal`, not execute_code — env vars are not inherited:
    set -a; . ~/.hermes/.env; set +a
    python3 cover.py --route voice --source URL --rvc-model Drake

Always --verify first: community model versions get superseded.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

API = "https://api.replicate.com/v1"

MODELS = {
    "stems": "triadmusic/stems-separator",
    "rvc": "zsxkib/realistic-voice-cloning",
    "minimax": "minimax/music-01",
    "remixer": "sakemin/musicgen-remixer",
}


def _token() -> str:
    tok = os.environ.get("REPLICATE_API_TOKEN")
    if not tok:
        sys.exit(
            "REPLICATE_API_TOKEN not set.\n"
            "  set -a; . ~/.hermes/.env; set +a"
        )
    return tok


def _curl_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    """urllib gets 403 from Replicate (UA filtering); curl works."""
    cmd = ["curl", "-s", "--max-time", "120", "-X", method,
           "-H", f"Authorization: Bearer {_token()}",
           "-H", "Content-Type: application/json"]
    if payload is not None:
        cmd += ["-d", json.dumps(payload)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"Non-JSON response from {url}:\n{out[:400]}")


def latest_version(model: str) -> str:
    d = _curl_json(f"{API}/models/{model}")
    lv = (d.get("latest_version") or {}).get("id")
    if not lv:
        sys.exit(f"{model}: no latest_version (official model — omit the hash)")
    return lv


def verify_all() -> None:
    print("Live version hashes:\n")
    for name, model in MODELS.items():
        try:
            print(f"  {name:<9} {model}:{latest_version(model)}")
        except SystemExit as e:
            print(f"  {name:<9} {model}  -> {e}")
    print("\nPin these in any call. Community models 422 without a version.")


def run(model: str, payload: dict) -> object:
    """Create a prediction and poll to completion."""
    version = latest_version(model)
    pred = _curl_json(f"{API}/predictions", "POST",
                      {"version": version, "input": payload})
    if "id" not in pred:
        sys.exit(f"Create failed: {json.dumps(pred)[:400]}")

    import time
    url = f"{API}/predictions/{pred['id']}"
    print(f"  prediction {pred['id']} ", end="", flush=True)
    while True:
        time.sleep(5)
        p = _curl_json(url)
        status = p.get("status")
        if status in ("succeeded", "failed", "canceled"):
            print(f" {status}")
            if status != "succeeded":
                sys.exit(f"  error: {p.get('error')}")
            return p["output"]
        print(".", end="", flush=True)


def download(url: str, dest: str) -> str:
    """Replicate output URLs expire — always pull the file down."""
    subprocess.run(["curl", "-sL", "--max-time", "300", "-o", dest, url], check=True)
    size = os.path.getsize(dest)
    if size < 10_000:
        sys.exit(f"{dest} is only {size} B — download likely failed")
    print(f"  saved {dest} ({size/1_048_576:.1f} MB)")
    return dest


def get_source(source: str) -> str:
    """YouTube link -> vocals stem URL. Direct audio URL passes through."""
    if "youtube.com" not in source and "youtu.be" not in source:
        return source
    print("Separating stems from YouTube...")
    stems = run(MODELS["stems"],
                {"youtube_url": source, "format": "mp3", "model_name": "htdemucs"})
    if not isinstance(stems, dict):
        sys.exit(f"Unexpected stems output: {str(stems)[:200]}")
    # NOTE: there is no "mixture" key. Keys are bass/drums/other/piano/guitar/vocals.
    print(f"  stems: {', '.join(k for k, v in stems.items() if v)}")
    return stems


def route_voice(args) -> str:
    src = args.source
    if "youtube" in src or "youtu.be" in src:
        stems = get_source(src)
        src = stems.get("vocals") or sys.exit("no vocals stem returned")
        print("  note: RVC handles separation itself; passing the full mix is "
              "usually better than a stem")
    payload = {
        "song_input": src,
        "rvc_model": args.rvc_model,
        "pitch_change": args.pitch_change,
        "index_rate": args.index_rate,
        "protect": args.protect,
        "rms_mix_rate": 0.25,
        "pitch_detection_algorithm": "rmvpe",
        "output_format": "mp3",
    }
    if args.rvc_model == "CUSTOM":
        if not args.custom_model_url:
            sys.exit("--rvc-model CUSTOM requires --custom-model-url (.zip)")
        payload["custom_rvc_model_download_url"] = args.custom_model_url
    print("Converting vocal...")
    out = run(MODELS["rvc"], payload)
    return download(out if isinstance(out, str) else out[0], args.out)


def route_style(args) -> str:
    if not args.lyrics:
        sys.exit("--route style requires --lyrics (or --lyrics-file)")
    lyrics = args.lyrics
    if os.path.isfile(lyrics):
        lyrics = open(lyrics).read()
    print("Generating (reference-conditioned, ~1 min max output)...")
    out = run(MODELS["minimax"], {
        "lyrics": lyrics,
        "song_file": args.source,
        "sample_rate": 44100,
        "bitrate": 256000,
    })
    return download(out if isinstance(out, str) else out[0], args.out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="print live version hashes and exit")
    ap.add_argument("--route", choices=["voice", "style"], default="voice")
    ap.add_argument("--source", help="audio URL or YouTube link")
    ap.add_argument("--out", default="cover.mp3")
    ap.add_argument("--rvc-model", default="Drake",
                    help="Squidward MrKrabs Plankton Drake Vader Trump Biden "
                         "Obama Guitar Voilin CUSTOM")
    ap.add_argument("--custom-model-url", help=".zip of a trained RVC v2 model")
    ap.add_argument("--pitch-change", default="no-change",
                    choices=["no-change", "male-to-female", "female-to-male"])
    ap.add_argument("--index-rate", type=float, default=0.5)
    ap.add_argument("--protect", type=float, default=0.33)
    ap.add_argument("--lyrics", help="lyrics text or path to a file")
    args = ap.parse_args()

    if args.verify:
        verify_all()
        return
    if not args.source:
        ap.error("--source is required (or use --verify)")

    path = route_voice(args) if args.route == "voice" else route_style(args)
    print(f"\nDone: {path}")


if __name__ == "__main__":
    main()
