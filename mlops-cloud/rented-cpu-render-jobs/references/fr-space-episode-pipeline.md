# French space channel: generic per-episode tools (Oct 2026)

All in `~/.hermes/data/yt-arbitrage/fr-space/`. Every tool takes an episode folder name (`e2-betelgeuse`,
`e3-fin-univers`, …), so one copy serves the whole channel. Style rules: `viral-youtube-video`
`references/fr-space-style.md` (that skill is user-owned; read it, don't assume it's current).

| Tool | Does |
|---|---|
| `vo_run.sh <ep>` | VO chunks (Nicolas, eleven_v4) → loudnorm −14 LUFS → Scribe check + word timings → `build/words.json`, `beats_real.json`. Run episodes one after another (`vo_batch_e4e6.sh`): ElevenLabs is shared. |
| `auto_cuts.py <ep>` | Matches each [VISUAL] cue's first words to Scribe timings and puts the cut in the middle of the preceding pause → `build/cue_overrides.json`. Number-word normalising must not treat "un/une/et" as numbers. |
| `ep_jobs.py <ep>` | Prints graphics jobs `ID:from:to …` from `visuals/shots.py` rows with `src=='graphic'` (real cue times + overrides; last cue ends 1 s after the last word). |
| `pod_episode.sh <ep> <graphics-project>` | Whole-episode render on one rented pod: graphics + photo_fx slots concurrently, then assembly and sync audit there; pulls back; always terminates. |
| `assemble_ep.py <ep> <graphics-project>` | Per-cue segments, exact frame counts, music bed, −14 LUFS master, strict "no cut inside a word" audit. Upload is gated on it. |
| `music_bed_ep.py <out> <dur> <ep>` | Code-generated drone; chords seeded by the episode name so beds differ (anti-template). |
| `upload_ep.py <ep> "<Drive name>" <sub> '<glob>'` | Uploads to `French Space Channel/<name>/<sub>/`, verifies sizes, prints the folder link. |
| `VISUALS_WORKER_BRIEF.md` | Brief a visuals subagent follows: rules, spend caps (stills ≤ $1.50, clips ≤ $3.00 per episode), QC gates, final JSON. |

The photo engine (`visual_test/photo_fx/engine.py`) reads `PFX_VT`, `PFX_BUILD`, `PFX_SPEC` env vars, so it
serves any episode.

## ElevenLabs credit accounting
The subscription counter includes Scribe STT, not just TTS. Split it with
`GET /v1/usage/character-stats?breakdown_type=product_type|model|voice&aggregation_interval=hour`.
v4 TTS stayed ~0.1 credit/char; the apparent "rising rate" was two Scribe passes per VO (check + word timings)
on the same audio, and one pass can serve both. Measured lengths: E3 9:56, E4 10:08 (~1,940 credits incl.
STT), E5 9:33, E6 20:03 (~3,250).
