# Audio remix, stem separation, and locally-synthesized production

Companion to the video-oriented references. Covers the **audio** branch of a
generative media pipeline: separating an existing recording, restyling it, and
synthesizing replacement elements locally when hosted models cannot reach the
required fidelity.

Everything here is measured, from a session remixing a commercial track into a
trap arrangement while preserving the original vocal.

---

## 1. Route selection decides everything

Ask one question before touching any API: **must the original recording survive?**

| Goal | Route | Original recording |
|---|---|---|
| Same song, different singer | stem separation + RVC voice conversion | instrumental preserved |
| Same song, different arrangement, **keep original vocal** | separate → restyle instrumental → remux vocal | vocal preserved |
| Original vocal over a bed made **elsewhere** (Suno, a DAW) | separate → beat-match → remux (§10) | vocal preserved |
| Melody into a wholly new arrangement | score-conditioned generation (YuE2 class) | nothing preserved |
| New song in a style | text-to-music | nothing preserved |

The external-bed route (§10) is usually where this lands once hosted restyle
fails the fidelity bar (§2) and local synthesis proves laborious (§4). The
human picks the backing track; the pipeline only has to align and mix.

Getting this wrong wastes the whole run. A user asked to "remix this song but
keep the original vocals" — a score-conditioned cover model was the wrong tool
because it regenerates **both** backing track and vocals synthetically. The
requirement excluded the entire category before any cost question arose.

Corollary: when the original vocal is preserved, **lyrics are not needed at
all.** Requesting them is a tell that the route was misidentified.

---

## 2. Verify what a model EMITS, not only what it accepts

The most expensive mistake in this session. Model selection checked whether
each candidate had an audio input — a necessary but badly insufficient test.

MusicGen-family models emit **32 kHz / ~48 kbps**. That is architectural, not a
quality setting:

```
source material    44100 Hz / 192 kbps
musicgen output    32000 Hz /  48 kbps
```

Everything above ~16 kHz is gone. The result is dull hi-hats, no air, smeared
low end — and layering a clean 44.1 kHz vocal stem on top makes the mismatch
*more* audible, not less, because the ear gets a direct A/B within one mix.

The user's verdict was "that doesn't sound good at all," and they were right.

**Check `sample_rate` and `bit_rate` on a real output before recommending a
route:**

```bash
ffprobe -v error -show_entries stream=sample_rate,bit_rate \
        -show_entries format=bit_rate -of default=nw=1 out.mp3
```

Survey result for hosted instrumental restyle (all checked live):

| Model | Audio in | Notes |
|---|---|---|
| `sakemin/musicgen-remixer` | yes | 32 kHz ceiling |
| `meta/musicgen` | yes | same family, same ceiling |
| `sakemin/musicgen-chord` | yes | same family |
| `minimax/music-1.5` | **no** | 4-min songs, but text-only — cannot cover |
| `lucataco/ace-step` | **no** | no audio input |
| `riffusion/riffusion` | **no** | no audio input |

A model advertising long, high-quality output is irrelevant if it has no audio
input. Read the full input schema, not the marketing line.

---

## 3. Stem separation is the reliable primitive

`htdemucs` (Hybrid Transformer Demucs v4) separation was the one step that
worked first time, every time, and was never the weak link.

Output keys: `bass`, `drums`, `other`, `vocals`, sometimes `guitar` / `piano`
(null when the model finds none). **There is no `mixture` key.**

Verification that the separation is real, not padded copies:

```bash
md5sum *.mp3            # must differ
# identical FILE SIZES are normal — CBR encoding pads to the same length
```

Per-stem loudness is the better sanity check: distinct stems land at visibly
different mean volumes (measured -19.2 to -20.7 dB across four stems).

Rebuilding a backing track from non-vocal stems gives a restyle model full
harmonic context rather than one isolated part:

```bash
ffmpeg -i bass.mp3 -i drums.mp3 -i other.mp3 \
  -filter_complex "amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.95" \
  backing.mp3
```

### Stems are often the real deliverable

A remix attempt can end with the user routing the stems into a tool that does
the job better — Suno Studio, a DAW, anything with a human in the loop. Treat
that as a success, not an abandoned task, and hand them over properly.

Separate the **full track**, not the section that was being prototyped: a 30 s
working clip is useless downstream. File them predictably and sync to wherever
the user actually works:

```
~/music/stems/<Artist> - <Title>/{bass,drums,other,vocals}.mp3
```

Then upload to the cloud folder rather than leaving them local — a path on a
headless box is not a deliverable for someone on a phone. Say plainly whether
they have been synced, since "filed" and "accessible" are different claims and
the user will reasonably assume the latter.

---

## 4. Locally-synthesized production: event-driven, never grid-driven

When hosted restyle cannot reach the fidelity bar, synthesize the new elements
locally with numpy/scipy at full sample rate. Two bugs dominated, and the
second forced an architectural rewrite.

### 4.1 Sub-bass must actually be sub

First attempt folded detected bass pitches "into the octave below 80 Hz",
which let notes land at **78 Hz** — low-mid, not sub. Combined with heavy
saturation (`tanh(x * 2.6)`) and a 1.1 s decay, this produced exactly what the
user described as *"male bass honking… far too loud."*

Fix, all four together:

```
fold range     30-55 Hz strict     (not "anything under 80")
saturation     tanh(x * 1.5)       (was 2.6)
decay          0.7s                (was 1.1s)
low-pass       110 Hz hard         butter(4, 110, 'low')
```

Verify by measuring the stem *above* the cutoff — a correct sub stem returns
no signal at all:

```bash
ffmpeg -i sub.wav -af "highpass=f=130,volumedetect" -f null -
# expect: no mean_volume line (silence)
```

### 4.2 A fixed tempo grid ALWAYS drifts against a real performance

The user reported *"the tempo of the song gets off from the vocals later on."*
Diagnosis, in order:

1. Global BPM estimate: 129.2, then refined by least-squares to 130.7.
2. Grid phase was assumed `t=0`; the real first downbeat was at **0.306 s** —
   a constant offset on top of any rate error.
3. Best achievable grid fit: **96.6 ms RMS error**. Unusable.
4. Inter-onset intervals of the real drum stem clustered at **0.167 / 0.333 /
   0.417 s** — multiple unrelated values. The performance is syncopated with
   fills; it is not a metronome.

No fixed grid can track that. Tuning the BPM more precisely cannot help,
because there is no single period to find.

**The fix is to delete the independent clock.** Trigger every synthesized
element from onsets detected in the real drum stem:

- detect kicks in a low band (40–180 Hz) and snares in a high band
  (1200–8000 Hz) separately, so each layer reinforces its real counterpart
- space hi-hats by subdividing the interval **between consecutive real kicks**,
  so hat spacing tracks local tempo automatically
- snap synthesized bass notes to the nearest real kick within a tolerance
  (~0.14 s)
- place drops on an actual detected onset, not a wall-clock time

With no independent timebase, drift is structurally impossible rather than
merely small. This is the audio analogue of validator-owned canon: make the
illegal state unrepresentable.

### 4.3 Gain-stage before mixing

Synthesized stems normalized to peak trivially clip at 0 dBFS. Normalize each
to a headroom target before the mix:

```
808     -4 dB      kick   -5 dB     snare  -10 dB
hats   -16 dB      riser -13 dB
```

Then sidechain the instrumental bed off the vocal (`sidechaincompress`,
threshold ~0.05, ratio 3–4) so the vocal sits forward without simply being
louder.

---

## 5. ffmpeg traps that produced wrong measurements

Three separate false readings in one session, each of which looked like real
data:

1. **`-v error` suppresses `volumedetect` output.** The filter writes at info
   level, so a "quiet" invocation returns nothing and naive parsing yields a
   default. Use `-hide_banner` instead of `-v error` when parsing filter output.

2. **`astats` with `metadata=1` reports cumulative averages**, not per-block
   values, unless `reset=N` is set correctly. An energy map built from it
   showed a smooth monotonic curve that did not exist. Measure each segment
   independently with `-ss T -t N` instead.

3. **Embedded cover art is a video stream.** A downloaded mp3 carried an
   `mjpeg` stream, which breaks `-map` defaults and confuses downstream tools.
   Strip it first:

   ```bash
   ffmpeg -i in.mp3 -map 0:a:0 -vn -acodec libmp3lame -ar 44100 -b:a 192k clean.mp3
   ```

**Do not select a section by RMS energy alone.** Picking the loudest 30 s gave
a chorus when the user wanted the song's opening — "you missed the whole intro
also starting with the vocals." Loudest is not the same as representative; ask
which section, or default to the opening.

---

## 6. Source acquisition

YouTube blocks downloads from datacenter IPs with `Sign in to confirm you're
not a bot`, across every player client and on current builds. This is an access
control, and routing around it (proxies, scraper frontends) is out of scope —
particularly for commercially released material.

The workable path is **user-supplied audio**: a file attachment, or a Drive
link fetched with the existing Google OAuth credentials. Note that a `pip
install --upgrade` may silently no-op under PEP 668, so a "version is current"
conclusion needs a venv to be a real test.

---

## 7. Licensing

- Source recordings by commercial artists: personal remixing is one thing,
  distribution or monetisation needs clearance. State this once, plainly, when
  output heads anywhere public.
- YuE2 / SheetSage2 weights are **CC BY-NC 4.0** — non-commercial regardless of
  where they run. Rented hardware does not change the licence.
- Do not fetch and reproduce copyrighted lyrics to feed a pipeline. Either the
  user supplies them, they are written original, or the material is public
  domain. When the original vocal is preserved, the question does not arise
  (§1).

---

## 8. Deriving a generation prompt from a reference track

When asked for a "prompt in the style of X", measure X instead of describing it
from impression. Genre labels are the least reliable part of a music prompt;
numbers translate directly into the vocabulary generators respond to.

### Getting the audio

Streaming pages are JS-rendered, so scraping the track page yields nothing
useful. The **embed** endpoint carries a `__NEXT_DATA__` JSON blob with title,
artists, release date, duration and often a preview URL:

```
https://open.spotify.com/embed/track/<id>
```

The plain `/oembed` endpoint returns a title with **no artist**, which is not
enough to identify a track. Parse the embed payload instead. A 15–30 s preview
is enough for tempo and spectral character, though not for arrangement.

### What to measure

```
tempo          onset-envelope autocorrelation, 60-180 BPM window
onset density  onsets/sec — busy vs sparse percussion
crest factor   20*log10(peak/rms) — under 10 dB is a loud, heavily
               limited modern master; over 14 dB is dynamic
spectral split % of total energy in sub / bass / low-mid / mid / hi-mid / air
key            strongest pitch classes via harmonic-summed chroma
```

The **spectral split is the most useful and the least guessable.** One measured
reference came back with 29.5% of its energy above 6 kHz and only 4.6% below
60 Hz — a bright, top-heavy record, not the bass-weighted one the genre label
would have implied. Writing "heavy sub bass" into that prompt would have been
wrong in the most audible way.

### Translating numbers into prompt language

Each phrase should trace to a measurement, and say so when presenting it:

| Measurement | Prompt phrase |
|---|---|
| 121.6 BPM | `122 BPM` (state it; generators honour explicit tempo) |
| sub 4.6%, bass 12.6% | `tight controlled sub-bass, no boom` |
| air 29.5% | `sparkling high-end sheen, shimmering hats` |
| crest 9.6 dB | `loud modern master, heavily compressed and forward` |
| chroma C#/G#/D | `C# minor` |
| 5.3 onsets/sec | `busy percussion, driving pulse` |

Offer a long form and a short form — prompt fields are often length-limited,
and the short form should keep tempo, key, the low-end character and the
brightness, dropping adjectives first.

**State the sampling caveat.** A 15 s preview is one slice, usually the densest
part. Tempo, key and spectral balance hold across a track; arrangement, drop
dynamics and section contrast do not. Say which claims are which rather than
presenting a whole-track analysis that was measured on a fragment.

### Resolving a contradictory style brief

Briefs routinely pull two ways — "upbeat and energetic but also darker and
grimier" is a normal request and a real tension. Prompting both moods directly
averages them into sludge.

**Split the brief across dimensions that do not compete:**

```
energy     -> rhythm      driving, syncopated hats, relentless forward pulse
darkness   -> harmony     minor key
grime      -> timbre      distorted reese bass, gritty metallic textures
```

Each attribute lands somewhere different in the mix, so none cancels another.

Two further rules that raised prompt quality measurably:

- **Name the synthesis technique, not the adjective.** `reese bass` (a detuned,
  phasing sawtooth) is far more actionable than "menacing bass"; `808 with
  pitch glides` beats "heavy sub".
- **Describe a drop as an event, not as loudness.** "Heavy drops" gets read as
  constant volume. "Tight filtered build into a drop where the bass fully
  detunes and snarls" describes a transition the model can actually stage.

Anchor the tempo to the **measured** source BPM when the output must sit
alongside existing material — a guessed tempo (140 assumed against a real
129–130) puts the generated groove outside the vocal's natural pocket.

---

## 10. Beat-matching a preserved vocal onto an external bed

The endgame of the "remix but keep the vocals" brief. The user brings a backing
track from a generator or DAW; the job is to align two independently-produced
recordings and mix them. No GPU, no API beyond the one separation call.

### 10.1 Resolve the tempo octave before anything else

Onset autocorrelation returns half or double the true tempo routinely. Measured
here: a 130 BPM dance track reported **67 BPM**, and naive peak-picking on raw
onsets gave **295 BPM** because it fired on hats and sub-events rather than
beats.

Take the autocorrelation peak, then score each octave candidate by how much
low-band (40–150 Hz) **kick** energy lands on its grid:

```python
def grid_score(bpm, low_env, fps):
    beat = 60.0 / bpm
    best = -1e9
    for ph in np.arange(0, beat, beat / 32):
        idx = ((np.arange(ph, len(low_env) / fps, beat)) * fps).astype(int)
        idx = idx[idx < len(low_env)]
        if len(idx) >= 8:
            best = max(best, low_env[idx].mean())
    return best

bpm = max((grid_score(c, low, fps), c)
          for c in {raw / 2, raw, raw * 2} if 60 <= c <= 200)[1]
```

**Cross-check against an independent pipeline when one exists.** YuE2's
`save_score` ABC header carries `Q:1/4=<bpm>` from SheetSage2's own analysis;
it agreeing with a local measurement (130 in both) is far stronger evidence
than either alone. An early guess of 140 BPM, made before measuring, was the
root cause of a mix that sat wrong against the vocal.

### 10.2 Align

```python
stretch = target_bpm / bed_bpm     # atempo is transparent within ~0.95-1.05
offset  = bed_first_kick / stretch - vocal_first_phrase
```

- `first_kick` — first strong peak of a 40–150 Hz onset envelope.
- `first_phrase` — first **sustained** 200–4000 Hz energy. Require persistence
  over ~200 ms or breaths and noise trigger it.

**A negative offset would clip the vocal intro.** Never truncate; push forward
whole bars until positive:

```python
bar = 4 * 60.0 / bpm
while offset < 0:
    offset += bar
```

### 10.3 Mix

`atempo` preserves pitch; `adelay` takes milliseconds per channel. High-pass
the vocal at ~95 Hz to clear room for the sub, cut ~2.5 dB at 280 Hz (mud),
and sidechain the bed off the vocal rather than just raising the vocal:

```
[bed][vkey]sidechaincompress=threshold=0.05:ratio=3.5:attack=6:release=200:makeup=1.05
```

### 10.4 Verify, and report the number honestly

Measure kick spacing against the target grid and state the result:

```python
err = [abs(g / beat - round(g / beat)) * beat * 1000 for g in np.diff(kicks)]
# under ~25 ms = tight;  100 ms+ = audibly loose
```

Two beds generated by a text-to-music tool measured **163 ms** and **101 ms**
mean grid error after alignment. Generated backing tracks frequently have loose
internal timing that **drifts**, and a single global offset corrects constant
lag, not drift. When the measurement says loose, say so rather than calling the
job beat-matched — the honest report is the deliverable, and the real fix is
multi-anchor time-warping between detected downbeats on both sides.

---

## 11. Cost reference

Measured, small-scale:

```
stem separation, 30s        ~$0.01
stem separation, full 3min  ~$0.02
musicgen restyle, 30s       ~$0.04   (146s wall)
local synthesis             $0       numpy/scipy, seconds
```

Local synthesis being free and instant is the argument for reaching for it
before a rented GPU — iterate on 808 decay, hat density and drop placement at
no cost, then spend only if the approach itself is wrong.
