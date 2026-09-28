#!/usr/bin/env python3
"""
Synthesize a trap production bed locked to a song's real tempo and bassline.

Prereqs: separated stems as i_drums.mp3 / i_bass.mp3 in WORKDIR, plus
    python3 -m venv aenv && ./aenv/bin/pip install numpy scipy

Usage:
    ./aenv/bin/python trap_synth.py --workdir /tmp/remix --duration 40 --drop 20

Writes t_808 / t_kick / t_snare / t_hats / t_riser as normalised 44.1kHz wavs,
ready to mix against the original vocal stem. See references/local-synthesis.md
for the mixing chain.
"""
import argparse
import json
import subprocess

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, find_peaks

SR = 44100

# mix-ready peak targets, dBFS — raw synth output clips when summed
TARGETS = {'t_808': -3.0, 't_kick': -4.0, 't_snare': -8.0,
           't_hats': -14.0, 't_riser': -12.0}


def load(path):
    wav = str(path).replace('.mp3', '.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1',
                    '-ar', str(SR), wav, '-y'], check=True)
    _, x = wavfile.read(wav)
    return x.astype(np.float64) / 32768.0


def env_ad(n, attack, decay, curve=2.5):
    a = max(1, int(attack * SR))
    e = np.zeros(n)
    e[:a] = np.linspace(0, 1, a)
    if n - a > 0:
        e[a:] = np.exp(-np.linspace(0, curve, n - a))
    return e


def detect_tempo(drums):
    """Positive spectral flux + autocorrelation. Never guess the tempo."""
    sos = butter(4, [60, 4000], btype='band', fs=SR, output='sos')
    y = sosfilt(sos, drums)
    hop = 512
    env = np.array([np.sqrt(np.mean(y[i*hop:(i+1)*hop]**2))
                    for i in range(len(y) // hop)])
    env = np.maximum(0, np.diff(env, prepend=env[0]))
    env = (env - env.mean()) / (env.std() + 1e-9)

    ac = np.correlate(env, env, mode='full')[len(env)-1:]
    fps = SR / hop
    lo, hi = int(fps * 60 / 180), int(fps * 60 / 70)
    bpm = 60.0 * fps / (int(np.argmax(ac[lo:hi])) + lo)
    peaks, _ = find_peaks(env, height=1.2, distance=int(fps * 0.12))
    return bpm, peaks / fps


def track_bass(bass, beats):
    """Dominant low-band partial per onset -> 808 pitches that follow the song."""
    sos = butter(4, 250, btype='low', fs=SR, output='sos')
    y = sosfilt(sos, bass)
    freqs = np.fft.rfftfreq(8192, 1 / SR)
    band = (freqs > 35) & (freqs < 250)
    out = []
    for t in beats:
        a, b = int(t * SR), int((t + 0.25) * SR)
        if b > len(y):
            break
        spec = np.abs(np.fft.rfft(y[a:b] * np.hanning(b - a), 8192))
        out.append({'t': float(t),
                    'hz': float(freqs[band][int(np.argmax(spec[band]))]),
                    'amp': float(spec[band].max())})
    if not out:
        return out
    thr = np.percentile([n['amp'] for n in out], 45)   # drop separation artefacts
    return [n for n in out if n['amp'] >= thr]


def sub808(freq, dur, glide=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1 + 3.0 * np.exp(-t * 28))             # the pitch drop
    if glide:
        f = f * (1 + glide * np.exp(-t * 6))
    phase = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(phase) + 0.25 * np.sin(2 * phase)       # harmonic for small speakers
    x *= env_ad(n, 0.004, dur, curve=3.2)
    return np.tanh(x * 2.6) * 0.72                     # saturate, don't clip


def kick(dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 150 * np.exp(-t * 45) + 48
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(n, 0.001, dur, curve=5.0)
    click = np.random.randn(int(0.004 * SR)) * 0.5
    x[:len(click)] += click
    return np.tanh(x * 3.2) * 0.85


def snare(dur=0.18):
    n = int(dur * SR)
    sos = butter(4, [1400, 7200], btype='band', fs=SR, output='sos')
    x = sosfilt(sos, np.random.randn(n)) * 0.8
    x += np.sin(2 * np.pi * 185 * np.arange(n) / SR) * 0.45
    return x * env_ad(n, 0.001, dur, curve=4.5) * 0.6


def hat(dur=0.045, bright=1.0):
    n = int(dur * SR)
    sos = butter(6, 7000 * bright, btype='high', fs=SR, output='sos')
    x = sosfilt(sos, np.random.randn(n))
    return x * env_ad(n, 0.0005, dur, curve=7.0) * 0.34


def place(buf, sig, t):
    i = int(t * SR)
    if i < len(buf):
        j = min(len(buf), i + len(sig))
        buf[i:j] += sig[:j - i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workdir', default='/tmp/remix')
    ap.add_argument('--duration', type=float, default=40.0)
    ap.add_argument('--drop', type=float, default=20.0,
                    help='seconds; engineered drop position')
    a = ap.parse_args()
    W, N = a.workdir, int(a.duration * SR)

    bpm, beats = detect_tempo(load(f'{W}/i_drums.mp3'))
    notes = track_bass(load(f'{W}/i_bass.mp3'), beats[:64])
    beat = 60.0 / bpm
    print(f"tempo {bpm:.1f} BPM | half-time {bpm/2:.1f} | {len(notes)} bass notes")

    b808 = np.zeros(N)
    last_t, last_hz = -9.0, None
    for nt in notes:
        if nt['t'] - last_t < beat * 0.9:      # thin: ~one per half-note
            continue
        hz = nt['hz']
        while hz > 80:                          # fold to sub octave
            hz /= 2
        if hz < 30:
            hz *= 2
        glide = 0.12 if (last_hz and abs(hz - last_hz) > 4) else 0.0
        place(b808, sub808(hz, min(beat * 1.6, 1.1), glide), nt['t'])
        last_t, last_hz = nt['t'], hz

    bk, bs, bh = np.zeros(N), np.zeros(N), np.zeros(N)
    bar, step, t = beat * 4, beat / 3, 0.0
    while t < a.duration:
        place(bk, kick(), t)                    # half-time: kick 1, snare 3
        place(bs, snare(), t + beat * 2)
        k = 0
        while k * step < bar and t + k * step < a.duration:
            pos = t + k * step
            if k % 12 == 9:                     # roll
                for r in range(4):
                    place(bh, hat(0.03, 1.15) * 0.7, pos + r * step / 4)
            else:
                place(bh, hat() * (1.0 if k % 3 == 0 else 0.62), pos)
            k += 1
        t += bar

    riser = np.zeros(N)
    rn = int(3.0 * SR)
    noise, sweep = np.random.randn(rn), np.zeros(rn)
    for i in range(0, rn, 512):
        sos = butter(2, 300 + (i / rn) * 9000, btype='high', fs=SR, output='sos')
        seg = sosfilt(sos, noise[i:i+512])
        sweep[i:i+len(seg)] = seg
    place(riser, sweep * np.linspace(0, 1, rn) ** 2 * 0.42, a.drop - 3.0)

    g0, g1 = int((a.drop - 0.28) * SR), int(a.drop * SR)   # near-silence
    for b in (b808, bk, bs, bh):
        b[g0:g1] *= np.linspace(1, 0.04, g1 - g0)
    place(b808, sub808(37.7, 1.5) * 1.15, a.drop)
    place(bk, kick(0.3) * 1.1, a.drop)

    for name, buf in (('t_808', b808), ('t_kick', bk), ('t_snare', bs),
                      ('t_hats', bh), ('t_riser', riser)):
        y = np.clip(buf, -1, 1)
        peak = np.abs(y).max()
        if peak > 0:
            y = y / peak * (10 ** (TARGETS[name] / 20))
        wavfile.write(f'{W}/{name}.wav', SR, (y * 32767).astype(np.int16))
        print(f"  {name:<8} -> {TARGETS[name]:>5.1f} dBFS")

    json.dump({'bpm': bpm, 'notes': notes}, open(f'{W}/analysis.json', 'w'))


if __name__ == '__main__':
    main()
