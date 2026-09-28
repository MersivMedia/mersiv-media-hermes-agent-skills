#!/usr/bin/env python3
"""Phase 4 — TTS chunked VO emitter.

Takes a `chunks.json` manifest (one entry per scene VO + one per talking-head
clip) and generates a separate `.wav`/`.mp3` per chunk via ElevenLabs TTS,
using the same `tts_chunk()` function the `revoice.py` script uses.

Each chunk filename encodes its target timestamp + identity so CapCut placement
is mechanical (drop the file at the timestamp the filename calls out).

Output naming convention (matches brand-youtube-pipeline SKILL.md):

  Scene VO:     scene-NN_[start_ss-end_ss].mp3
  Talking-head: th{N}-{section}_[start_ss-end_ss]_pose-{NN}-{action}.wav

Why both? Talking-heads need .wav so `prunaai/p-video-avatar` can ingest them
without re-decoding artifacts. Scene VO can be .mp3 to keep the per-episode
asset bundle small (audio compositing in CapCut handles MP3 fine).

Inputs (chunks.json schema):

  [
    {
      "kind": "scene",
      "scene_id": 0,
      "start": 0.0,
      "end": 44.1,
      "text": "Seven hundred and sixty million dollars..."
    },
    {
      "kind": "talking_head",
      "th_id": 1,
      "section": "cold-open",
      "start": 0.0,
      "end": 10.0,
      "pose": "08-pointing-at-camera",
      "text": "Seven hundred and sixty million dollars..."
    }
  ]

Voice locked to `TyJfVqGmT0iahaNbUE37` (Angry [brand]). Override only with
explicit `--voice-id` flag — and don't.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Reuse the proven tts_chunk implementation from revoice.py
SCRIPT_DIR = Path(__file__).resolve().parent
REVOICE_DIR = Path(os.path.expanduser(
    "~/.hermes/skills/creative/elevenlabs-narrator-revoice/scripts"
))
sys.path.insert(0, str(REVOICE_DIR))
import revoice as rv  # noqa: E402


LOCKED_VOICE_ID = "TyJfVqGmT0iahaNbUE37"  # Angry [brand] — DO NOT change.


def emit_chunk(chunk: dict, out_dir: Path, voice_id: str, model: str,
               api_key: str, voice_settings: dict | None,
               prev_request_ids: list[str]) -> tuple[Path, str | None]:
    """Render one chunk. Returns (output_path, request_id_for_chaining)."""
    kind = chunk["kind"]
    start = chunk["start"]
    end = chunk["end"]

    if kind == "scene":
        scene_id = chunk["scene_id"]
        ext = "mp3"
        of = "mp3_44100_128"
        name = f"scene-{scene_id:02d}_[{start:.2f}-{end:.2f}]"
    elif kind == "talking_head":
        th_id = chunk["th_id"]
        section = chunk["section"]
        pose = chunk["pose"]
        ext = "wav"
        of = "pcm_24000"  # uncompressed for clean lipsync ingest (wrapped in WAV/RIFF post-render)
        name = f"th{th_id}-{section}_[{start:.2f}-{end:.2f}]_pose-{pose}"
    else:
        raise ValueError(f"unknown chunk kind: {kind}")

    out_path = out_dir / f"{name}.{ext}"
    # Skip if already exists (idempotent re-runs)
    if out_path.exists() and out_path.stat().st_size > 1000:
        print(f"  [skip] {out_path.name} ({out_path.stat().st_size//1024} KB)")
        return out_path, None

    req_id = rv.tts_chunk(
        text=chunk["text"],
        voice_id=voice_id,
        model=model,
        api_key=api_key,
        previous_text=None,  # each chunk is rendered fresh; no inter-chunk context
        next_text=None,
        output_format=of,
        out_path=out_path,
        voice_settings=voice_settings,
        previous_request_ids=prev_request_ids or None,
        retries=3,
    )
    # ElevenLabs pcm_24000 returns headerless raw PCM — wrap as proper WAV
    # (RIFF header) so downstream consumers like prunaai/p-video-avatar can
    # decode. Without this the file ffprobe-reads as garbage Targa data and
    # Replicate rejects it with "Audio file could not be decoded".
    if of == "pcm_24000" and ext == "wav" and out_path.exists():
        import wave as _wave
        raw = out_path.read_bytes()
        if raw[:4] != b"RIFF":
            tmp = out_path.with_suffix(".wav.tmp")
            with _wave.open(str(tmp), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)  # 16-bit
                w.setframerate(24000)
                w.writeframes(raw)
            tmp.replace(out_path)
    return out_path, req_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True,
                    help="Path to chunks.json manifest")
    ap.add_argument("--out-dir", required=True,
                    help="Where to write chunk audio files")
    ap.add_argument("--voice-id", default=LOCKED_VOICE_ID,
                    help=f"ElevenLabs voice ID (DEFAULT + LOCKED: {LOCKED_VOICE_ID}). "
                         "DO NOT override for [brand] work — the brand is "
                         "single-narrator on this voice across the entire pipeline.")
    ap.add_argument("--model", default="eleven_multilingual_v2",
                    help="ElevenLabs model id")
    ap.add_argument("--stability", type=float, default=0.45)
    ap.add_argument("--similarity-boost", type=float, default=0.85)
    ap.add_argument("--style", type=float, default=0.30)
    ap.add_argument("--chain-request-ids", action="store_true",
                    help="Chain previous_request_ids across chunks for voice "
                         "consistency. Useful when chunks are sequential (e.g. "
                         "scene VOs read in order). Default: off for talking-heads "
                         "(they're independent clips).")
    args = ap.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("ELEVENLABS_API_KEY missing — see ~/.hermes/.env")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = json.loads(Path(args.chunks).read_text())
    print(f"Loaded {len(chunks)} chunks from {args.chunks}")
    print(f"Voice: {args.voice_id}  model: {args.model}")
    print(f"Output: {out_dir}")

    voice_settings = {
        "stability": args.stability,
        "similarity_boost": args.similarity_boost,
        "style": args.style,
    }

    prev_request_ids: list[str] = []
    results = []
    t0 = time.time()
    for i, ch in enumerate(chunks, 1):
        print(f"\n[{i}/{len(chunks)}] {ch['kind']} -> emitting...")
        try:
            path, req_id = emit_chunk(
                ch, out_dir, args.voice_id, args.model, api_key,
                voice_settings, prev_request_ids if args.chain_request_ids else [],
            )
            results.append({"chunk": ch, "out": str(path), "request_id": req_id})
            if req_id and args.chain_request_ids:
                prev_request_ids.append(req_id)
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"chunk": ch, "error": str(e)})

    # Manifest of what got built
    (out_dir / "_chunks_results.json").write_text(json.dumps(results, indent=2))
    elapsed = time.time() - t0
    print(f"\nDone. {len(chunks)} chunks in {elapsed:.1f}s ({elapsed/max(len(chunks),1):.1f}s/chunk avg)")


if __name__ == "__main__":
    main()
