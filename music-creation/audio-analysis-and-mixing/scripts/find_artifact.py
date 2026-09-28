#!/usr/bin/env python3
"""
Locate an unwanted artifact in a separated stem, and decide whether it is
bleed (fixable by re-separating) or real content (not fixable by EQ).

    /tmp/aenv/bin/python find_artifact.py stem.mp3 --bad 0:25 --good 120:160

Compares the NORMALISED spectrum of a region where the artifact is audible
against one where it is not. Normalising each region to its own total compares
spectral SHAPE rather than level, so a loud section does not dominate.

A band with a high early/late ratio is the artifact's home. If several
different separator models all leave it, it is genuinely part of that source
and must be edited in time, not frequency.
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
from scipy.io import wavfile

SR = 44100
NFFT = 16384

BANDS = [(20, 40), (40, 60), (60, 80), (80, 100), (100, 130), (130, 160),
         (160, 200), (200, 250), (250, 320), (320, 400), (400, 500),
         (500, 650), (650, 800), (800, 1000), (1000, 1500), (1500, 2500),
         (2500, 4000), (4000, 8000)]


def seg(path, start, dur):
    tmp = os.path.join(tempfile.gettempdir(), '_artifact_tmp.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(dur),
                    '-i', path, '-map', '0:a:0', '-vn', '-ac', '1',
                    '-ar', str(SR), '-c:a', 'pcm_s16le', tmp, '-y'], check=True)
    _, x = wavfile.read(tmp)
    return x.astype(np.float64) / 32768.0


def spectrum(y):
    if len(y) < NFFT:
        y = np.pad(y, (0, NFFT - len(y)))
    w = y[:NFFT] * np.hanning(NFFT)
    return np.fft.rfftfreq(NFFT, 1 / SR), np.abs(np.fft.rfft(w, NFFT))


def avg_spectrum(path, start, end, step=2.0, dur=1.0):
    acc, n, freqs = None, 0, None
    for t in np.arange(start, end, step):
        freqs, s = spectrum(seg(path, t, dur))
        acc = s if acc is None else acc + s
        n += 1
    return freqs, acc / max(n, 1)


def parse_range(s):
    a, b = s.split(':')
    return float(a), float(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--bad', required=True, help='START:END where artifact is present')
    ap.add_argument('--good', required=True, help='START:END where it is absent')
    a = ap.parse_args()

    if not os.path.exists(a.path):
        sys.exit(f"not found: {a.path}")

    b0, b1 = parse_range(a.bad)
    g0, g1 = parse_range(a.good)

    print(f"artifact region {b0:.0f}-{b1:.0f}s ...")
    freqs, bad = avg_spectrum(a.path, b0, b1)
    print(f"clean region    {g0:.0f}-{g1:.0f}s ...")
    _, good = avg_spectrum(a.path, g0, g1)

    bad_n = bad / (bad.sum() + 1e-12)
    good_n = good / (good.sum() + 1e-12)
    ratio = (bad_n + 1e-12) / (good_n + 1e-12)

    print("\nband            ratio   share   (ratio >> 1 = artifact lives here)")
    rows = []
    for lo, hi in BANDS:
        m = (freqs >= lo) & (freqs < hi)
        r = float(ratio[m].mean())
        pct = 100 * float(bad_n[m].sum())
        rows.append((r, lo, hi, pct))
        bar = '#' * int(min(40, max(0, (r - 1) * 12)))
        print(f"  {lo:>5}-{hi:<5} Hz  {r:5.2f}  {pct:5.2f}%  {bar}")

    print("\nmost likely artifact bands:")
    for r, lo, hi, pct in sorted(rows, reverse=True)[:4]:
        print(f"   {lo}-{hi} Hz   ratio {r:.2f}")

    print("\nNEXT STEP -- do not reach for EQ yet.")
    print("  Re-separate with 2+ models (ryan5453/demucs exposes htdemucs,")
    print("  htdemucs_ft, hdemucs_mmi, mdx_extra_q; use stem=vocals, shifts=5).")
    print("  Measure this band on each result:")
    top = sorted(rows, reverse=True)[0]
    print(f"    ffmpeg -hide_banner -ss {b0:.0f} -t 15 -i STEM \\")
    print(f"      -af 'bandpass=f={(top[1]+top[2])//2}:width_type=h:w={top[2]-top[1]},volumedetect' \\")
    print( "      -f null - 2>&1 | grep mean_volume")
    print("  Models differ  -> bleed; keep the best separation.")
    print("  Models agree   -> real content; edit in TIME (trim/gate), not EQ.")


if __name__ == '__main__':
    main()
