---
name: audio-analysis-and-mixing
description: Measure tempo/key/stems and mix audio with ffmpeg.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [audio, ffmpeg, tempo, bpm, stems, mixing, remix, beat-matching, dsp]
    related_skills: [ai-cover-songs, wan2gp-yue2-covers, songsee]
---

# Audio Analysis and Mixing

## When to Use

Any task that needs **measured facts about audio** or **local mixing** rather
than generation. Triggers: "what BPM is this", "analyze this song", "write me a
prompt based on this track", "mix these together", "beat match", "remove that
noise from the vocal", "layer the vocals over this beat".

Pairs with generation skills: this one supplies the numbers (tempo, key,
spectral balance) that make a generation prompt accurate, and does the
final assembly afterwards.

**Measure, never guess.** A guessed 140 BPM against a real 130 BPM song
produced a remix the user rejected. Every number stated to the user should come
from a tool run in this session.

## Setup

`numpy`/`scipy` are not in the system Python (PEP 668). Make a venv once:

```bash
python3 -m venv /tmp/aenv && /tmp/aenv/bin/pip install -q numpy scipy
```

For durable work use `~/.hermes/data/audio/aenv` instead of `/tmp`.

`scripts/analyze.py` does tempo, key, spectral balance and dynamics in one
pass. `scripts/find_artifact.py` diagnoses stem-separation bleed.

```bash
/tmp/aenv/bin/python scripts/analyze.py song.mp3
```

## ffmpeg traps that silently corrupt analysis

Four of these cost real time in one session — check them first.

**`-v error` suppresses `volumedetect` output.** The filter prints at info
level, so the "quiet" flag makes every reading come back empty and your parser
returns zeros or `-99`. Use `-hide_banner` instead:

```bash
ffmpeg -hide_banner -ss 10 -t 5 -i in.mp3 -af volumedetect -f null - 2>&1 \
  | grep -oP 'mean_volume: \K[-0-9.]+'
```

**Embedded cover art breaks stream mapping.** An mp3 with album art carries an
`mjpeg` video stream; `ffprobe` reports `codec_name=mjpeg` and default `-map`
behaviour picks up the wrong stream. Strip it before anything else:

```bash
ffmpeg -v error -i in.mp3 -map 0:a:0 -vn -acodec libmp3lame -ar 44100 -b:a 192k clean.mp3 -y
```

**`astats` with `reset` reports cumulative averages, not per-block.** A graph
built from it looks like a smooth ramp regardless of the actual arrangement.
Measure each window with a separate `-ss`/`-t` `volumedetect` call.

**int24 WAV needs the right divisor.** `scipy.io.wavfile` returns int32-backed
samples for `pcm_s24le`; dividing by `2**23` or `32768` gives levels 40–90 dB
wrong and every threshold test fails. Decode to `pcm_s16le` for analysis and
keep the high-resolution file only for rendering.

## Tempo: resolve the octave, always

Onset autocorrelation routinely lands an octave out — 65 BPM for a 130 BPM
track, or 295 BPM when peak-picking fires on sub-events instead of beats.
Never report the raw autocorrelation peak.

Take the raw estimate, generate `{raw/2, raw, raw*2}`, and score each candidate
by how much **low-band (40–150 Hz) kick energy** lands on its grid. Highest
score wins. `scripts/analyze.py` implements this.

Cross-check against an independent source when one exists. In one session
three methods agreed on 130 BPM — onset autocorrelation (129.2), least-squares
grid refinement (130.7), and a YuE2 ABC header (`Q:1/4=130`). Agreement across
different pipelines is much stronger evidence than one confident number.

Beware: a **half-time feel** is real musical information, not an error. 130 BPM
with a half-time trap groove is genuinely "65" to a listener. Report both.

### With separated stems, score the DRUM stem — not bass or harmony

Running the analyser per stem routinely returns three different tempi for the
same song. One session on a 130 BPM track produced:

| Stem | Reported | Kick-grid score | Reality |
|---|---|---|---|
| drums | 129.94 | 0.429 | correct |
| bass | 75.47 | **0.140** | garbage lock |
| other | 65.15 | 0.326 | real half-time harmonic rhythm |

Bass and harmonic stems are sparse (1.5 onsets/s vs the drums' 2.3) and have no
transient kick band to score against, so their estimates are weak or nonsense —
note how low the winning score is for `bass`. Resolve the octave on the **drum
stem only**, then run a fine sweep rather than trusting the coarse candidates:

```python
best = max(np.arange(126, 134, 0.05), key=grid_score)   # -> 129.85, score 0.4303
grid_score(best/2)                                       # -> 0.2609, clearly worse
```

The coarse `{raw/2, raw, raw*2}` candidates can all score poorly if the true
tempo is between them — 130.00 scored 0.0815 while 129.85 scored 0.4303. Always
fine-sweep around the winner before reporting a number.

A harmonic stem reading exactly half the drum tempo is **not** an error to
discard: it means chords move at half the drum rate, which is why the groove
feels laid back over a fast kick. Report it as feel, and remember it when
writing a generation prompt — see the tempo-lock section below.

## Programmed parts must follow the performance, not a grid

Synthesizing drums or bass on a fixed grid from a global BPM **will drift
audibly** against a real recording within a few bars, because real performances
are syncopated and micro-timed. A user described exactly this as "the tempo of
the song gets off from the vocals later on".

The diagnostic: histogram the inter-onset intervals of the source drums. If
they cluster at several unrelated values (e.g. 0.167 / 0.333 / 0.417 s) rather
than one, no fixed grid can track it.

The fix is to delete the independent clock. Trigger every synthesized element
from **detected onsets in the real stem**:

- kick layer → fires on each detected low-band onset
- snare layer → fires on each detected high-band onset
- hats → subdivide the interval *between consecutive real kicks*, so spacing
  tracks local tempo
- bass/808 → snap to the nearest real kick within a tolerance

With no independent timebase there is nothing to drift against.

## Sub-bass synthesis: fold strictly, or it honks

Folding "anything below 80 Hz" leaves notes at 78 Hz, which is low-mid and
reads as a honking drone — especially under saturation with a long decay. Fold
strictly into **30–55 Hz**, low-pass at ~110 Hz, keep drive modest
(`tanh(x*1.5)`, not `2.6`) and decay short (~0.7 s).

Verify by measuring the stem above 130 Hz: it should return no signal.

## Diagnosing stem-separation artifacts

When a separated stem carries unwanted content, find the band before reaching
for EQ. Compare the **normalised** spectrum of a region where the artifact is
present against one where it is absent — normalising to each region's own total
compares shape rather than level:

```
250-320 Hz   early/late energy ratio 4.08   <- the artifact
320-400 Hz   ratio 2.06
```

Then decide whether it is bleed or real content:

**Run two or three different separator models.** `ryan5453/demucs` exposes
`htdemucs`, `htdemucs_ft`, `htdemucs_6s`, `hdemucs_mmi`, `mdx_q`, `mdx_extra_q`
plus `stem`, `shifts` and `overlap` — far more control than a single-model
wrapper. If several architectures produce the same result within ~0.5 dB, the
content **is not bleed** — every model keeps it because it genuinely belongs to
that source (e.g. a low male vocal or chanted hook inside the "vocals" stem).

That distinction decides the fix:

| Finding | Fix |
|---|---|
| Models disagree → bleed | Re-separate with the better model |
| Models agree → real content | Cannot be EQ'd out; edit in **time**, not frequency |

Subtractive EQ on a band the lead voice also occupies either leaves the
artifact or guts the vocal. There is no setting that works — say so rather than
iterating on filter curves.

## Finding an edit point

To trim before a vocal entry, track a **lead register band (400–3500 Hz)** and
find the first sustained energy well above the noise floor. A real entry is
unmistakable — one session showed roughly −95 dB before and −25.9 dB at the
entry, a 78 dB jump. Cut ~150 ms early for pre-roll and add a ~50 ms fade so
the edit is inaudible.

Set the threshold from the signal's own statistics (e.g. 20th and 98th
percentile of the band envelope), never a hardcoded dB value.

## Mixing a vocal over a bed

Sidechain the bed off the vocal so it ducks instead of fighting:

```bash
ffmpeg -hide_banner -v error -i bed.mp3 -i vocal.mp3 -filter_complex "
  [0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[bed];
  [1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,
       adelay=${MS}|${MS},highpass=f=95,volume=2.0[voc];
  [voc]asplit=2[vmix][vkey];
  [bed][vkey]sidechaincompress=threshold=0.05:ratio=3.5:attack=6:release=200:makeup=1.05[duck];
  [duck][vmix]amix=inputs=2:duration=first:normalize=0,
  equalizer=f=55:t=q:w=0.9:g=2,
  equalizer=f=280:t=q:w=1.2:g=-2.5,
  alimiter=level_in=1:level_out=0.93:limit=0.96,
  aformat=sample_fmts=s16p
" -acodec libmp3lame -b:a 320k out.mp3 -y
```

`asplit` is what makes this work — the vocal is both the audible signal and the
sidechain key. Target about −14 dB mean with peaks near −0.5 dB.

For tempo alignment use `atempo` (preserves pitch); ratios within 0.97–1.03 are
transparent. If the computed vocal offset is **negative**, do not clip the
intro — push forward whole bars (`bar = 4 * 60 / bpm`) until it is positive.

**Verify alignment afterwards and report the number honestly.** Measure kick
positions in the render against the expected grid; under ~25 ms mean error is
tight. A single global offset does not correct drift — if the error is large,
say so rather than calling the result beat-matched, and move to per-downbeat
anchoring with time-warping between anchors.

## Building a generation prompt from measurements

Analyse first, then write the prompt from the numbers. Spectral balance is more
informative than genre intuition: a track with 29.5% of its energy above 6 kHz
and 4.6% below 60 Hz is bright and tight, not bass-heavy, no matter what the
genre label suggests. Crest factor under ~10 dB means a heavily limited master.

Translate measurements into production language the model understands:

```
measured 4.6% sub energy   ->  "tight controlled sub-bass, no boom"
measured 29.5% air         ->  "sparkling high-end sheen"
measured 9.6 dB crest      ->  "loud modern master, heavily compressed"
measured 121.6 BPM         ->  "122 BPM"
ABC header K:D#m           ->  "D# minor, progression D#m B G#m A#"
```

Naming the key and progression explicitly keeps generated output compatible
with a real vocal stem you intend to layer back on.

Resolve "upbeat but dark" style briefs by putting energy in the **rhythm**
(driving, syncopated, relentless) and darkness in the **harmony and timbre**
(minor key, detuned reese bass, industrial textures). Asking for both in the
same term yields sludge. Name drops as events — "builds into a drop where the
bass fully detunes and snarls" — rather than asking for "heavy drops", which
tends to produce uniform loudness.

### Genre tags outrank the BPM number — lock the tempo with rhythm words

A prompt reading "Psychedelic bass house, 130 BPM ... heavy trippy bass drops"
returned tracks the user rejected as "too slow in the half time range". The BPM
number was correct and ignored. Three signals in that prompt all implied
half-time and collectively outvoted it:

- **bass house / psychedelic bass** are half-time genres *by definition*
- **"drop"** in bass-music context specifically means the beat halves
- nothing in the prompt asserted a constant pulse

The generator produced exactly what the tags implied: a 130 grid played at 65
feel. Stating a BPM does not constrain the *feel*, only the grid.

Fix by moving trippiness out of the rhythm and into the timbre, then naming the
pulse explicitly. The load-bearing phrases are **"kick on every beat"** and
**"kick never stops"** — these block half-time interpretation in a way the
number alone does not.

| Avoid (implies half-time) | Use instead |
|---|---|
| `drop` | `peak`, `main groove` |
| `bass house`, `psychedelic bass`, `dubstep` | `acid techno`, `tech house` |
| `heavy bass drops` | `relentless rolling bassline` |
| *(nothing about pulse)* | `four-on-the-floor, kick on every beat` |
| *(nothing about subdivision)* | `sixteenth-note hi-hats` |

Fast subdivisions raise perceived tempo hard, so name them. Adding
`full tempo throughout, no half-time, no breakbeat` as an explicit negative is
cheap insurance.

Let the measured **drum** spectrum pick the genre, not the brief's vibe words:
33% air with 2.3 onsets/s is a house/techno drum signature, so techno tags
match the source material better than bass-music tags regardless of how
"trippy" the user's request sounded.

Worked example with the measurements behind it:
`references/suno-tempo-lock.md`.

### "Use similar instruments" needs timbre, not spectral balance

When the user asks for a backing track using **the same instruments as the
original**, percentages are not enough. "37% sub energy" is equally true of a
sine sub, an 808 and a detuned reese, and those three need completely different
prompt words. Measure which one it actually is:

| Discriminator | Test | Reads as |
|---|---|---|
| Kick | dominant low freq in first 40 ms vs next 120 ms | glides down → 808; stable + click ratio >0.06 → layered house kick |
| Hats | spectral flatness 4–16 kHz | >0.35 → white-noise drum machine; <0.35 → metallic/acoustic |
| Bass | `rms(30–90 Hz) / rms(200–1500 Hz)` | >3 → pure sine/808; <3 → saw/square/reese |
| Stabs | partial spacing 150–6000 Hz | inharmonic + flatness 0.3–0.6 → percussive synth pluck |

Decode at the **full 44.1 kHz** for this — telling a drum-machine hat from a
sampled cymbal depends on content above 11 kHz that a 22 kHz decode discards.

`scripts/timbre.py` runs all four discriminators and prints the prompt phrase
each reading implies. Use it rather than retyping the analysis — the three bugs
in the pitfalls list below are already fixed in it:

```bash
/tmp/aenv/bin/python scripts/timbre.py stems/          # whole stem directory
/tmp/aenv/bin/python scripts/timbre.py bass.mp3 --role bass
```

This changes prompts materially. One session measured a bass sub/harmonic ratio
of **7.34** at 54 Hz — a clean sine sub with no distortion anywhere. The draft
prompt had asked for a `detuned gritty reese growl`, which would have clashed
with the source instead of matching it. Trippiness had to come from *pitch-bend
and filter modulation of a clean sub* instead.

**Negative assertions carry real weight.** `no pads, no sustained chords` and
`no distortion on the low end` stop the generator adding textures the source
never had. Derive them from measurements: if every stem decays in under ~140 ms,
nothing in the track sustains, and the prompt should say so.

Method, discriminator thresholds, the script bugs that produce confident
nonsense, and the measurement→phrase table: `references/timbre-identification.md`.

### Genres with half-time baked in (trap, dubstep)

When the user wants trap/dark energy *and* a constant pulse, the genre label
itself is the obstacle — half-time **is** the genre at 130 BPM. Take the
genre's **timbres** and explicitly refuse its **rhythm**:

```
Dark trap-house hybrid, 130 BPM, four-on-the-floor.
Menacing distorted 808 sub-bass, fast triplet hi-hat rolls, trap snares
LAYERED OVER a constant four-on-the-floor kick.
No half-time, no breakbeat, no boom-bap, kick drives continuously.
```

**Observed: this hybrid prompt STILL came back half-time.** The user reported
"it slowed it down still" even with `no half-time`, `never halves` and
`kick drives continuously` all present. Negations did not beat the positive
signal of `trap` + `808` + `triplet hat rolls`. That makes three consecutive
half-time results across bass-house, tech-house-with-drop and trap-hybrid
prompts. Do not offer this hybrid again as a likely fix.

What has NOT yet been verified (present as untested, not as the answer):
- stripping every bass-music word (`trap`, `808`, `hat rolls`, `drop`) and
  carrying darkness in mood words only, with a literal pulse description
  (`one kick every half second`) on a techno base
- generating at ~150–160 BPM and pulling back to 130 with `atempo` locally —
  sidesteps the model's genre prior entirely, but check the stretch ratio and
  the audible cost before promising it

After a user reports "still slow", **measure the render** (drum-stem tempo and
on-beat kick %) before writing another prompt — three prompt rewrites without
numbers is how this loop wasted a session.

Split the brief the same way as any "dark but energetic" request: darkness in
timbre words (`menacing`, `sinister`, `grimy`, `underground`), speed in rhythm
words (`every single beat`, `never halves`, `kick drives continuously`).

## Sourcing audio

Prefer a file the user supplies or a direct URL. When a download is blocked by
an access control (bot check, sign-in wall), **stop and ask** — do not route
around it with proxies or scraper frontends. Ask for a Drive link or an
attachment; it is faster than engineering an evasion.

Spotify track metadata is available without scraping the JS-rendered page:
`https://open.spotify.com/embed/track/<id>` carries a `__NEXT_DATA__` JSON blob
with title, artists, release date and duration.

## Pitfalls

- **Guessing tempo.** Measure, then verify the octave.
- **`-v error` with `volumedetect`** returns nothing. Use `-hide_banner`.
- **Cover art breaks `-map` defaults.** Strip with `-vn -map 0:a:0`.
- **Raw autocorrelation peaks are often an octave out.** Score candidates.
- **Per-stem tempo disagrees.** Score the *drum* stem; bass/harmony stems are
  too sparse to score reliably. Fine-sweep — the true tempo often sits between
  the coarse octave candidates.
- **Stating "130 BPM" in a generation prompt does not prevent half-time.**
  Genre tags and the word "drop" outrank it. Name the pulse explicitly.
- **Negations do not override genre words.** `no half-time` alongside `trap` /
  `808` / `hat rolls` still produced half-time. Remove the implying words.
- **Spectral balance does not identify an instrument.** "37% sub" fits a sine
  sub, an 808 and a reese equally. Measure pitch glide, spectral flatness and
  sub/harmonic ratio before writing timbre words into a prompt.
- **Decay measured from the onset index returns 0 ms.** Onsets fire on the
  rise; find the real peak within ~80 ms first, then measure the fall.
- **Spectral centroid is dragged upward by near-empty HF bins.** A 54 Hz sine
  sub read as 1854 Hz. Floor the magnitudes at ~2% of frame max and take the
  median across frames. Two measurements that contradict each other mean one is
  broken — resolve it rather than reporting both with a caveat.
- **Fixed grids drift against real recordings.** Trigger from detected onsets.
- **Folding sub-bass to "under 80 Hz"** leaves a honk at 78 Hz. Use 30–55 Hz.
- **EQ cannot remove content that shares bands with the wanted signal.** Test
  whether it is bleed by running multiple separator models first.
- **int24 WAV scaling** silently breaks every level threshold.
- **Stems with identical file sizes** are usually CBR padding, not duplicates —
  check MD5 and per-stem loudness before assuming separation failed.
- **Claiming "beat matched" without measuring.** Verify and report the error.

## Support files

- `scripts/analyze.py` — tempo (octave-resolved), key, spectral balance,
  dynamics, onset density
- `scripts/timbre.py` — identify the actual instruments in a stem (808 vs house
  kick, sine vs reese bass, drum-machine vs acoustic hats, pads vs stabs) and
  print the prompt phrase each reading implies
- `scripts/find_artifact.py` — locate stem-separation artifacts by comparing
  normalised spectra between two regions
- `references/suno-tempo-lock.md` — worked example: why a prompt stating
  "130 BPM" still generated half-time, the per-stem measurements behind it,
  and the corrected prompt
- `references/timbre-identification.md` — identifying actual instruments from a
  stem (808 vs house kick, sine vs reese bass, drum-machine vs acoustic hats),
  the analysis-script bugs that produce confident nonsense, and the
  measurement→prompt-phrase table
