---
name: character-reference-sheet
description: Build character reference sheets + packs for video.
version: 1.0.0
author: Mersiv Media + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [character-design, reference-sheet, turnaround, expression-sheet, identity-lock, replicate, seedream, video-consistency]
    related_skills: [replicate-api-generation, generated-asset-verification, generative-video-consistency, ref-character-replacement-content-pipeline, video-character-replacement, seedance-video, branching-ai-film-engine, motion-trainer-for-generative-video]
---

# Character Reference Sheet

Builds a production character reference sheet in the 7-section format
(profile, full-body turnaround, face and identity, expression sheet, poses,
costume details, colour and material palette), **and** the model-facing
reference pack that video skills actually consume.

**This is the default source of character references for every video skill in
this library.** A single casual photo as the identity input is the most common
reason a character drifts across shots.

## When to Use

- The user sends a reference sheet like the 7-section examples and asks for one.
- Any video job that needs a character to hold identity across shots or clips:
  H3 ref2va swaps, Seedance reference locks, VACE/Wan character replacement,
  branching-film pre-production, avatar insertion.
- The user has only one photo of a character and wants multiple angles and
  expressions before spending on video.

## Two outputs, two audiences

| Output | Who reads it | Why |
|---|---|---|
| `sheet.jpg` (2400×3300) | Humans | Review and approval, the thing that looks like the examples |
| `pack/NN_<plate>.png` + `manifest.json` | Video models | One clean plate per image, ranked |

**Never feed the composed sheet to a video model as a reference.** A collage
teaches the model to render a collage, panel borders and labels included.
Video models get individual plates from `pack/`, in rank order, cut to their
reference cap with `manifest.json` → `top_refs`.

## Consent (enforced in `build_sheet.py`, not optional)

- `subject_type: fictional` is the default and the normal case.
- `subject_type: real_person` needs `consent: self` (the user) or
  `consent: consented` (the person agreed), **and** must start from that
  person's own photo. The script refuses anything else.
- Sheets of celebrities or public figures who haven't consented are refused.
  The two example sheets the format came from depict famous actors; copy the
  **layout**, never the subject. Offer to design a fictional character in the
  same format.
- Same content rules as the H3 pipeline: no sexual or nude content.

## Quick Reference

```bash
S=~/.hermes/skills/creative/character-reference-sheet/scripts/build_sheet.py
set -a; . ~/.hermes/.env; set +a            # REPLICATE_API_TOKEN (terminal, not execute_code)
python3 $S init mara-voss --name "Mara Voss" [--anchor photo.jpg]
#   -> ~/.hermes/data/character-reference-sheet/mara-voss/spec.yaml  (fill it in: this is the canon)
python3 $S plan  <spec.yaml>                  # dry run: every plate, prompts.json, cost
python3 $S run   <spec.yaml> --only anchor --yes   # 1 plate, approve it before anything else
python3 $S run   <spec.yaml> --yes            # the rest, i2i from the anchor; runs QC + compose + pack
python3 $S run   <spec.yaml> --only turn_side,expr_sad --yes   # re-roll what QC flagged
python3 $S qc | compose | pack <spec.yaml>    # no spend
```

## Procedure

1. **Author the spec first.** `spec.yaml` holds name, profile, face details,
   costume (summary, accessories, footwear, detail shots), palette hexes and
   materials. Every prompt is built from it verbatim and QC checks against it.
   An unauthored property can't be held steady: a pipeline with no costume
   field once got a white garment where tan was intended, and the reviewer
   graded it against a spec it had made up.
2. **Plan and quote.** `plan` prints every plate and the estimate. The full
   sheet is 31 plates: **$1.24 on seedream-4.5** ($0.04/plate), about $1.43
   with re-rolls. Show the user the estimate and wait for approval before `--yes`.
3. **Anchor first, then approve it.** `run` renders the anchor and stops. It
   is a full-body neutral plate (from `anchor.from_photo` if given). Every
   other plate is i2i from it, so its mistakes copy into all 30. Look at it
   (vision) before continuing.
4. **Render the rest.** One prediction per plate, never a batched call
   (batched "N images" silently under-delivers and collapses contrast between
   items). The returned count is asserted, and raw images land in
   `_raw/<plate>.<sha8>.png`, never overwritten.
5. **Numeric QC before vision.** `rs_qc.py` white-balances on the known-neutral
   backdrop, then applies a luma-only gamma onto the set median, then measures:
   neutrality ≤12, group luma spread ≤20, closest-pair distinctness ≥6. It
   prints the closest pairs, not just the minimum. Anything that still fails
   is listed as must-regenerate and is left out of the sheet and the pack.
6. **Vision review, one group at a time.** Numeric gates can't check meaning:
   is the side view really 90°, does "worried" read as worried, is it the same
   person. Build one contact sheet per group and check each group separately
   (turnaround, face, expressions, poses). Re-roll with `--only`.
7. **Deliver** `sheet.jpg`, the `pack/` folder and `manifest.json`. For Drive,
   file under the project the character belongs to.

## Handing the pack to video skills

`manifest.json` → `top_refs` gives the best N plates for each reference cap.
Rank order: `face_front, turn_front, turn_side, turn_back, face_profile,
expr_neutral, turn_three_quarter, face_three_quarter, pose_walking,
pose_neutral_stand`, then the rest.

| Consumer | Cap | Use |
|---|---|---|
| `ref-character-replacement-content-pipeline` (H3 ref2va) | 1 character image in the graph | `turn_front` (full body, plain backdrop, so SAM3's cutout is clean). Plain backdrop also means no environment leaks in when the background box is unticked |
| `seedance-video` / seedance-2.0 | 9 `reference_images` | `top_refs["9"]`; round-robin across characters when there are several |
| seedance-1-lite | 4 | `top_refs["4"]` |
| `video-character-replacement` (VACE / Wan Animate) | 1 | `turn_front` |
| nano-banana-pro / seedream stills | 14 | the whole pack |
| `branching-ai-film-engine` pre-production | per shot | pack plates as identity locks; the spec is the canon file |

Also pass `manifest.json` → `identity_text` into the video prompt, so text and
image describe the same person.

## Pitfalls

1. **Text in the sheet is drawn, never generated.** Names, labels, hex codes
   and swatches all come from `rs_layout.py`. Generated small text comes out
   misspelled, and a generated swatch isn't the authored colour.
2. **The 3/4 (45°) slots are the known weak point.** Across three rounds of
   prompting, intermediate angles over- and under-rotated while front, profile
   and back passed every time. The examples include a 3/4 view, so the slot
   exists, but check it with vision. If it's wrong, drop it (the sheet reflows)
   and don't ship a wrong angle: it teaches a video model an angle the
   character never actually holds. It is ranked low in the pack.
3. **No cinematic grade on any plate.** A grade on the anchor spreads through
   i2i to every plate, and the video model then learns coloured light instead
   of the character's real colours. `REF_LIGHT` forbids it; keep grades for
   final shots.
4. **Expressions are physical muscle actions, not emotion words.** "Neutral
   but guarded" comes out blank. The `EXPR` table spells out brows, lids and
   mouth. "Sad" carries clean-under-eye clauses, because "grief" once
   rendered as bruising.
5. **Age is anchored to the reference, not a number.** "Late 50s" came out
   as late 60s. `KEEP` says "same age as the reference, no older".
6. **Strong costume colours bleed into the backdrop.** Tan pushes it warm,
   olive pushes it teal. The white-balance pass handles this; expect it.
7. **Replicate's default `Python-urllib` user agent gets a 403.** The script
   uses curl with its own user agent and uploads through the files API (2K
   PNGs as data URIs blow the ~10 MB body limit).
8. **`execute_code` doesn't see `REPLICATE_API_TOKEN`.** Run from `terminal`.
9. **Costume and material plates have no backdrop** and are exempt from
   neutrality and uniformity. Don't "fix" a close-up to grey.
10. **Page rows must sum to 1.0** in `rs_layout.compose`, or the sheet ends in
    a dead white band (found in the first layout check). Headers are
    truncated to the text column so they never run under the portrait.

## Models (verified live 2026-09-28)

| Key | Model | Refs field / cap | Price |
|---|---|---|---|
| `seedream` (default) | `bytedance/seedream-4.5` | `image_input` / 14 | $0.04 |
| `nano` | `google/nano-banana-pro` | `image_input` / 14 | ~$0.15 at 2K |
| `flux` | `black-forest-labs/flux-2-pro` | `input_images` / 8 | ~$0.06 at 2 MP |

Check a model's schema live before switching (`replicate-api-generation`).

## Files

| Path | What |
|---|---|
| `scripts/build_sheet.py` | init / plan / run / qc / compose / pack; consent gate; one call per plate |
| `scripts/rs_qc.py` | neutrality, uniformity, distinctness; white balance + luma-only gamma; triage |
| `scripts/rs_layout.py` | 7-section sheet composer; reflows missing plates |
| `templates/spec.yaml` | fully annotated spec (a fictional example character) |
| `tests/test_offline.sh` | 14 checks: consent gate, plan/cost, prompt rules, QC with planted defects, layout, pack. No spend |

## Status

Built and tested offline on 2026-09-28: 14/14 checks pass, and the layout was
checked visually on synthetic plates. **Not yet run against a real model.**
The first real run should be a single anchor (`--only anchor`, $0.04), then
the full set once the user approves.

## Verification

- [ ] `plan` estimate shown and approved before any `--yes`
- [ ] Anchor viewed and approved before the other 30 plates
- [ ] `qc.json` pass, or every failure re-rolled or knowingly dropped
- [ ] Vision check per group; 3/4 slots judged specifically
- [ ] `sheet.jpg` text read back (it's drawn, so it should be exact)
- [ ] `pack/` plus `manifest.json` delivered; video skills pointed at `top_refs`
