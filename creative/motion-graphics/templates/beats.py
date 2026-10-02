# beats.py — measure a supplied track so the animation can cut on it.
# Usage: python beats.py audio/track.wav > beats.json
# Needs: numpy, librosa, soundfile (pip install in a venv; PEP 668 systems block global pip).
# Adapted from @0xMovez's course (2026-09-27).
import json
import sys

import librosa
import numpy as np

y, sr = librosa.load(sys.argv[1], sr=None, mono=True)
tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
beats = librosa.frames_to_time(frames, sr=sr).round(3).tolist()

onset = librosa.onset.onset_strength(y=y, sr=sr)
peaks = librosa.util.peak_pick(onset, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.5, wait=10)
json.dump({
    "bpm": float(np.atleast_1d(tempo)[0]),
    "beats": beats,                                                   # state changes go here
    "downbeats": beats[::4],                                          # big moments go here (assumes 4/4, beat 1 = first detected beat: check it)
    "hits": librosa.frames_to_time(peaks, sr=sr).round(3).tolist(),   # SFX go here
    "duration": round(len(y) / sr, 3),
    "source": sys.argv[1],
}, sys.stdout, indent=1)
