# SPEC — [REF VIDEO] remade for [BRAND]

Source: [URL / file, who made it] · [duration]s · [fps] fps · [W]x[H] · hard cuts (ref/cuts.json): [list]
Rights: REF supplied by [user]; our film reuses none of REF's music, voice, images or people. Original brand credited in the post.

## Swap rules
| REF | ours |
|---|---|
| [old brand name / mark] | [new brand name / mark] |
| [old accent hex] | [new accent hex] |
| [REF product claim] | [TRUE equivalent claim for our brand, or "Example data" label] |

## Shot table (frames are 0-based, f1 exclusive; boundaries are estimates, build agents correct them)
| id | f0 | f1 | REF content (what moves, how) | our content (brand swap) | group |
|---|---|---|---|---|---|
| s01 | 0 | | | | G1 |

## Groups (contiguous; one build agent each)
G1: [f0-f1] · G2: [f0-f1] · G3: [f0-f1] · G4: [f0-f1]  (copy into project.json "groups")

## Audio (audio agent)
REF BPM [x] · drop at [t]s · hard stop [t]s · SFX hits: ref/audio_map.json · VO slots (STT timings): [..]
Our track: [Mixkit id / supplied / synthesized], stretch <= 8%, drop on REF's drop.
