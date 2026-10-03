# drop.py — find where a track really drops/lifts, by band energy. Never trust an automatic beat grid
# (one real track had its detected bar 2 beats off, so the drop landed on nothing).
# Usage:
#   python drop.py audio/track.mp3                    BPM estimate + per-bar full/low-band energy + biggest jumps
#   python drop.py audio/track.mp3 --zoom 31.9        20 ms energy windows around a candidate -> exact drop time
#   python drop.py audio/track.mp3 --drop 31.97 --at 8.0 --dur 15 [--bpm 120] > beats.json
#        writes beats.json with offset = drop - at (start the song there so its drop hits film time `at`),
#        beats/downbeats re-anchored on the drop, and `drop` = film time of the drop.
# Needs numpy + ffmpeg only (no librosa). Adapted from howseen-ai/claude-motion-design (MIT).
import json
import subprocess
import sys

import numpy as np

SR = 22050


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def lowpass(x, n=60):                       # ~ <180 Hz at 22.05 kHz: kick + bass
    return np.convolve(x, np.ones(n) / n, "same")


def db(seg):
    return 10 * np.log10((seg ** 2).mean() + 1e-12)


def bpm_estimate(x):
    hop = 256
    fr = len(x) // hop
    env = np.sqrt((x[: fr * hop].reshape(fr, hop) ** 2).mean(1))
    on = np.maximum(0, np.diff(np.log(env + 1e-6)))
    on -= on.mean()
    m = min(len(on), 6000)
    ac = np.correlate(on[:m], on[:m], "full")[m - 1:]
    fps = SR / hop
    best = max(((60 / (i / fps), ac[i]) for i in range(1, len(ac)) if 0.33 < i / fps < 1.0), key=lambda z: z[1])
    return best[0]


def first_onset(x, bpm):
    """Phase of the beat grid: the strongest low-band onset among the first 8 beats."""
    lp = lowpass(x)
    hop = 128
    fr = len(lp) // hop
    env = np.sqrt((lp[: fr * hop].reshape(fr, hop) ** 2).mean(1))
    on = np.maximum(0, np.diff(env))
    spb = 60 / bpm
    best, phase = -1, 0.0
    for ph in np.arange(0, spb, 0.005):
        idx = [int((ph + k * spb) * SR / hop) for k in range(8)]
        s = sum(on[i] for i in idx if i < len(on))
        if s > best:
            best, phase = s, ph
    return phase


def main():
    a = sys.argv[1:]
    path = a[0]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    x = load(path)
    dur = len(x) / SR
    bpm = float(opt("--bpm") or bpm_estimate(x))
    if "--zoom" in a:
        c = float(opt("--zoom"))
        lp = lowpass(x)
        prev = None
        print(f"20 ms low-band energy around {c:.2f}s (dB, jump vs previous):", file=sys.stderr)
        for t in np.arange(max(0, c - 0.3), min(dur - 0.02, c + 0.3), 0.02):
            e = db(lp[int(t * SR): int((t + 0.02) * SR)])
            print(f"  {t:7.2f}  {e:6.1f}  {'' if prev is None else f'{e - prev:+5.1f}'}", file=sys.stderr)
            prev = e
        return
    if "--drop" in a:
        drop, at = float(opt("--drop")), float(opt("--at", "0"))
        film = float(opt("--dur", str(dur)))
        offset = drop - at
        spb = 60 / bpm
        # anchor the grid on the drop (the drop is a downbeat), then extend both ways
        k0 = -int(at / spb) - 1
        beats = [round(at + k * spb, 3) for k in range(k0, int((film - at) / spb) + 2) if 0 <= at + k * spb < film]
        down = [b for b in beats if abs(((b - at) / spb) % 4) < 1e-6 or abs(((b - at) / spb) % 4 - 4) < 1e-6]
        json.dump({"bpm": round(bpm, 3), "beats": beats, "downbeats": down, "hits": [], "drop": at,
                   "song": path, "offset": round(offset, 3), "source": "drop.py"}, sys.stdout, indent=1)
        print(f"\nstart the song at {offset:.3f}s so its drop ({drop:.3f}s) lands on film {at:.3f}s", file=sys.stderr)
        return
    phase = first_onset(x, bpm)
    spb = 60 / bpm
    bar = 4 * spb
    print(f"{path}: {dur:.1f}s, BPM ~{bpm:.2f}, first beat ~{phase:.3f}s, bar {bar:.3f}s")
    lp = lowpass(x)
    rows = []
    t = phase
    while t + bar <= dur:
        i0, i1 = int(t * SR), int((t + bar) * SR)
        rows.append((t, db(x[i0:i1]), db(lp[i0:i1])))
        t += bar
    print(" bar   start   full dB  low dB   jump(low)")
    for i, (t, f, l) in enumerate(rows):
        j = l - rows[i - 1][2] if i else 0
        print(f" {i:3d}  {t:7.2f}  {f:7.1f}  {l:7.1f}   {j:+6.1f}{'  <==' if j > 4 else ''}")
    jumps = sorted(((rows[i][2] - rows[i - 1][2], rows[i][0]) for i in range(1, len(rows))), reverse=True)[:3]
    print("biggest low-band jumps (candidate drops):", ", ".join(f"{t:.2f}s (+{j:.1f} dB)" for j, t in jumps))
    print("next: --zoom <t> to pin the drop to 20 ms, then --drop <t> --at <film_t> --dur <film_s> > beats.json")


main()
