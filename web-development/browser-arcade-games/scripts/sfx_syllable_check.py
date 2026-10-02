"""Check that a synthesized syllabic SFX (e.g. "HA HA HA") has an audible consonant onset.

Works on the WAV written by render_sfx_pitch.py (sfx-new.wav / sfx-old.wav).
Per syllable it measures:
  - onset level vs vowel level (dB): a breathy "h" that reads should be roughly -6..-14 dB.
    Above 0 dB means noise drowns the vowel. Below -20 dB means the "h" is inaudible.
  - onset harmonicity (0..1, autocorrelation peak): low (< ~0.35) = aperiodic breath, good.
  - vowel harmonicity: high (> ~0.4) = voiced vowel, good.
  - silence gap before the syllable (dB vs vowel): lower = crisper syllable separation.
    Values near 0 mean echo/reverb is smearing into the next onset.
  - vowel f0 in 60-300 Hz. The floor ignores a deliberate sub-octave "growl" layer,
    which otherwise gets picked up as the pitch.

Usage:
  ~/.venvs/cdp/bin/python sfx_syllable_check.py <wav> <first_syllable_s> <step_s> [onset_s=0.065] [count=7]
Example (gift-game laugh: HAs start 0.6s, every 0.25s):
  sfx_syllable_check.py .test/shots/sfx-new.wav 0.6 0.25 0.065 7
Needs numpy in the venv (pip install numpy).
"""
import sys, wave
import numpy as np

path = sys.argv[1]
HA0, STEP = float(sys.argv[2]), float(sys.argv[3])
H = float(sys.argv[4]) if len(sys.argv) > 4 else 0.065
N = int(sys.argv[5]) if len(sys.argv) > 5 else 7

with wave.open(path) as w:
    SR = w.getframerate()
    s = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float) / 32768


def db(x):
    return 10 * np.log10(np.mean(x ** 2) + 1e-12)


def harmonicity(seg):
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, 'full')[len(seg) - 1:]
    if ac[0] <= 0:
        return 0.0
    return float(ac[SR // 300:SR // 60].max() / ac[0])


def f0(seg):
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, 'full')[len(seg) - 1:]
    lo, hi = SR // 300, SR // 60
    return SR / (lo + np.argmax(ac[lo:hi]))


rows = []
for k in range(N):
    st = int((HA0 + k * STEP) * SR)
    h = s[st + int(0.012 * SR): st + int((H - 0.008) * SR)]
    v = s[st + int((H + 0.035) * SR): st + int((H + 0.095) * SR)]
    gap = s[max(0, st - int(0.02 * SR)): st]
    rows.append((db(h) - db(v), harmonicity(h), harmonicity(v), db(gap) - db(v), f0(v)))

fmt = lambda i, p='.1f': ', '.join(format(r[i], p) for r in rows)
print('onset vs vowel (dB)  :', fmt(0), '  target ~ -6..-14')
print('onset harmonicity    :', fmt(1, '.2f'), '  low = breathy, good')
print('vowel harmonicity    :', fmt(2, '.2f'), '  high = voiced, good')
print('gap before syllable  :', fmt(3), '  dB vs vowel, lower = crisper')
print('vowel f0 (Hz)        :', fmt(4, '.0f'))
