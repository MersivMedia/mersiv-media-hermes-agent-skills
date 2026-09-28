#!/usr/bin/env python3
"""Identify the actual instruments in a stem, not just its spectral balance.

Answers "is this bass a sine sub, an 808, or a reese?" — the question spectral
percentages cannot. Use when the user asks for a generation prompt with
"similar instruments to the original".

    /tmp/aenv/bin/python timbre.py drums.mp3 --role drums
    /tmp/aenv/bin/python timbre.py bass.mp3  --role bass
    /tmp/aenv/bin/python timbre.py other.mp3 --role other
    /tmp/aenv/bin/python timbre.py stems/ --bpm 130      # whole directory

Prints measured values, the classification each implies, and the prompt phrase
to use. See references/timbre-identification.md for thresholds and rationale.

Three bugs this script exists to avoid — all produced confident nonsense in a
real session (0 ms decay on everything, a 54 Hz sine sub reported at 1854 Hz):

  1. Decay measured from the onset index. Onsets fire on the RISE; the true
     peak is 5-40 ms later, so searching forward for peak*0.1 lands inside the
     attack and returns 0. Fix: find the real peak within ~80 ms first.
  2. Fixed onset threshold. A hardcoded 0.25 of max flux works on drums and
     finds nothing in a sparse bass stem. Fix: percentile of the band's own
     flux distribution.
  3. Spectral centroid dragged up by near-empty HF bins. Thousands of tiny
     high-frequency magnitudes pull the mean far above audible content.
     Fix: floor magnitudes at ~2% of frame max, take the MEDIAN across frames.

Requires the venv from the skill's Setup section (numpy, scipy) and ffmpeg.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import os
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, find_peaks

# Full rate on purpose: telling a drum-machine hat from a sampled cymbal
# depends on content above 11 kHz that a 22 kHz decode has already discarded.
SR = 44100


# --------------------------------------------------------------------------
# io / dsp helpers
# --------------------------------------------------------------------------

def load(path: str, dur: float = 90, ss: float = 30) -> np.ndarray:
    """Decode mono at full rate. Strips cover art via explicit -map 0:a:0."""
    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(ss), "-t", str(dur), "-i", path,
         "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SR),
         "-acodec", "pcm_s16le", tmp, "-y"],
        check=True,
    )
    _, x = wavfile.read(tmp)
    os.unlink(tmp)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x.astype(np.float64) / 32768.0


def band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    ny = SR / 2
    sos = butter(4, [max(lo, 20) / ny, min(hi, ny - 500) / ny],
                 btype="band", output="sos")
    return sosfilt(sos, x)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)))


def avg_spectrum(x: np.ndarray, N: int = 8192):
    acc = np.zeros(N // 2 + 1)
    n = 0
    win = np.hanning(N)
    for i in range(0, max(len(x) - N, 1), N // 2):
        seg = x[i:i + N]
        if len(seg) < N:
            break
        m = np.abs(np.fft.rfft(seg * win))
        if m.sum() > 1e-6:
            acc += m
            n += 1
    return np.fft.rfftfreq(N, 1 / SR), acc / max(n, 1)


def flatness(x: np.ndarray, lo: float, hi: float) -> float:
    """Geometric/arithmetic mean ratio. High = noise, low = tonal partials."""
    f, a = avg_spectrum(x)
    m = (f > lo) & (f < hi)
    if not m.any() or a[m].sum() <= 0:
        return float("nan")
    g = np.exp(np.mean(np.log(a[m] + 1e-12)))
    return float(g / np.mean(a[m]))


def centroid(x: np.ndarray, N: int = 4096) -> float:
    """BUG-FIX 3: floor tiny bins, take median across frames."""
    vals = []
    win = np.hanning(N)
    for i in range(0, max(len(x) - N, 1), N * 2):
        seg = x[i:i + N]
        if len(seg) < N:
            break
        m = np.abs(np.fft.rfft(seg * win))
        if m.sum() < 1e-5:
            continue
        m = np.where(m < m.max() * 0.02, 0, m)   # <- the fix
        if m.sum() <= 0:
            continue
        f = np.fft.rfftfreq(N, 1 / SR)
        vals.append((f * m).sum() / m.sum())
    return float(np.median(vals)) if vals else float("nan")


HOP = 512


def envelope(x: np.ndarray) -> np.ndarray:
    n = len(x) // HOP
    return np.array([rms(x[i * HOP:(i + 1) * HOP]) for i in range(n)])


def onsets(x: np.ndarray, pct: float = 97) -> np.ndarray:
    """BUG-FIX 2: threshold from this band's own flux distribution."""
    e = envelope(x)
    flux = np.maximum(0, np.diff(e))
    if flux.size == 0 or flux.max() <= 0:
        return np.array([], dtype=int)
    thr = max(np.percentile(flux, pct), flux.max() * 0.08)
    idx = np.where(flux >= thr)[0]
    keep: list[int] = []
    min_gap = (SR / HOP) * 0.08
    for i in idx:
        if not keep or i - keep[-1] > min_gap:
            keep.append(int(i))
    return np.array(keep, dtype=int)


def decay_ms(x: np.ndarray, ons: np.ndarray, limit: int = 120) -> float:
    """BUG-FIX 1: find the real peak first, then measure the fall to -20 dB."""
    out = []
    smooth_n = max(int(SR * 0.005), 1)
    for o in ons[:limit]:
        s = o * HOP
        seg = np.abs(x[s:s + int(SR * 1.5)])
        if len(seg) < 2000:
            continue
        head = seg[:int(SR * 0.08)]          # search window for the true peak
        if not len(head):
            continue
        pk_i = int(np.argmax(head))
        pk = seg[pk_i]
        if pk < 2e-4:
            continue
        tail = seg[pk_i:]
        sm = np.convolve(tail, np.ones(smooth_n) / smooth_n, mode="same")
        below = np.where(sm < pk * 0.1)[0]
        if len(below):
            out.append(below[0] / SR * 1000)
    return float(np.median(out)) if out else float("nan")


# --------------------------------------------------------------------------
# classifiers
# --------------------------------------------------------------------------

def profile_kick(x: np.ndarray) -> list[str]:
    k = band(x, 25, 250)
    ons = onsets(k)
    if len(ons) < 3:
        return ["  kick: too few onsets to classify"]

    hits = []
    for o in ons[:40]:
        s = o * HOP
        seg = x[s:s + int(SR * 0.5)]
        if len(seg) >= 4096:
            hits.append(seg)
    if not hits:
        return ["  kick: no usable hits"]

    L = min(len(h) for h in hits)
    avg = np.mean([h[:L] for h in hits], axis=0)

    f, a = avg_spectrum(avg, N=4096)
    lo = (f > 30) & (f < 400)
    dom = f[lo][np.argmax(a[lo])] if lo.any() else float("nan")

    # pitch glide: attack vs body
    f1, a1 = avg_spectrum(avg[:int(SR * 0.04)], N=2048)
    f2, a2 = avg_spectrum(avg[int(SR * 0.04):int(SR * 0.16)], N=2048)
    m1 = (f1 > 30) & (f1 < 400)
    m2 = (f2 > 30) & (f2 < 400)
    d1 = f1[m1][np.argmax(a1[m1])] if m1.any() else float("nan")
    d2 = f2[m2][np.argmax(a2[m2])] if m2.any() else float("nan")
    glide = d1 > d2 * 1.25

    click = rms(band(avg, 2000, 8000)) / max(rms(avg), 1e-9)

    if glide:
        verdict, phrase = "808 / sub kick", "deep 808 kick with pitch-bent sub"
    elif click > 0.06:
        verdict = "layered house kick (sub body + clicky transient)"
        phrase = "punchy layered house kick with clicky attack"
    else:
        verdict, phrase = "soft / acoustic kick", "soft rounded kick"

    return [
        f"  fundamental   {dom:.0f} Hz",
        f"  pitch glide   {d1:.0f} -> {d2:.0f} Hz  ({'GLIDES DOWN' if glide else 'stable'})",
        f"  click/body    {click:.3f}",
        f"  decay         {decay_ms(k, ons):.0f} ms",
        f"  => {verdict}",
        f"  PROMPT: {phrase}",
    ]


def profile_hats(x: np.ndarray) -> list[str]:
    h = band(x, 5000, 16000)
    fl = flatness(h, 4000, 16000)
    cen = centroid(h)
    machine = fl > 0.35
    return [
        f"  centroid      {cen:.0f} Hz",
        f"  flatness      {fl:.3f}",
        f"  => {'white-noise drum machine (808/909)' if machine else 'metallic / sampled acoustic cymbal'}",
        f"  PROMPT: {'white-noise drum-machine hi-hats, 909 hats' if machine else 'crisp metallic sampled hi-hats'}",
    ]


def profile_snare(x: np.ndarray) -> list[str]:
    s = band(x, 150, 3000)
    fl = flatness(s, 150, 3000)
    f, a = avg_spectrum(s)
    m = (f > 150) & (f < 3000)
    pk, _ = find_peaks(a[m], height=a[m].max() * 0.25, distance=6)
    peaks = [f"{f[m][p]:.0f}Hz" for p in pk[:5]]
    noisy = fl > 0.3
    return [
        f"  flatness      {fl:.3f}",
        f"  peaks         {', '.join(peaks) if peaks else 'none'}",
        f"  => {'noise clap / snare' if noisy else 'tuned percussion'}",
        f"  PROMPT: {'layered noise claps on the offbeat' if noisy else 'tuned percussive hits'}",
    ]


def profile_bass(x: np.ndarray) -> list[str]:
    sub = rms(band(x, 30, 90))
    harm = rms(band(x, 200, 1500))
    ratio = sub / max(harm, 1e-9)
    f, a = avg_spectrum(x)
    m = (f > 30) & (f < 1200)
    pk, _ = find_peaks(a[m], height=a[m].max() * 0.06, distance=6)
    order = np.argsort(a[m][pk])[::-1][:6]
    partials = sorted(float(f[m][pk[i]]) for i in order)
    ons = onsets(x)
    dm = decay_ms(x, ons)
    sine = ratio > 3

    lines = [
        f"  partials      {', '.join(f'{p:.0f}Hz' for p in partials[:6])}",
        f"  sub/harmonic  {ratio:.2f}",
        f"  centroid      {centroid(x):.0f} Hz",
        f"  decay         {dm:.0f} ms",
        f"  => {'pure sine / 808 sub (few harmonics)' if sine else 'harmonically rich — saw / square / reese'}",
    ]
    if sine:
        lines.append("  PROMPT: deep pure sine sub-bass, no distortion on the low end")
        lines.append("  NOTE: source owns 30-90 Hz. A generated sine sub will phase-cancel")
        lines.append("        against it — mute the original bass stem or high-pass the new one.")
    else:
        lines.append("  PROMPT: detuned gritty reese bass, harmonically rich low end")
    if not np.isnan(dm) and dm < 200:
        lines.append(f"  PROMPT: short plucky bass stabs, no long sustained notes ({dm:.0f} ms decay)")
    return lines


def profile_other(x: np.ndarray) -> list[str]:
    f, a = avg_spectrum(x)
    m = (f > 150) & (f < 6000)
    pk, _ = find_peaks(a[m], height=a[m].max() * 0.06, distance=6)
    order = np.argsort(a[m][pk])[::-1][:8]
    partials = sorted(float(f[m][pk[i]]) for i in order)
    fl = flatness(x, 150, 8000)
    ons = onsets(x)
    dm = decay_ms(x, ons)

    # harmonic spacing test: are partials near-integer multiples of the lowest?
    harmonic = False
    if len(partials) >= 3 and partials[0] > 0:
        ratios = [p / partials[0] for p in partials[:5]]
        harmonic = all(abs(r - round(r)) < 0.12 for r in ratios)

    sustained = (not np.isnan(dm)) and dm > 400
    lines = [
        f"  partials      {', '.join(f'{p:.0f}Hz' for p in partials[:6])}",
        f"  flatness      {fl:.3f}",
        f"  centroid      {centroid(x):.0f} Hz",
        f"  decay         {dm:.0f} ms",
        f"  spacing       {'harmonic' if harmonic else 'inharmonic'}",
        f"  => {'sustained tonal pad/keys' if sustained else 'percussive synth stabs'}",
    ]
    lines.append(
        "  PROMPT: warm sustained pads, evolving chords" if sustained
        else "  PROMPT: dry inharmonic synth pluck stabs, staccato and clipped"
    )
    return lines


ROLES = {
    "drums": lambda x: (["KICK"] + profile_kick(x)
                        + ["", "HATS"] + profile_hats(x)
                        + ["", "SNARE / CLAP"] + profile_snare(x)),
    "bass": lambda x: ["BASS"] + profile_bass(x),
    "other": lambda x: ["CHORDS / STABS"] + profile_other(x),
    "vocals": lambda x: ["VOCALS — skipped (timbre profiling targets instruments)"],
}


def infer_role(name: str) -> str | None:
    n = name.lower()
    for role in ROLES:
        if role in n:
            return role
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="stem file, or a directory of stems")
    ap.add_argument("--role", choices=sorted(ROLES),
                    help="override; inferred from filename otherwise")
    ap.add_argument("--start", type=float, default=30, help="seconds in (default 30)")
    ap.add_argument("--dur", type=float, default=90, help="seconds to analyse (default 90)")
    args = ap.parse_args()

    p = Path(args.path)
    targets: list[tuple[Path, str]] = []

    if p.is_dir():
        for f in sorted(p.iterdir()):
            if f.suffix.lower() not in (".mp3", ".wav", ".flac", ".m4a"):
                continue
            role = args.role or infer_role(f.name)
            if role:
                targets.append((f, role))
        if not targets:
            sys.exit(f"no recognisable stems in {p} (expect drums/bass/other in filenames)")
    else:
        role = args.role or infer_role(p.name)
        if not role:
            sys.exit(f"cannot infer role from {p.name!r} — pass --role")
        targets.append((p, role))

    print("=" * 70)
    print(f"TIMBRE PROFILE   {SR} Hz, {args.dur:.0f}s from {args.start:.0f}s")
    print("=" * 70)

    for f, role in targets:
        print(f"\n### {f.name}  (role: {role})")
        try:
            x = load(str(f), dur=args.dur, ss=args.start)
        except subprocess.CalledProcessError:
            print("  decode failed")
            continue
        if rms(x) < 1e-5:
            print("  silent in this window — try a different --start")
            continue
        for line in ROLES[role](x):
            print(line if line.startswith(" ") or not line else f"{line}")

    print("\nThresholds and rationale: references/timbre-identification.md")


if __name__ == "__main__":
    main()
