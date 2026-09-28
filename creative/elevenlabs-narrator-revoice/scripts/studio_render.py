#!/usr/bin/env python3
"""
ElevenLabs Studio API client — generates long-form narration as a single coherent take.

Unlike chunked TTS, Studio renders the entire script as one project with consistent
voice throughout. This module handles the multi-step API flow:
  1. Create project from text + voice
  2. Trigger conversion
  3. Poll until done
  4. Download the rendered audio
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path

import requests

EL_API_BASE = "https://api.elevenlabs.io/v1"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def create_project(api_key: str, name: str, text: str, voice_id: str,
                   model_id: str = "eleven_multilingual_v2") -> str:
    """Create a Studio project from text. Returns project_id."""
    url = f"{EL_API_BASE}/studio/projects"
    headers = {"xi-api-key": api_key}
    files = {"from_document": ("script.txt", text.encode("utf-8"), "text/plain")}
    data = {
        "name": name,
        "default_paragraph_voice_id": voice_id,
        "default_title_voice_id": voice_id,
        "default_model_id": model_id,
    }
    log(f"Creating Studio project '{name}'...")
    r = requests.post(url, headers=headers, files=files, data=data, timeout=120)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Studio create failed: HTTP {r.status_code} {r.text[:500]}")
    proj = r.json()["project"]
    pid = proj["project_id"]
    log(f"  project_id: {pid}")
    return pid


def trigger_convert(api_key: str, project_id: str) -> None:
    url = f"{EL_API_BASE}/studio/projects/{project_id}/convert"
    headers = {"xi-api-key": api_key}
    log("Triggering conversion...")
    r = requests.post(url, headers=headers, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Studio convert trigger failed: HTTP {r.status_code} {r.text[:500]}")


def get_project(api_key: str, project_id: str) -> dict:
    url = f"{EL_API_BASE}/studio/projects/{project_id}"
    headers = {"xi-api-key": api_key}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()


def list_snapshots(api_key: str, project_id: str) -> list[dict]:
    url = f"{EL_API_BASE}/studio/projects/{project_id}/snapshots"
    headers = {"xi-api-key": api_key}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    body = r.json()
    # Response shape: {"snapshots":[...]} or just a list
    return body.get("snapshots", body) if isinstance(body, dict) else body


def wait_for_conversion(api_key: str, project_id: str,
                        timeout_s: int = 1800, poll_s: int = 5) -> str:
    """Block until project conversion completes. Returns project_snapshot_id."""
    log(f"Polling project state (timeout {timeout_s}s)...")
    t0 = time.time()
    last_status = None
    while time.time() - t0 < timeout_s:
        proj = get_project(api_key, project_id)
        # The project dict can be top-level or wrapped under "project"
        p = proj.get("project", proj)
        chapters = p.get("chapters", [])
        # Aggregate state
        meta = p.get("creation_meta", {})
        progress = meta.get("creation_progress")
        status = meta.get("status") or p.get("state")
        elapsed = time.time() - t0
        if status != last_status:
            log(f"  status={status} progress={progress} ({elapsed:.0f}s)")
            last_status = status

        # Look for a snapshot — once a chapter has current_snapshot_id, we have audio
        for ch in chapters:
            snap = ch.get("current_snapshot_id") or ch.get("snapshot_id")
            ch_state = ch.get("state")
            if snap and ch_state in ("converted", "default", None):
                # If multiple chapters, the project-level snapshot list is more reliable
                pass

        # Also check project-level snapshot list
        snaps = list_snapshots(api_key, project_id)
        if snaps:
            # newest first
            snaps_sorted = sorted(snaps, key=lambda s: s.get("created_at_unix", 0), reverse=True)
            latest = snaps_sorted[0]
            snap_id = latest.get("project_snapshot_id")
            if snap_id:
                log(f"  ✓ snapshot ready: {snap_id} (duration={latest.get('audio_duration_secs')}s, {elapsed:.0f}s elapsed)")
                return snap_id

        time.sleep(poll_s)
    raise TimeoutError(f"Studio conversion didn't finish in {timeout_s}s")


def download_snapshot(api_key: str, project_id: str, snapshot_id: str,
                      out_path: Path, convert_to_mpeg: bool = True) -> None:
    """Stream the rendered audio to disk."""
    url = f"{EL_API_BASE}/studio/projects/{project_id}/snapshots/{snapshot_id}/stream"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {"convert_to_mpeg": convert_to_mpeg}
    log(f"Downloading snapshot {snapshot_id}...")
    with requests.post(url, headers=headers, json=payload, stream=True, timeout=600) as r:
        if r.status_code != 200:
            raise RuntimeError(f"Snapshot download failed: HTTP {r.status_code} {r.text[:500]}")
        with open(out_path, "wb") as fh:
            total = 0
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    fh.write(chunk)
                    total += len(chunk)
    log(f"  wrote {total/1024:.0f} KB → {out_path}")


def delete_project(api_key: str, project_id: str) -> None:
    """Clean up — Studio projects count against quota."""
    url = f"{EL_API_BASE}/studio/projects/{project_id}"
    headers = {"xi-api-key": api_key}
    r = requests.delete(url, headers=headers, timeout=60)
    if r.status_code == 200:
        log(f"  deleted project {project_id}")
    else:
        log(f"  warning: failed to delete project {project_id} (HTTP {r.status_code})")


def render_studio_audio(text: str, voice_id: str, api_key: str, out_path: Path,
                        project_name: str = "hermes-narrator-revoice",
                        model_id: str = "eleven_multilingual_v2",
                        cleanup: bool = True) -> None:
    """End-to-end: text → rendered mp3 via Studio API."""
    project_id = create_project(api_key, project_name, text, voice_id, model_id)
    try:
        trigger_convert(api_key, project_id)
        snapshot_id = wait_for_conversion(api_key, project_id)
        download_snapshot(api_key, project_id, snapshot_id, out_path)
    finally:
        if cleanup:
            try:
                delete_project(api_key, project_id)
            except Exception as e:
                log(f"  cleanup error: {e}")


if __name__ == "__main__":
    # CLI for quick testing: studio_render.py SCRIPT.txt OUTPUT.mp3 VOICE_ID
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise SystemExit("ELEVENLABS_API_KEY not set")
    if len(sys.argv) < 4:
        raise SystemExit("usage: studio_render.py SCRIPT.txt OUTPUT.mp3 VOICE_ID")
    text = Path(sys.argv[1]).read_text()
    out = Path(sys.argv[2])
    voice_id = sys.argv[3]
    render_studio_audio(text, voice_id, api_key, out)
    log(f"\n✓ Done: {out}")
