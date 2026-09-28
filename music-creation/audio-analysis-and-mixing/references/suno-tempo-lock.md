# Suno tempo lock: stating BPM does not prevent half-time

Session record. A user supplied four separated stems and asked for a
"bass heavy 130 BPM backing track with heavy trippy bass drops" to remix
against. The first prompt was rejected: *"the songs ended up too slow in the
half time range."*

The BPM number in the prompt was correct. It was ignored.

## Measurements from the stems

Analyser run per stem, 120 s window. Tempi disagreed across stems:

| Stem | Reported BPM | Kick-grid score | Interpretation |
|---|---|---|---|
| drums | 129.94 | 0.429 | correct |
| bass | 75.47 | 0.140 | weak/garbage lock, sparse onsets |
| other | 65.15 | 0.326 | genuine half-time harmonic rhythm |

Fine sweep on the drum stem's 40–150 Hz kick envelope settled it:

```
126-134 sweep  -> 129.85 BPM  score 0.4303
half of that   ->  64.92 BPM  score 0.2609
130.00 BPM                    score 0.0815   <- coarse candidate scored WORSE
```

The coarse `{raw/2, raw, raw*2}` set never contained the true value. Always
fine-sweep.

Key, from chroma over bass + other with Krumhansl templates:

```
D# minor  r=+0.690     <- chosen
D# major  r=+0.514
A# major  r=+0.480
```

Pitch-class weight: A# 13.8%, D# 11.0%, B 10.5%, F# 9.3%.

Spectral balance:

| Stem | sub 20–60 | bass 60–150 | mid 400–2k | air 6k–16k | crest |
|---|---|---|---|---|---|
| drums | 5.5% | 13.2% | 16.1% | **33.0%** | 17.0 dB |
| bass | **37.0%** | 31.8% | 5.4% | 0.9% | 18.1 dB |
| other | 1.2% | 2.4% | **42.4%** | 17.3% | 21.8 dB |

Onset density: drums 2.3/s, bass 1.5/s.

Stem sanity check: all four files were byte-identical in size (7,497,142) —
CBR padding, not failed separation. Distinct MD5s and distinct per-stem
loudness (drums −16.8 dB, bass −20.2, other −20.2, vocals −24.2) confirmed
real separation.

## The failed prompt and why it failed

```
Psychedelic bass house, 130 BPM, D# minor. Heavy detuned
reese bass, warped sub-bass, trippy modulated low end.
...
[Drop - bass fully detunes and snarls, sub locks to kick]
```

Three independent half-time signals outvoted the BPM number:

1. **`bass house` / `psychedelic bass`** — half-time genres by definition.
2. **`drop`** — in bass-music context this *means* the beat halves.
3. **No assertion of a constant pulse anywhere in the prompt.**

Result: a 130 grid played at 65 feel. The generator was consistent with its
tags, not with its number.

Compounding error on the analysis side: the `other` stem's genuine 65 BPM
half-time harmonic rhythm was reported to the user, which made half-time
sound like a property of the source worth reproducing. It is a property of the
*chords*, not the *pulse*.

## The corrected prompt

```
Driving acid techno, 130 BPM, four-on-the-floor,
D# minor. Kick on every beat, relentless rolling
16th-note bassline, squelchy acid 303 twisting and
modulating, detuned reese growl in the low mids.
Crisp airy hats, sixteenth-note hi-hat pattern,
syncopated percussion, dark hypnotic minor groove.
Constant forward momentum, full tempo throughout,
no half-time, no breakbeat. Instrumental, no vocals.
```

Structure tags, instrumental ticked and lyrics left empty:

```
[Intro - filtered pulse, kick on every beat]
[Build - acid line opens, hats intensify]
[Peak - bass snarls and modulates, kick never stops]
[Breakdown - pads and hats, kick holds steady]
[Peak 2 - heavier acid, bass pitch-bends]
[Outro - filter close]
```

Every `[Drop]` became `[Peak]`, and two sections explicitly assert the kick
continues.

## Transferable rules

- **Genre tags outrank the BPM number.** Pick a genre locked to a constant
  pulse (acid techno, tech house) when the user wants full tempo.
- **Name the pulse**: `four-on-the-floor, kick on every beat`, and inside
  structure tags `kick never stops` / `kick holds steady`.
- **Name the subdivision**: `sixteenth-note hi-hats` raises perceived tempo.
- **Add explicit negatives**: `no half-time, no breakbeat`.
- **Avoid `drop`** entirely in tempo-sensitive prompts; use `peak`.
- **Let the drum spectrum choose the genre.** 33% air at 2.3 onsets/s is a
  house/techno drum signature — techno tags fit the source better than
  bass-music tags no matter how "trippy" the brief sounds.
- Tech house is the safer fallback if acid techno reads too aggressive: it
  sits naturally at 128–130 and never half-times.

## Remix note carried to the user

The original bass owned 20–150 Hz (37% + 31.8%) while 150–400 Hz was nearly
empty across all stems. Either drop the original bass stem and let the new one
carry the low end, or high-pass the new bass at ~120 Hz into that gap.
Otherwise the two sub-heavy parts mud each other.

Suno will not land exactly on 129.85, so expect slight drift;
`atempo=0.99885` corrects it and is well inside the transparent 0.97–1.03
range.
