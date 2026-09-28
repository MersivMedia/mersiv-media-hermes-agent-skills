#!/usr/bin/env python3
"""
STT → TTS re-narration pipeline.

1. Extract audio from input video
2. Transcribe with Replicate WhisperX
3. Re-synthesize with ElevenLabs TTS
4. Mux new audio over original video

Usage:
    revoice.py INPUT OUTPUT --voice-id VOICE_ID [options]
    revoice.py INPUT OUTPUT --voice narrator-alt  # uses shortcut from voice-changer skill
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

EL_API_BASE = "https://api.elevenlabs.io/v1"
REPLICATE_API = "https://api.replicate.com/v1"
WHISPERX_MODEL = "victor-upmeet/whisperx"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_MAX_CHARS = 2000  # sweet spot: long enough for stable voice, short enough to avoid drift

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    if capture:
        return subprocess.run(cmd, check=check, capture_output=True, text=True)
    return subprocess.run(cmd, check=check)


def probe_duration(path: Path) -> float:
    out = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture=True,
    ).stdout.strip()
    return float(out)


def has_video_stream(path: Path) -> bool:
    if path.suffix.lower() in AUDIO_EXTS:
        return False
    out = run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture=True, check=False,
    ).stdout.strip()
    return out == "video"


def extract_audio(input_path: Path, out_path: Path) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(input_path), "-vn",
           "-ac", "1", "-ar", "44100", "-b:a", "128k", str(out_path)]
    log(f"Extracting audio → {out_path.name}")
    run(cmd, capture=True)


def upload_to_tmpfiles(audio_path: Path) -> str:
    """Upload audio to tmpfiles.org (free anonymous file host with public URLs)."""
    log("Uploading audio to tmpfiles.org...")
    with open(audio_path, "rb") as fh:
        r = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": fh}, timeout=120)
    r.raise_for_status()
    data = r.json()
    # API returns {"status":"success","data":{"url":"https://tmpfiles.org/12345/foo.mp3"}}
    url = data["data"]["url"]
    # Convert preview URL to direct download URL
    # https://tmpfiles.org/12345/foo.mp3 → https://tmpfiles.org/dl/12345/foo.mp3
    direct = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    log(f"  uploaded: {direct}")
    return direct


def get_model_version(owner_name: str, api_token: str) -> str:
    """Fetch the latest version ID for a Replicate model."""
    headers = {"Authorization": f"Token {api_token}"}
    r = requests.get(f"{REPLICATE_API}/models/{owner_name}", headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["latest_version"]["id"]


def transcribe_whisperx(audio_url: str, api_token: str,
                       language: str | None = None) -> dict:
    """POST to Replicate WhisperX. Returns the full output (segments + word timestamps)."""
    headers = {"Authorization": f"Token {api_token}", "Content-Type": "application/json"}
    log("Resolving WhisperX latest version...")
    version = get_model_version(WHISPERX_MODEL, api_token)
    log(f"  version: {version[:16]}...")

    payload = {
        "version": version,
        "input": {
            "audio_file": audio_url,
            "diarization": False,  # single narrator
            "batch_size": 32,
        }
    }
    if language:
        payload["input"]["language"] = language

    log(f"Starting WhisperX transcription...")
    r = requests.post(
        f"{REPLICATE_API}/predictions",
        headers=headers, json=payload, timeout=120,
    )
    if r.status_code != 201:
        raise RuntimeError(f"Replicate create failed: HTTP {r.status_code} {r.text[:500]}")
    prediction = r.json()
    pred_id = prediction["id"]
    log(f"  prediction id: {pred_id}")

    # Poll
    t0 = time.time()
    while True:
        time.sleep(3)
        r = requests.get(f"{REPLICATE_API}/predictions/{pred_id}", headers=headers, timeout=60)
        r.raise_for_status()
        prediction = r.json()
        status = prediction["status"]
        elapsed = time.time() - t0
        if status in ("succeeded", "failed", "canceled"):
            log(f"  {status} after {elapsed:.1f}s")
            break
        log(f"  {status}... ({elapsed:.1f}s)")

    if prediction["status"] != "succeeded":
        raise RuntimeError(f"WhisperX failed: {prediction.get('error') or prediction}")
    return prediction["output"]


def segments_to_text(segments: list[dict]) -> str:
    """Concatenate WhisperX segments into clean text."""
    parts = []
    for s in segments:
        t = s.get("text", "").strip()
        if t:
            parts.append(t)
    return " ".join(parts)


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into balanced chunks of approximately max_chars, on sentence boundaries.

    Treats max_chars as a TARGET (not hard ceiling) so we don't strand tiny chunks.
    For 6089 chars with target=2000 we get 3 chunks of ~2030, not 4 chunks (3×2000 + 89).
    Hard cap is target × 1.2 to prevent runaway chunks.
    """
    if len(text) <= max_chars:
        return [text]

    n_chunks = max(1, round(len(text) / max_chars))
    target = len(text) / n_chunks  # ideal chunk size
    hard_cap = int(max_chars * 1.2)  # absolute upper bound per chunk

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if not cur:
            cur = s
            continue
        candidate = cur + " " + s
        # Hard cap — never exceed
        if len(candidate) > hard_cap:
            chunks.append(cur)
            cur = s
            continue
        # If we've hit target AND there's enough remaining for another chunk, split
        remaining_after_cur = len(text) - sum(len(c) for c in chunks) - len(cur)
        if len(cur) >= target and remaining_after_cur >= target * 0.5 and len(chunks) < n_chunks - 1:
            chunks.append(cur)
            cur = s
        else:
            cur = candidate
    if cur:
        chunks.append(cur)

    # Edge case: a single sentence longer than hard_cap — hard cut
    final = []
    for c in chunks:
        if len(c) <= hard_cap:
            final.append(c)
        else:
            for i in range(0, len(c), hard_cap):
                final.append(c[i:i+hard_cap])
    return final


def tts_chunk(text: str, voice_id: str, model: str, api_key: str,
              previous_text: str | None, next_text: str | None,
              output_format: str, out_path: Path,
              voice_settings: dict | None = None,
              previous_request_ids: list[str] | None = None,
              retries: int = 3) -> str | None:
    """Generate one TTS chunk. Returns the request_id (from response header) for chaining."""
    url = f"{EL_API_BASE}/text-to-speech/{voice_id}?output_format={output_format}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": model,
    }
    if previous_text:
        payload["previous_text"] = previous_text[-2000:]  # API caps at 2k chars
    if next_text:
        payload["next_text"] = next_text[:2000]
    if previous_request_ids:
        # API allows up to 3 chained request IDs
        payload["previous_request_ids"] = previous_request_ids[-3:]
    if voice_settings:
        payload["voice_settings"] = voice_settings

    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            r = requests.post(url, headers=headers, json=payload, timeout=600)
            if r.status_code == 200:
                out_path.write_bytes(r.content)
                # request_id comes back in the response header (case-insensitive)
                req_id = r.headers.get("request-id") or r.headers.get("Request-Id") or \
                         r.headers.get("x-request-id")
                log(f"  ✓ {out_path.name} ({len(r.content)/1024:.0f} KB, {time.time()-t0:.1f}s)" +
                    (f" req_id={req_id[:12]}..." if req_id else ""))
                return req_id
            log(f"  ✗ attempt {attempt} HTTP {r.status_code}: {r.text[:300]}")
            if r.status_code in (401, 403, 422):
                raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:500]}")
        except requests.RequestException as e:
            log(f"  ✗ attempt {attempt} network error: {e}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"TTS failed after {retries} attempts")


def concat_mp3s(chunks: list[Path], out_path: Path, workdir: Path) -> None:
    if len(chunks) == 1:
        shutil.copy(chunks[0], out_path)
        return
    list_file = workdir / "concat.txt"
    list_file.write_text("\n".join(f"file '{c.resolve()}'" for c in chunks) + "\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c:a", "libmp3lame", "-b:a", "128k", "-ac", "1", "-ar", "44100", str(out_path)],
        capture=True)


def mux_audio_over_video(video_path: Path, audio_path: Path, out_path: Path,
                         video_dur: float, audio_dur: float,
                         stretch_video: bool = False) -> None:
    """Mux new audio over video.
    - If stretch_video=True: slow/speed video frames so duration matches audio exactly (re-encodes).
    - Else: pad with silence if audio shorter, or extend video freeze-frame if audio longer.
    """
    if abs(video_dur - audio_dur) < 0.5:
        # Lengths match; simple mux
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-shortest", str(out_path)]
    elif stretch_video:
        # Stretch every scene proportionally so total video duration = audio duration
        ratio = audio_dur / video_dur
        log(f"Stretching video by {ratio:.4f}x to match audio ({video_dur:.1f}s → {audio_dur:.1f}s)")
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
               "-filter_complex", f"[0:v]setpts={ratio:.6f}*PTS[v]",
               "-map", "[v]", "-map", "1:a:0",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest", str(out_path)]
    elif audio_dur < video_dur:
        # Pad audio with silence at end
        log(f"Audio ({audio_dur:.1f}s) < video ({video_dur:.1f}s) — padding audio with silence")
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
               "-map", "0:v:0", "-map", "1:a:0",
               "-filter:a", f"apad=whole_dur={video_dur}",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-t", str(video_dur), str(out_path)]
    else:
        # Audio longer — extend video by freezing last frame
        log(f"Audio ({audio_dur:.1f}s) > video ({video_dur:.1f}s) — extending video freeze-frame")
        cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
               "-map", "0:v:0", "-map", "1:a:0",
               "-filter:v", f"tpad=stop_mode=clone:stop_duration={audio_dur - video_dur}",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18",
               "-c:a", "aac", "-b:a", "192k",
               "-t", str(audio_dur), str(out_path)]
    log(f"Muxing → {out_path.name}")
    run(cmd, capture=True)


def resolve_voice(args) -> str:
    if args.voice_id:
        return args.voice_id
    if args.voice:
        # Look in elevenlabs-voice-changer skill's voices.json
        voices_json = Path.home() / ".hermes" / "skills" / "creative" / \
                      "elevenlabs-voice-changer" / "scripts" / "voices.json"
        if not voices_json.exists():
            raise SystemExit(f"voices.json not found: {voices_json}")
        data = json.loads(voices_json.read_text())
        if args.voice not in data:
            raise SystemExit(f"unknown voice shortcut '{args.voice}'. Known: {', '.join(data.keys())}")
        return data[args.voice]["voice_id"]
    raise SystemExit("must provide --voice-id or --voice")


def main():
    ap = argparse.ArgumentParser(description="STT→TTS re-narration via WhisperX + ElevenLabs")
    ap.add_argument("input", type=Path, help="Input video or audio file")
    ap.add_argument("output", type=Path, help="Output file path")
    ap.add_argument("--voice-id", help="ElevenLabs voice ID")
    ap.add_argument("--voice", help="Voice shortcut from voice-changer skill's voices.json")
    ap.add_argument("--model", default=DEFAULT_TTS_MODEL,
                    help=f"ElevenLabs TTS model (default: {DEFAULT_TTS_MODEL})")
    ap.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT,
                    help=f"TTS output format (default: {DEFAULT_OUTPUT_FORMAT})")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                    help=f"Max chars per TTS request (default: {DEFAULT_MAX_CHARS})")
    ap.add_argument("--language", help="ISO language code hint for WhisperX (e.g. 'en')")
    ap.add_argument("--audio-url",
                    help="Pre-uploaded audio URL to skip tmpfiles.org. Must be publicly fetchable.")
    ap.add_argument("--transcript", type=Path,
                    help="Where to save the transcript JSON (default: alongside output)")
    ap.add_argument("--text-override", type=Path,
                    help="Skip STT entirely, use this text file instead. Useful for correcting STT errors.")
    ap.add_argument("--stability", type=float, default=None,
                    help="voice_settings.stability 0-1")
    ap.add_argument("--similarity-boost", type=float, default=None,
                    help="voice_settings.similarity_boost 0-1")
    ap.add_argument("--style", type=float, default=None,
                    help="voice_settings.style 0-1")
    ap.add_argument("--stretch-video", action="store_true",
                    help="If new audio length differs from video length, stretch all scenes "
                         "proportionally to match (no audio speed change). Re-encodes video.")
    ap.add_argument("--use-studio", action="store_true",
                    help="Use ElevenLabs Studio API (long-form, single coherent take) instead of "
                         "chunked TTS. Recommended for narration over 1-2 min. Much better voice "
                         "consistency since the entire script renders as one project.")
    ap.add_argument("--workdir", type=Path, help="Working directory (default: tempdir)")
    ap.add_argument("--keep-workdir", action="store_true", help="Don't delete workdir on success")
    args = ap.parse_args()

    el_key = os.environ.get("ELEVENLABS_API_KEY")
    if not el_key:
        raise SystemExit("ELEVENLABS_API_KEY not set")
    rep_token = os.environ.get("REPLICATE_API_TOKEN")
    if not rep_token and not args.text_override:
        raise SystemExit("REPLICATE_API_TOKEN not set (or pass --text-override to skip STT)")

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    voice_id = resolve_voice(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.workdir:
        workdir = args.workdir
        workdir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        workdir = Path(tempfile.mkdtemp(prefix="revoice-"))
        cleanup = not args.keep_workdir

    transcript_path = args.transcript or args.output.parent / f"{args.output.stem}.transcript.json"

    voice_settings = {}
    if args.stability is not None:
        voice_settings["stability"] = args.stability
    if args.similarity_boost is not None:
        voice_settings["similarity_boost"] = args.similarity_boost
    if args.style is not None:
        voice_settings["style"] = args.style

    log(f"Workdir: {workdir}")
    log(f"Voice ID: {voice_id}")
    log(f"TTS model: {args.model}")
    if voice_settings:
        log(f"Voice settings: {voice_settings}")

    try:
        input_is_video = has_video_stream(args.input)

        # 1. Extract audio
        src_audio = workdir / "source.mp3"
        extract_audio(args.input, src_audio)
        input_dur = probe_duration(args.input)
        log(f"Input duration: {input_dur:.1f}s")

        # 2. Transcribe (or load from override)
        if args.text_override:
            text = args.text_override.read_text().strip()
            log(f"Using text override ({len(text)} chars)")
            transcript_data = {"text": text, "source": "override"}
        else:
            audio_url = args.audio_url or upload_to_tmpfiles(src_audio)
            transcript_data = transcribe_whisperx(audio_url, rep_token, args.language)
            segments = transcript_data.get("segments", [])
            text = transcript_data.get("text") or segments_to_text(segments)
            log(f"Transcript: {len(text)} chars, {len(segments)} segments")

        transcript_path.write_text(json.dumps(transcript_data, indent=2))
        log(f"Transcript saved → {transcript_path}")

        # 3. Chunk text (only used in non-Studio path)
        if args.use_studio:
            log("Using Studio API path — single coherent render, no chunking.")
            chunks = [text]
        else:
            chunks = chunk_text(text, args.max_chars)
            log(f"TTS chunks: {len(chunks)}")
            for i, c in enumerate(chunks):
                log(f"  chunk {i:02d}: {len(c)} chars")

        # 4. Generate TTS — Studio API or chunked
        if args.use_studio:
            # Add script dir to path so we can import the sibling module
            script_dir = str(Path(__file__).resolve().parent)
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)
            from studio_render import render_studio_audio
            full_audio = workdir / "full-tts.mp3"
            render_studio_audio(
                text=text, voice_id=voice_id, api_key=el_key,
                out_path=full_audio, model_id=args.model,
                project_name=f"hermes-{args.output.stem}",
            )
        else:
            # Chunked TTS — chain previous_request_ids for voice consistency
            converted = []
            prior_request_ids: list[str] = []
            for i, chunk in enumerate(chunks):
                log(f"Generating TTS chunk {i+1}/{len(chunks)}...")
                out_chunk = workdir / f"tts-{i:02d}.mp3"
                prev_text = chunks[i-1] if i > 0 else None
                next_text = chunks[i+1] if i < len(chunks) - 1 else None
                req_id = tts_chunk(
                    chunk, voice_id, args.model, el_key,
                    prev_text, next_text, args.output_format, out_chunk,
                    voice_settings=voice_settings or None,
                    previous_request_ids=prior_request_ids if prior_request_ids else None,
                )
                if req_id:
                    prior_request_ids.append(req_id)
                converted.append(out_chunk)

            # 5. Concat (chunked path only)
            full_audio = workdir / "full-tts.mp3"
            concat_mp3s(converted, full_audio, workdir)
        new_audio_dur = probe_duration(full_audio)
        log(f"Generated audio: {new_audio_dur:.1f}s (vs input {input_dur:.1f}s)")

        # 6. Mux
        if input_is_video and args.output.suffix.lower() in VIDEO_EXTS:
            mux_audio_over_video(args.input, full_audio, args.output, input_dur, new_audio_dur,
                                 stretch_video=args.stretch_video)
        else:
            # Audio-only output
            if args.output.suffix.lower() == ".mp3":
                shutil.copy(full_audio, args.output)
            else:
                run(["ffmpeg", "-y", "-i", str(full_audio), str(args.output)], capture=True)

        log(f"\n✓ Done: {args.output} ({args.output.stat().st_size/1024/1024:.1f} MB)")
        log(f"  duration: {probe_duration(args.output):.1f}s")
        log(f"  transcript: {transcript_path}")

    finally:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            log(f"Workdir preserved: {workdir}")


if __name__ == "__main__":
    main()
