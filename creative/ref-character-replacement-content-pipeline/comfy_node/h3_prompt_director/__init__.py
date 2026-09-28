"""H3 Prompt Director — ComfyUI custom node.

Turns a one-line instruction plus a character reference image and a source
video into a full MiniMax H3 full-reference-mode prompt (the six sections from
VIDEO_PROMPT_WRITING_GUIDE_ref_en.md), with correct <Subject>/<Picture>/<Video>
labels, and feeds it straight into MiniMaxH3ReferenceToVideo.

The LLM call goes to Anthropic. The key is read from the pod ENVIRONMENT
(ANTHROPIC_API_KEY) and never stored in the workflow, so exported workflow
JSON never contains a secret.

Content policy is enforced HERE, not only in the agent, so it applies the same
way to a manual browser run as to a Telegram-triggered one.
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request

import numpy as np

try:
    from PIL import Image
except ImportError:  # ComfyUI always ships Pillow; guard for linting only
    Image = None

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE_PATH = os.path.join(HERE, "guide_ref_en.md")
CRAFT_PATH = os.path.join(HERE, "cinematography_vocab.md")
DEFAULT_MODEL = os.environ.get("H3_DIRECTOR_MODEL", "claude-sonnet-4-5")

POLICY = """HARD CONTENT RULES — these override the user's instruction:
1. Never describe nudity, sexual acts, sexual touching, undressing, or sexualised
   framing. If the SOURCE VIDEO itself contains such content, do not describe
   it: output exactly REFUSED: <one-line reason> and nothing else.
2. If the instruction asks to make a real, identifiable person (a celebrity,
   public figure, or a named private individual) do or appear to do something,
   output exactly REFUSED: <one-line reason> and nothing else. Fictional,
   stylised, generated, or self-portrait characters are fine.
3. Never invent camera moves: in video-editing mode the source video's camera is
   fixed structure. Describe the camera the source actually has, using precise
   cinematography vocabulary. Enhance lighting, rendition, colour, texture and
   (in background mode) environment instead."""

SYSTEM = """You write prompts for MiniMax H3 in full-reference (ref2va) mode.
Follow the attached writing guide EXACTLY: six sections, in this order and with
these exact keys:

subject_definitions:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:
(and the task summary / type content the guide requires inside those sections)

Label conventions for THIS pipeline:
- <Video 1> is the source video being edited. Its camera framing, camera motion
  and timing are fixed structure in BOTH modes.
- <Subject 1> is the original performer in <Video 1>.
- <Picture 1> is the first frame of <Video 1> (supplied so you can see it).
- <Subject 2> is the replacement character shown in <Picture 2>.
- <Subject 1> is partially_preserved (motion, pose, timing kept; appearance
  replaced). <Subject 2> is attribute_transfer.

There are exactly two modes, set by REPLACE_BACKGROUND:
- REPLACE_BACKGROUND = false: <Picture 2> shows the character cut out onto a
  flat neutral grey backdrop. That grey is NOT an environment — never describe
  or reference it. The environment of <Video 1> is fully_preserved: describe
  the source's own setting and lighting exactly as the frames show it.
- REPLACE_BACKGROUND = true: <Picture 2> shows the character inside their own
  environment. That environment replaces the source's: in retention_analysis
  the <Video 1> environment is attribute_transfer from <Picture 2>, while
  <Video 1>'s camera framing, camera motion and choreography timing remain
  fully_preserved. Describe the new environment from <Picture 2>, adapted to
  the source's framing (e.g. a wider view than <Picture 2> shows). Do NOT
  transfer any other people who appear in <Picture 2>'s environment; the
  replacement character is the only person in the frame unless the source
  video itself contains others.

Write detailed_description shot by shot with [Shot 1] and timestamps for later
beats, describing only what the frames actually show. Use the cinematography
vocabulary for lighting, lens feel, colour and texture. Output ONLY the prompt
text, no preamble, no markdown fences.

""" + POLICY


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _tensor_to_jpeg_b64(t, max_side: int = 768) -> str:
    """ComfyUI IMAGE tensor [B,H,W,C] float 0..1 -> base64 JPEG of frame 0."""
    arr = t[0].cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)[0]
    arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def _sample_frames(video, n: int):
    """Evenly sample n frames from an IMAGE batch [F,H,W,C]."""
    f = video.shape[0]
    if f == 0:
        return []
    idx = np.linspace(0, f - 1, num=min(n, f)).round().astype(int)
    return [video[i:i + 1] for i in idx]


def _call_claude(model: str, system: str, content: list, max_tokens: int = 3000) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set in the pod environment. "
            "Set it in /root/secrets.env (container disk, never /workspace) and restart ComfyUI.")
    body = json.dumps({"model": model, "max_tokens": max_tokens,
                       "system": system,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


class H3PromptDirector:
    """Instruction + references -> six-section H3 ref2va prompt.

    `character_image` must be exactly what H3 receives as <Picture 2>:
    the SAM3 cutout on grey when replace_background is off, the original
    reference (with its environment) when it is on. The graph's switch node
    guarantees this, so the prompt and the conditioning never disagree.
    """

    CATEGORY = "MiniMax H3/Prompt"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "preview")
    FUNCTION = "direct"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_video": ("IMAGE", {"tooltip": "Frames of the video being edited (<Video 1>)"}),
                "character_image": ("IMAGE", {"tooltip": "Exactly what H3 gets as <Picture 2>"}),
                "instruction": ("STRING", {"multiline": True,
                                           "default": "Replace the performer with the character in the reference image."}),
                "replace_background": ("BOOLEAN", {"default": False,
                                                   "label_on": "use character's background",
                                                   "label_off": "keep video's background",
                                                   "tooltip": "On: the environment comes from the character reference image. Off: the source video keeps its own background."}),
                "duration_seconds": ("FLOAT", {"default": 5.0, "min": 2.0, "max": 15.0, "step": 0.5}),
                "frames_to_analyse": ("INT", {"default": 6, "min": 2, "max": 12}),
                "model": ("STRING", {"default": DEFAULT_MODEL}),
            },
            "optional": {
                "manual_override": ("STRING", {"multiline": True, "default": "",
                                               "tooltip": "If non-empty, used verbatim (still policy-screened) and the LLM is skipped"}),
            },
        }

    def direct(self, source_video, character_image, instruction, replace_background,
               duration_seconds, frames_to_analyse, model, manual_override=""):
        if manual_override and manual_override.strip():
            self._screen(manual_override, model)
            return (manual_override.strip(), manual_override.strip())

        guide = _read(GUIDE_PATH)
        craft = _read(CRAFT_PATH)
        content: list = [
            {"type": "text", "text": f"WRITING GUIDE:\n{guide}\n\nCINEMATOGRAPHY VOCABULARY:\n{craft[:12000]}"},
            {"type": "text", "text": (f"Source video duration: {duration_seconds:.1f} s. The following "
                                      f"{frames_to_analyse} images are evenly spaced frames of <Video 1> in "
                                      f"playback order; the first is <Picture 1>.")},
        ]
        for fr in _sample_frames(source_video, frames_to_analyse):
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                        "data": _tensor_to_jpeg_b64(fr)}})
        content.append({"type": "text", "text": "This is <Picture 2>, the replacement character:"})
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": _tensor_to_jpeg_b64(character_image)}})
        content.append({"type": "text", "text": (f"REPLACE_BACKGROUND = {str(bool(replace_background)).lower()}\n"
                                                 f"USER INSTRUCTION: {instruction}\n\nWrite the full prompt now.")})

        out = _call_claude(model, SYSTEM, content)
        if out.startswith("REFUSED"):
            raise RuntimeError(f"H3 Prompt Director declined: {out}")
        missing = [k for k in ("subject_definitions:", "retention_analysis:", "detailed_description:",
                               "overall_soundscape:", "non_diegetic_music:") if k not in out]
        if missing:
            raise RuntimeError(f"Prompt missing sections {missing}; re-queue to retry.\n\n{out[:800]}")
        return (out, out)

    @staticmethod
    def _screen(text: str, model: str):
        verdict = _call_claude(model, "You are a content screen. " + POLICY +
                               "\nReply ALLOWED or REFUSED: <reason>.",
                               [{"type": "text", "text": text[:8000]}], max_tokens=60)
        if verdict.upper().startswith("REFUSED"):
            raise RuntimeError(f"H3 Prompt Director declined manual prompt: {verdict}")


class H3AudioRoute:
    """Choose the soundtrack written into the output file.

    MiniMax H3 generates audio JOINTLY with video (one latent), so generation
    itself can't skip it. This node only decides what ends up in the file:
      generated  decode H3's own audio track
      source     the original video's soundtrack (in sync; best for dialogue)
      off        silent video
    Both audio inputs are LAZY: in `source`/`off` mode VAEDecodeAudio never
    runs, and in `generated`/`off` mode the source track is never extracted.
    """

    CATEGORY = "MiniMax H3/Audio"
    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "route"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (["source", "generated", "off"], {
                    "default": "source",
                    "tooltip": "source = original video's soundtrack; generated = H3's audio; off = silent"}),
            },
            "optional": {
                "generated_audio": ("AUDIO", {"lazy": True}),
                "source_audio": ("AUDIO", {"lazy": True}),
            },
        }

    def check_lazy_status(self, mode, generated_audio=None, source_audio=None):
        if mode == "generated" and generated_audio is None:
            return ["generated_audio"]
        if mode == "source" and source_audio is None:
            return ["source_audio"]
        return []

    @staticmethod
    def _plain(a):
        """VHS hands over a LazyAudioMap; touching it runs ffmpeg. Return a
        plain dict, or None if the source has no usable audio track."""
        if a is None:
            return None
        try:
            wf, sr = a["waveform"], a["sample_rate"]
        except Exception as e:  # no audio stream / ffmpeg failure
            print(f"[H3AudioRoute] source has no readable audio ({e}); writing silent video")
            return None
        if wf is None or getattr(wf, "numel", lambda: 0)() == 0:
            print("[H3AudioRoute] source audio track is empty; writing silent video")
            return None
        return {"waveform": wf, "sample_rate": sr}

    def route(self, mode, generated_audio=None, source_audio=None):
        if mode == "generated":
            return (generated_audio,)
        if mode == "source":
            return (self._plain(source_audio),)
        return (None,)


NODE_CLASS_MAPPINGS = {"H3PromptDirector": H3PromptDirector, "H3AudioRoute": H3AudioRoute}
NODE_DISPLAY_NAME_MAPPINGS = {"H3PromptDirector": "H3 Prompt Director",
                              "H3AudioRoute": "H3 Audio (source / generated / off)"}
