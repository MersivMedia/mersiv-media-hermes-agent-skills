# remake_audio.py — Phase 2 audio-agent helper: analyse REF's soundtrack (never reuse it), then fit a royalty-free track.
#   python3 remake_audio.py analyse                 REF tempo, loudest low-band jumps (drop candidates), hard stop,
#                                                   SFX-like transient hits -> ref/audio_map.json
#   python3 remake_audio.py fit audio/track.mp3 --track-drop 31.97 [--ref-drop 14.75] [--max-stretch 0.08]
#        stretch our track (atempo, <= 8%) so its BPM matches REF's, offset so its drop lands on REF's drop time,
#        cut at REF's hard stop -> out/music_fit.wav and a sound.json for motion-graphics mix.py
#        (cues = REF transient hits, synthesized; tune names/gains by ear). VO slots: STT word timings only.
# Needs numpy + ffmpeg. Reuses motion-graphics drop.py logic.
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050
H = Path.cwd()
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d


def load(p, sr=SR):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(p), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def bpm(x):
    hop = 256
    fr = len(x) // hop
    env = np.sqrt((x[: fr * hop].reshape(fr, hop) ** 2).mean(1))
    on = np.maximum(0, np.diff(np.log(env + 1e-6)))
    on -= on.mean()
    m = min(len(on), 6000)
    ac = np.correlate(on[:m], on[:m], "full")[m - 1:]
    fps = SR / hop
    return max(((60 / (i / fps), ac[i]) for i in range(1, len(ac)) if 0.33 < i / fps < 1.0), key=lambda z: z[1])[0]


def drops(x, step=0.5):
    lp = np.convolve(x, np.ones(60) / 60, "same")
    win = int(step * SR)
    e = np.array([10 * np.log10((lp[i:i + win] ** 2).mean() + 1e-12) for i in range(0, len(lp) - win, win)])
    j = np.diff(e)
    idx = np.argsort(j)[::-1][:3]
    return [(round((i + 1) * step, 2), round(float(j[i]), 1)) for i in idx]


if a[0] == "analyse":
    x = load(H / "ref/audio.wav")
    dur = len(x) / SR
    hop = 512
    env = np.sqrt((x[: len(x) // hop * hop].reshape(-1, hop) ** 2).mean(1))
    loud = np.where(env > env.max() * 0.02)[0]
    stop = round(float((loud[-1] + 1) * hop / SR), 3) if len(loud) else dur
    on = np.maximum(0, np.diff(env))
    thr = on.mean() + 4 * on.std()
    hits, last = [], -1
    for i in np.where(on > thr)[0]:
        t = (i + 1) * hop / SR
        if t - last > 0.12:
            hits.append(round(float(t), 3))
            last = t
    m = {"duration": round(dur, 3), "bpm": round(float(bpm(x)), 2), "drop_candidates": drops(x), "hard_stop": stop, "hits": hits}
    (H / "ref/audio_map.json").write_text(json.dumps(m, indent=1))
    print(json.dumps({k: v for k, v in m.items() if k != "hits"}), f"| {len(hits)} transient hits -> ref/audio_map.json")
    print("pick REF's drop from the candidates BY EAR/EYE (check ref sheets), then: fit <track> --track-drop T --ref-drop R")
elif a[0] == "fit":
    m = json.loads((H / "ref/audio_map.json").read_text())
    track = a[1]
    y = load(track)
    tb, rb = float(opt("--track-bpm") or bpm(y)), float(opt("--ref-bpm") or m["bpm"])
    ratio = rb / tb
    for cand in (ratio, ratio * 2, ratio / 2):        # allow half/double-time matches
        if abs(cand - 1) <= float(opt("--max-stretch", "0.08")):
            ratio = cand
            break
    else:
        sys.exit(f"tempo gap too big: track {tb:.1f} vs REF {rb:.1f} BPM (needs x{ratio:.3f}); pick another track")
    track_drop = float(opt("--track-drop")) / ratio      # drop time after stretching
    ref_drop = float(opt("--ref-drop") or m["drop_candidates"][0][0])
    offset = track_drop - ref_drop
    out = H / "out"
    out.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", track, "-af", f"atempo={ratio:.5f}", "-ar", "48000", "-ac", "2",
                    str(out / "music_fit.wav")], check=True)
    # mix length = the FILM's length (REF duration), never the audio hard stop: a shorter mix + -shortest truncates the video.
    # The music fades out so it ends at REF's hard stop; silence after it matches REF.
    film = float(opt("--dur") or m["duration"])
    fade = max(0.05, film - m["hard_stop"] + 0.3) if m["hard_stop"] < film else 0.3
    cfg = {"dur": round(film, 3), "music": "out/music_fit.wav", "offset": round(offset, 3), "fade_in": 0.05,
           "fade_out": round(min(fade, film), 3), "sfx": {}, "cues": [[t, "tick", 0.06] for t in m["hits"]]}
    (H / "sound.json").write_text(json.dumps(cfg, indent=1))
    print(f"stretch x{ratio:.4f} ({tb:.1f} -> {rb:.1f} BPM), track drop {track_drop:.3f}s lands on REF {ref_drop:.3f}s "
          f"(offset {offset:.3f}s), film {film:.3f}s, music silent after REF's hard stop {m['hard_stop']}s "
          f"-> out/music_fit.wav + sound.json ({len(m['hits'])} placeholder cues). Then: python3 mix.py")
