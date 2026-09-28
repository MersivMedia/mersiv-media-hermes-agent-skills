#!/usr/bin/env python3
"""
ElevenLabs voice changer — convert speech in a video/audio file to another voice.

Usage:
    voice_change.py INPUT OUTPUT --voice-id VOICE_ID [options]
    voice_change.py INPUT OUTPUT --voice narrator-alt     # shortcut from voices.json

Workflow:
    1. Extract audio (mono mp3 44.1kHz)
    2. If >chunk_limit, split on silence; else single request
    3. POST each chunk to /v1/speech-to-speech/{voice_id}
    4. Concat returned mp3s
    5. If input was video, mux new audio over original video stream
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

API_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_sts_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_CHUNK_LIMIT = 270.0  # seconds — API hard cap is 300s, leave 30s headroom
SILENCE_GAP_MS = 80          # inserted between hard-cut chunks if no silence found

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


def extract_audio(input_path: Path, out_path: Path, remove_noise: bool = False,
                  pre_pitch_semitones: float = 0.0) -> None:
    """Extract audio as mono 44.1kHz mp3, optionally pre-pitch-shifted."""
    cmd = ["ffmpeg", "-y", "-i", str(input_path), "-vn",
           "-ac", "1", "-ar", "44100"]
    if pre_pitch_semitones != 0.0:
        ratio = 2 ** (pre_pitch_semitones / 12.0)
        cmd += ["-af", f"rubberband=pitch={ratio}"]
    cmd += ["-b:a", "128k", str(out_path)]
    log(f"Extracting audio → {out_path.name}" +
        (f" (pre-pitch {pre_pitch_semitones:+g}st)" if pre_pitch_semitones else ""))
    run(cmd, capture=True)


def detect_silences(audio_path: Path, noise_db: float = -30.0, min_silence_s: float = 0.5) -> list[tuple[float, float]]:
    """Return list of (silence_start, silence_end) tuples in seconds."""
    cmd = ["ffmpeg", "-i", str(audio_path),
           "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}",
           "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    starts, ends = [], []
    for line in res.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            starts.append(float(m.group(1)))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m:
            ends.append(float(m.group(1)))
    return list(zip(starts, ends))


def plan_chunks(duration: float, silences: list[tuple[float, float]], chunk_limit: float) -> list[tuple[float, float]]:
    """Plan chunk boundaries [(start, end), ...] using silence midpoints when possible."""
    if duration <= chunk_limit:
        return [(0.0, duration)]

    chunks = []
    cursor = 0.0
    while duration - cursor > chunk_limit:
        target = cursor + chunk_limit
        # Look for a silence whose midpoint is in (cursor + chunk_limit*0.6, cursor + chunk_limit)
        window_start = cursor + chunk_limit * 0.6
        window_end = cursor + chunk_limit
        best_cut = None
        for s_start, s_end in silences:
            mid = (s_start + s_end) / 2
            if window_start <= mid <= window_end:
                best_cut = mid  # take the latest silence in window
        if best_cut is None:
            # Hard cut at chunk_limit
            best_cut = target
            log(f"  no silence in window [{window_start:.1f}, {window_end:.1f}] — hard cut at {best_cut:.1f}")
        chunks.append((cursor, best_cut))
        cursor = best_cut
    chunks.append((cursor, duration))
    return chunks


def split_audio(audio_path: Path, chunks: list[tuple[float, float]], workdir: Path) -> list[Path]:
    paths = []
    for i, (start, end) in enumerate(chunks):
        out = workdir / f"chunk-{i:02d}.mp3"
        cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
               "-i", str(audio_path), "-c:a", "libmp3lame", "-b:a", "128k",
               "-ac", "1", "-ar", "44100", str(out)]
        run(cmd, capture=True)
        paths.append(out)
        log(f"  chunk {i:02d}: {start:6.1f}s — {end:6.1f}s ({end-start:.1f}s) → {out.name}")
    return paths


def post_speech_to_speech(audio_path: Path, voice_id: str, api_key: str,
                          model_id: str, remove_noise: bool, output_format: str,
                          out_path: Path, voice_settings: dict | None = None,
                          retries: int = 3) -> None:
    url = f"{API_BASE}/speech-to-speech/{voice_id}?output_format={output_format}"
    headers = {"xi-api-key": api_key}

    for attempt in range(1, retries + 1):
        try:
            with open(audio_path, "rb") as fh:
                files = {"audio": (audio_path.name, fh, "audio/mpeg")}
                data = {
                    "model_id": model_id,
                    "remove_background_noise": "true" if remove_noise else "false",
                }
                if voice_settings:
                    data["voice_settings"] = json.dumps(voice_settings)
                t0 = time.time()
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=900)
            if resp.status_code == 200:
                out_path.write_bytes(resp.content)
                log(f"  ✓ {audio_path.name} → {out_path.name} ({len(resp.content)/1024:.0f} KB, {time.time()-t0:.1f}s)")
                return
            log(f"  ✗ attempt {attempt} HTTP {resp.status_code}: {resp.text[:300]}")
            if resp.status_code in (401, 403, 422):
                raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:500]}")
        except requests.RequestException as e:
            log(f"  ✗ attempt {attempt} network error: {e}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"voice changer failed after {retries} attempts for {audio_path}")


def concat_mp3s(chunks: list[Path], out_path: Path, workdir: Path, gap_ms: int = SILENCE_GAP_MS) -> None:
    """Concat mp3 chunks, inserting a brief silence between them to mask seams."""
    if len(chunks) == 1:
        shutil.copy(chunks[0], out_path)
        return

    # Build concat list with silence padding
    silence = workdir / "silence.mp3"
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"anullsrc=channel_layout=mono:sample_rate=44100",
         "-t", f"{gap_ms/1000:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(silence)],
        capture=True)

    list_file = workdir / "concat.txt"
    lines = []
    for i, c in enumerate(chunks):
        lines.append(f"file '{c.resolve()}'")
        if i < len(chunks) - 1:
            lines.append(f"file '{silence.resolve()}'")
    list_file.write_text("\n".join(lines) + "\n")

    # Re-encode during concat to normalize timing
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c:a", "libmp3lame", "-b:a", "128k", "-ac", "1", "-ar", "44100", str(out_path)],
        capture=True)


def mux_audio_over_video(video_path: Path, audio_path: Path, out_path: Path) -> None:
    """Copy video stream, replace audio with new track. Truncates to shorter stream."""
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
           "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-shortest", str(out_path)]
    log(f"Muxing new audio over video → {out_path.name}")
    run(cmd, capture=True)


def resolve_voice(args, voices_json: Path) -> str:
    if args.voice_id:
        return args.voice_id
    if args.voice:
        if not voices_json.exists():
            raise SystemExit(f"voices.json not found at {voices_json}")
        data = json.loads(voices_json.read_text())
        if args.voice not in data:
            raise SystemExit(f"unknown voice shortcut '{args.voice}'. Known: {', '.join(data.keys())}")
        return data[args.voice]["voice_id"]
    raise SystemExit("must provide --voice-id or --voice")


def main():
    ap = argparse.ArgumentParser(description="ElevenLabs voice changer for video/audio")
    ap.add_argument("input", type=Path, help="Input video or audio file")
    ap.add_argument("output", type=Path, help="Output file path")
    ap.add_argument("--voice-id", help="ElevenLabs voice ID (e.g. 6zTRy4vPhz1hAPsZhT9A)")
    ap.add_argument("--voice", help="Voice shortcut name from voices.json (e.g. narrator-alt)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"ElevenLabs model id (default: {DEFAULT_MODEL})")
    ap.add_argument("--output-format", default=DEFAULT_OUTPUT_FORMAT,
                    help=f"API output format (default: {DEFAULT_OUTPUT_FORMAT})")
    ap.add_argument("--chunk-limit", type=float, default=DEFAULT_CHUNK_LIMIT,
                    help=f"Max seconds per API request (default: {DEFAULT_CHUNK_LIMIT})")
    ap.add_argument("--remove-background-noise", action="store_true",
                    help="Strip non-speech background before conversion")
    ap.add_argument("--stability", type=float, default=None,
                    help="voice_settings.stability 0-1. Higher = less source pitch bleed.")
    ap.add_argument("--similarity-boost", type=float, default=None,
                    help="voice_settings.similarity_boost 0-1.")
    ap.add_argument("--style", type=float, default=None,
                    help="voice_settings.style 0-1. Lower = pull toward target voice's natural style.")
    ap.add_argument("--use-speaker-boost", action="store_true",
                    help="voice_settings.use_speaker_boost (clearer target voice)")
    ap.add_argument("--lock-identity", action="store_true",
                    help="Preset: stability=1.0, style=0.0, similarity_boost=1.0, speaker_boost=on. "
                         "Forces full target-voice identity, kills source pitch/timbre bleed-through.")
    ap.add_argument("--pre-pitch", type=float, default=0.0,
                    help="Pitch-shift source audio by N semitones BEFORE sending to API. "
                         "Negative = lower. ONLY USE FOR FEMALE→MALE (or wide pitch gap) "
                         "conversions, e.g. -3 for female source → male [character] voice. "
                         "Do NOT use when source/target are in the same vocal range.")
    ap.add_argument("--workdir", type=Path, help="Working directory (default: tempdir)")
    ap.add_argument("--keep-workdir", action="store_true", help="Don't delete workdir on success")
    args = ap.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise SystemExit("ELEVENLABS_API_KEY not set in environment")

    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    skill_dir = Path(__file__).resolve().parent
    voice_id = resolve_voice(args, skill_dir / "voices.json")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.workdir:
        workdir = args.workdir
        workdir.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        workdir = Path(tempfile.mkdtemp(prefix="voicechg-"))
        cleanup = not args.keep_workdir

    log(f"Workdir: {workdir}")
    log(f"Voice ID: {voice_id}")
    log(f"Model: {args.model}")

    # Build voice_settings
    voice_settings = {}
    if args.lock_identity:
        voice_settings = {
            "stability": 1.0,
            "similarity_boost": 1.0,
            "style": 0.0,
            "use_speaker_boost": True,
        }
    if args.stability is not None:
        voice_settings["stability"] = args.stability
    if args.similarity_boost is not None:
        voice_settings["similarity_boost"] = args.similarity_boost
    if args.style is not None:
        voice_settings["style"] = args.style
    if args.use_speaker_boost:
        voice_settings["use_speaker_boost"] = True
    if voice_settings:
        log(f"Voice settings: {voice_settings}")

    try:
        input_is_video = has_video_stream(args.input)
        log(f"Input type: {'video' if input_is_video else 'audio'}")

        # 1. Extract audio (optionally pre-pitched)
        src_audio = workdir / "source.mp3"
        extract_audio(args.input, src_audio, pre_pitch_semitones=args.pre_pitch)
        duration = probe_duration(src_audio)
        log(f"Source audio duration: {duration:.1f}s")

        # 2. Plan chunks
        if duration > args.chunk_limit:
            log("Detecting silences for chunk boundaries...")
            silences = detect_silences(src_audio)
            log(f"  found {len(silences)} silences")
        else:
            silences = []
        chunks = plan_chunks(duration, silences, args.chunk_limit)
        log(f"Planned {len(chunks)} chunk(s)")

        # 3. Split & convert each
        chunk_paths = split_audio(src_audio, chunks, workdir) if len(chunks) > 1 else [src_audio]
        converted_paths = []
        for i, cp in enumerate(chunk_paths):
            out_chunk = workdir / f"converted-{i:02d}.mp3"
            log(f"Converting chunk {i+1}/{len(chunk_paths)}...")
            post_speech_to_speech(
                cp, voice_id, api_key, args.model,
                args.remove_background_noise, args.output_format,
                out_chunk,
                voice_settings=voice_settings or None,
            )
            converted_paths.append(out_chunk)

        # 4. Concat
        full_audio = workdir / "full-converted.mp3"
        concat_mp3s(converted_paths, full_audio, workdir)
        log(f"Concatenated audio: {probe_duration(full_audio):.1f}s")

        # 5. Final output
        if input_is_video and args.output.suffix.lower() in VIDEO_EXTS:
            mux_audio_over_video(args.input, full_audio, args.output)
        else:
            # Audio-only output
            if args.output.suffix.lower() == ".mp3":
                shutil.copy(full_audio, args.output)
            else:
                run(["ffmpeg", "-y", "-i", str(full_audio), str(args.output)], capture=True)

        log(f"\n✓ Done: {args.output}  ({args.output.stat().st_size/1024/1024:.1f} MB)")
        log(f"  duration: {probe_duration(args.output):.1f}s")

    finally:
        if cleanup:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            log(f"Workdir preserved: {workdir}")


if __name__ == "__main__":
    main()
