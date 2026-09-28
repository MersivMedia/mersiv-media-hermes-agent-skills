# Measured drift experiments

Real A/B numbers from a branching-film build. Cite these instead of re-deriving them;
every one cost a paid render. Provider: fal MiniMax H3 Max, 1536x672, 24fps.

## The experiment

Same story beat, same characters, same style bible, rendered twice under different
pipeline settings.

| | Render A (baseline) | Render B (fixed) |
|---|---|---|
| Shot durations | 13.7s, 14.4s, 7.3s | 5s x3, 6s, 5s |
| Mode | 1 reference-to-video, then 2 chained | 4 reference-to-video, 1 chained |
| Costume | **unspecified** — model invented per call | authored canon, injected verbatim |
| Shots per scene | 3 | 5 |

## Result 1: identity drift — collapse eliminated

```
Render A   8/10 -> 5/10 -> 3/10     monotonic decay along the chain
Render B   8/10 -> 8/10 -> 8/10     flat (scored on the re-anchored shots)
```

The character in the *last* shot of B is as on-model as in the second. The A
collapse is a chaining artifact: only shot 0 ever saw the reference sheet, and each
subsequent shot inherited identity from a frame that had already drifted.

## Result 2: the one chained shot in B was the worst shot in B

Scored 6/10 against 8/10 for the reference-anchored shots around it, and it was the
only shot that still re-staged inside a 5-second take: interior two-shot at t=0.2 →
doorway seen from outside at t=2.5 → legs and boots at t=4.8. Location, camera side,
lighting and blocking all changed within one clip.

Combined with the fact that image-to-video accepts no reference audio (so chained
shots cannot lip-sync), this is three independent reasons to disable chaining.

## Result 3: shot length is the stability control

Garment colour sampled at first/mid/last frame of each B shot held within one
lighting stop, e.g. `rgb(50,35,14)` → `rgb(48,34,16)`. No location swap, no relight,
no re-aging. Render A's 35 seconds wandered night-rain-threshold → sunny balcony →
cosy interior.

## Result 4: short shots are disproportionately faster

| Shot | Mode | Duration | Inference | Ratio to realtime |
|---|---|---|---|---|
| A[0] | ref2v, 9 refs | 13s | 22.3s | 0.58x |
| A[1] | chained | 14s | 15.4s | 0.91x |
| A[2] | chained | 7s | 5.0s | 1.4x |
| B[*] | ref2v | 5s | ~5.6-5.7s | ~0.88x |
| B[*] | chained | 5s | 2.9s | 1.7x |

Scene totals: A rendered 35.4s of film from 42.7s inference (0.83x). B rendered 27.3s
from 29.5s (0.93x).

The important non-linearity: a 13s reference-to-video shot took 22.3s while a 5s one
takes ~5.7s. Reference-to-video is far cheaper at short durations than its long-shot
timings suggest — which is what makes "re-anchor every shot" affordable. Do not
budget reference-to-video from a long-shot measurement.

Cost was ~$1.05 per scene, ~$9-10 per 9-scene run.

## Result 5: costume canon works, measured in pixels

| | Render A | Render B |
|---|---|---|
| Reference plate | `rgb(244,242,234)` near-white | `rgb(142,122,97)` / `rgb(169,132,90)` warm tan |
| In-shot torso | — | `rgb(128,78,41)` tan under sodium light |
| Second character | invented | olive shirt `rgb(99,98,74)`, tan-brown boots `rgb(167,126,71)` |

Vision review confirmed the authored details on screen: tan-khaki buttoned coverall
with the specified grey undershirt at the collar; the other character in olive with
**two buttoned chest pockets** and the specified equipment case. Details written into
canon show up; details left out get invented.

Note the trap: under sodium-vapour practicals a tan garment samples as dark as
`rgb(50,35,14)`. Hue ordering (R>G>B) survives; absolute values do not. Gate on hue
and luminance, and sample from several shots before declaring a costume failure.

## Result 6: writing quality improved as a side effect

At 13-14s the story engine crammed four dialogue lines into a single shot. At 5s it
wrote one line per shot. The duration cap propagated into the writing, unprompted.

## What no metric caught

Both defects a human viewer reported — a door showing exterior on both sides, and
doubled/desynced dialogue — passed every objective gate in the pipeline. Neutrality,
uniformity, distinctness and costume checks are all *plate* metrics; nothing was
watching scene geometry or audio-video alignment. Budget for a human or vision pass
on the assembled output, not just on the reference assets.
