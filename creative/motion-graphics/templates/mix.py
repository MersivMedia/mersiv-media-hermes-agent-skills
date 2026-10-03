# mix.py — the soundtrack: music (offset so its drop hits the key frame) + SFX placed by their MEASURED PEAK
# (not their file start), optional voice-over with ducking, tail fade, two-pass loudnorm to -14 LUFS / TP -1.
# Usage: python mix.py [--video out/silent.mp4 --out out/final.mp4]
# Reads sound.json:
# {
#   "dur": 15,                                     film length (s)
#   "music": "audio/track.mp3", "offset": 6.77,    start the song here (drop.py prints it); or music.mjs output, offset 0
#   "music_gain": 1.0, "fade_in": 0.25, "fade_out": 0.9,
#   "sfx": {"click": "sfx/1125.mp3", "whoosh": "synth:whoosh"},   files, or synth:<voice> from sfx.mjs voices
#   "cues": [[0.5, "click", 0.2], [2.5, "whoosh", 0.05]],          [time, name, gain 0.04-0.3]; peak lands ON time
#   "voice": "audio/vo.wav", "voice_at": 0.4, "duck_db": 9           optional VO, music ducked under it
# }
# Writes out/mix.wav (48 kHz stereo). With --video, muxes it (video stream copied).
# Needs numpy + ffmpeg. Adapted from howseen-ai/claude-motion-design audio_template.py (MIT).
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 48000
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
cfg = json.loads(Path(opt("--config", "sound.json")).read_text())
T = float(cfg["dur"])
N = int(round(T * SR))


def load(p, start=0.0):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-ss", str(max(0, start)), "-i", str(p), "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def synth(voice, seed=42):
    """Same voices as sfx.mjs, for when no SFX file is used."""
    s = [seed]

    def noise():
        s[0] = (s[0] * 1664525 + 1013904223) % 4294967296
        return s[0] / 2147483648 - 1
    V = {
        "click": (0.05, lambda t: math.sin(2 * math.pi * 1800 * t) * math.exp(-t * 90) * 0.5),
        "tick": (0.03, lambda t: math.sin(2 * math.pi * 3200 * t) * math.exp(-t * 160) * 0.35),
        "pop": (0.15, lambda t: math.sin(2 * math.pi * (600 + 900 * t) * t) * math.exp(-t * 30) * 0.4),
        "thump": (0.5, lambda t: math.sin(2 * math.pi * (90 - 60 * t) * t) * math.exp(-t * 9) * 0.9),
        "whoosh": (0.35, lambda t: noise() * math.sin(math.pi * min(1, t / 0.35)) * 0.25),
    }
    ln, fn = V[voice]
    m = np.array([fn(i / SR) for i in range(int(ln * SR))], np.float32)
    return np.stack([m, m], 1)


mix = np.zeros((N, 2), np.float32)
if cfg.get("music"):
    m = load(cfg["music"], float(cfg.get("offset", 0)))[:N] * float(cfg.get("music_gain", 1.0))
    if float(cfg.get("offset", 0)) < 0:                  # song starts after the film starts
        pad = int(-float(cfg["offset"]) * SR)
        m = np.concatenate([np.zeros((pad, 2), np.float32), load(cfg["music"])])[:N]
    fi = int(float(cfg.get("fade_in", 0.25)) * SR)
    if fi:
        m[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix[: len(m)] += m

if cfg.get("voice"):
    v = load(cfg["voice"])
    i0 = int(float(cfg.get("voice_at", 0)) * SR)
    v = v[: max(0, N - i0)]
    env = np.convolve(np.abs(v).mean(1), np.ones(int(0.15 * SR)) / int(0.15 * SR), "same")
    duck = 10 ** (-float(cfg.get("duck_db", 9)) / 20)
    g = np.ones(N, np.float32)
    g[i0:i0 + len(v)] = np.where(env > 0.01, duck, 1.0)
    g = np.convolve(g, np.ones(int(0.08 * SR)) / int(0.08 * SR), "same")      # smooth the ducking
    mix *= g[:, None]
    mix[i0:i0 + len(v)] += v

bank = {}
for name, src in cfg.get("sfx", {}).items():
    bank[name] = synth(src.split(":", 1)[1]) if src.startswith("synth:") else load(src)
placed = 0
for t, name, gain in cfg.get("cues", []):
    s = bank[name] if name in bank else synth(name)
    s = s / (np.abs(s).max() + 1e-9) * float(gain)
    i0 = int(round(float(t) * SR)) - int(np.abs(s).sum(1).argmax())        # the PEAK lands exactly on t
    lo, hi = max(0, i0), min(N, i0 + len(s))
    if hi > lo:
        mix[lo:hi] += s[lo - i0:hi - i0]
        placed += 1

fo = int(float(cfg.get("fade_out", 0.9)) * SR)
if fo:
    mix[N - fo:] *= (np.linspace(1, 0, fo) ** 1.3)[:, None]

out = Path("out"); out.mkdir(exist_ok=True)
raw = out / "mix_raw.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", str(raw)],
               input=mix.astype(np.float32).tobytes(), check=True)
# two-pass loudnorm: measure, then normalise linearly to the target (one pass pumps)
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
                       "-f", "null", "-"], capture_output=True, text=True).stderr
j = json.loads(meas[meas.rindex("{"): meas.rindex("}") + 1])
af = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
      f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
wav = out / "mix.wav"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", af, "-ar", str(SR), str(wav)], check=True)
raw.unlink()
chk = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af", "ebur128=peak=true", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
I = [l for l in chk.splitlines() if l.strip().startswith("I:")][-1].split()[1]
print(f"wrote {wav}: {T}s, {placed} SFX placed by peak, integrated {I} LUFS")
if opt("--video"):
    final = opt("--out", "out/final.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", opt("--video"), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", final], check=True)
    print(f"wrote {final}")
