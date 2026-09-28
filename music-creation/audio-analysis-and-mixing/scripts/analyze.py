#!/usr/bin/env python3
"""
Analyze an audio file: tempo (octave-resolved), key, spectral balance,
dynamics, onset density.

    python3 -m venv /tmp/aenv && /tmp/aenv/bin/pip install -q numpy scipy
    /tmp/aenv/bin/python analyze.py song.mp3 [--seconds 120]

Every number printed here is measured. Do not report tempo or key to a user
without running something like this first.
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, find_peaks

SR = 44100
HOP = 256
FPS = SR / HOP
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def decode(path, seconds=None, start=0.0):
    """Mono 16-bit at SR. s16 avoids the int24 scaling trap."""
    tmp = os.path.join(tempfile.gettempdir(), '_analyze_tmp.wav')
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(start), '-i', path,
           '-map', '0:a:0', '-vn', '-ac', '1', '-ar', str(SR),
           '-c:a', 'pcm_s16le']
    if seconds:
        cmd += ['-t', str(seconds)]
    subprocess.run(cmd + [tmp, '-y'], check=True)
    _, x = wavfile.read(tmp)
    return x.astype(np.float64) / 32768.0


def duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def band_env(y, lo, hi):
    """Normalised positive spectral flux in a band."""
    sos = butter(4, [lo, hi], btype='band', fs=SR, output='sos')
    b = sosfilt(sos, y)
    fr = len(b) // HOP
    e = np.array([np.sqrt(np.mean(b[i * HOP:(i + 1) * HOP] ** 2))
                  for i in range(fr)])
    e = np.maximum(0, np.diff(e, prepend=e[0]))
    return (e - e.mean()) / (e.std() + 1e-9)


def tempo(y):
    """
    Autocorrelation peak, then resolve the octave by checking which candidate
    grid best explains low-band kick energy. The raw peak is frequently an
    octave out -- never report it directly.
    """
    full = band_env(y, 50, 6000)
    low = band_env(y, 40, 150)
    ac = np.correlate(full, full, 'full')[len(full) - 1:]

    best = (-1e9, 120.0)
    for bpm in np.arange(60, 200.01, 0.05):
        i = int(round(60.0 * FPS / bpm))
        if 2 <= i < len(ac) and ac[i] > best[0]:
            best = (ac[i], bpm)
    raw = best[1]

    def grid_score(bpm):
        beat = 60.0 / bpm
        top = -1e9
        for ph in np.arange(0, beat, beat / 32):
            idx = ((np.arange(ph, len(low) / FPS, beat)) * FPS).astype(int)
            idx = idx[idx < len(low)]
            if len(idx) >= 8:
                top = max(top, low[idx].mean())
        return top

    cands = sorted({round(raw / 2, 2), round(raw, 2), round(raw * 2, 2)})
    scored = sorted(((grid_score(c), c) for c in cands if 60 <= c <= 200),
                    reverse=True)

    # least-squares refinement against strong onsets
    pk, _ = find_peaks(full, height=1.0, distance=int(FPS * 0.14))
    ons = pk / FPS
    chosen = scored[0][1] if scored else raw
    phase = 0.0
    if len(ons) > 8:
        strong = ons[:200]
        fit = (1e9, chosen, 0.0)
        for c in np.arange(chosen - 1.5, chosen + 1.5, 0.02):
            beat = 60.0 / c
            for ph in np.arange(0, beat, beat / 32):
                k = np.round((strong - ph) / beat)
                err = np.mean((strong - (ph + k * beat)) ** 2)
                if err < fit[0]:
                    fit = (err, c, ph)
        _, chosen, phase = fit
    return raw, scored, chosen, phase, len(ons)


def spectral(y):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    freqs = np.fft.rfftfreq(len(y), 1 / SR)
    total = spec.sum() + 1e-12
    bands = [("sub 20-60", 20, 60), ("bass 60-150", 60, 150),
             ("lowmid 150-400", 150, 400), ("mid 400-2k", 400, 2000),
             ("hi-mid 2k-6k", 2000, 6000), ("air 6k-16k", 6000, 16000)]
    out = []
    for name, f0, f1 in bands:
        m = (freqs >= f0) & (freqs < f1)
        out.append((name, 100 * spec[m].sum() / total))
    return out, spec, freqs


def key_of(spec, freqs):
    chroma = np.zeros(12)
    m = (freqs > 55) & (freqs < 2000)
    for f, s in zip(freqs[m], spec[m]):
        midi = 69 + 12 * np.log2(f / 440.0)
        chroma[int(round(midi)) % 12] += s
    if chroma.max() > 0:
        chroma /= chroma.max()
    return [NOTES[i] for i in np.argsort(chroma)[::-1][:5]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--seconds', type=float, default=120)
    ap.add_argument('--start', type=float, default=0)
    a = ap.parse_args()

    if not os.path.exists(a.path):
        sys.exit(f"not found: {a.path}")

    total = duration(a.path)
    y = decode(a.path, a.seconds, a.start)
    print(f"file      : {os.path.basename(a.path)}")
    print(f"length    : {total:.1f}s   analyzing {len(y)/SR:.1f}s "
          f"from {a.start:.0f}s")
    print(f"peak      : {20*np.log10(np.abs(y).max()+1e-12):.1f} dBFS\n")

    raw, scored, bpm, phase, n_ons = tempo(y)
    print(f"tempo     : {bpm:.2f} BPM        (half-time feel {bpm/2:.1f})")
    print(f"  raw autocorrelation peak {raw:.2f} BPM -- octave candidates:")
    for s, c in scored:
        mark = '  <- chosen' if abs(c - round(bpm, 2)) < 1.6 else ''
        print(f"     {c:7.2f} BPM  kick-grid score {s:+.3f}{mark}")
    print(f"  first downbeat ~{phase:.3f}s")
    print(f"  onsets {n_ons} ({n_ons/(len(y)/SR):.1f}/s)\n")

    bands, spec, freqs = spectral(y)
    print("spectral balance:")
    for name, pct in bands:
        print(f"  {name:<16} {pct:5.1f}%  {'#' * int(pct * 1.2)}")

    rms = np.sqrt(np.mean(y ** 2))
    peak = np.abs(y).max()
    crest = 20 * np.log10(peak / (rms + 1e-9))
    verdict = ('heavily compressed' if crest < 10
               else 'moderate' if crest < 14 else 'dynamic')
    print(f"\nRMS       : {20*np.log10(rms+1e-12):.1f} dBFS")
    print(f"crest     : {crest:.1f} dB  ({verdict})")
    print(f"pitch set : {', '.join(key_of(spec, freqs))}")

    print("\nprompt hints:")
    sub = dict(bands)['sub 20-60']
    air = dict(bands)['air 6k-16k']
    print(f"  {'tight controlled sub, no boom' if sub < 8 else 'deep heavy sub-bass'}")
    print(f"  {'sparkling high-end sheen' if air > 20 else 'warm rolled-off top end'}")
    print(f"  {'loud modern master, heavily compressed' if crest < 10 else 'open dynamics'}")
    print(f"  {bpm:.0f} BPM")


if __name__ == '__main__':
    main()
