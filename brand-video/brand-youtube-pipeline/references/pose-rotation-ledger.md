# Pose Rotation Ledger — Talking-Head Anti-Repetition

The SKILL.md Phase 6 selection rules say: "Across the last 3 episodes, track which poses were used in talking-head #1, #2, etc., and bias toward poses not used in that slot recently. Goal: any given viewer sees a different sequence in consecutive videos."

This file tracks what shipped. **Update it after every episode** so the next selection has data to bias against. If two consecutive episodes use the same pose in slot N, the curator (or the next agent) gets to see the violation here and fix it.

## How to use this ledger

1. Before generating talking-heads for a new episode, read this file.
2. For each TH slot (1-6), check what pose ran in the last 2-3 episodes. Bias toward a pose **not** in that slot's recent history while still matching the line intent (intent > rotation when they conflict — but force a swap when intent is genuinely flexible).
3. After the episode is generated and accepted, append a new row.
4. Cold-open and outro-CTA slots are intentionally allowed to repeat poses 08 and 10 — they're bookends and the consistent open/close framing is on-purpose. Slots 2-5 are where rotation matters most.

## Episode-by-episode pose usage

| Episode | th1 (cold-open) | th2 | th3 | th4 | th5 | th6 (outro) | Notes |
|---|---|---|---|---|---|---|---|
| Ep1 — Pure-Play Space Stocks | 08-pointing | 05-explaining | 03-arms-crossed | 12-fist | 04-gesturing | 10-hand-on-hip | Reference baseline; canonical thumbnail = pose-08 gold |
| Ep5 — Space SPAC Graveyard | 08-pointing | 05-explaining | 03-arms-crossed | 12-fist | 04-gesturing | 10-hand-on-hip | **VIOLATION: identical to Ep1.** All 6 slots reused. Sequence-rotation rule was not consulted. Pose-03 thumbnail (red) chosen separately. |
| Ep2 — Rocket Lab vs SpaceX | 08-pointing | 03-arms-crossed | 04-gesturing | 12-fist | 05-explaining | 10-hand-on-hip | **PARTIAL VIOLATION:** slots 2 + 5 swapped vs Ep1/Ep5 baseline; slots 1, 3, 4, 6 still identical. Pose-04 thumbnail (gold). |
| Ep3 — AST SpaceMobile $34B Paper Fleet | 08-pointing | 05-explaining | 12-fist | 03-arms-crossed | 04-gesturing | 10-hand-on-hip | **VIOLATION:** same 6 poses as everything else; only slot 3+4 swapped. Pose-03 thumbnail (red). |
| Ep4 — Reading Space Company Earnings | 08-pointing | 05-explaining | 12-fist | 03-arms-crossed | 04-gesturing | 10-hand-on-hip | **VIOLATION: IDENTICAL TO Ep3.** Sequence `08 → 05 → 12 → 03 → 04 → 10` shipped unchanged across two consecutive episodes. Ledger was not read before Phase 6 — the rule was theoretical, not enforced. Pose-05 thumbnail (gold). |
| Ep12 — Space Industry Salaries | 08-pointing | 05-explaining | 12-fist | 03-arms-crossed | 04-gesturing | 10-hand-on-hip | **VIOLATION: IDENTICAL TO Ep3 AND Ep4.** Sequence `08 → 05 → 12 → 03 → 04 → 10` shipped a THIRD consecutive time. Even after the previous violation notice was already in this ledger, the agent ran the pipeline without loading the ledger first. The script.md note even explicitly says "proven rotation, no back-to-back repeats" — which is FALSE; it's the third consecutive identical sequence. Pose-04 thumbnail (gold). First Careers-pillar episode shipped — pillar change did NOT break the rotation drift. |

## ENFORCEMENT FAILURE (May 2026, ONGOING)

6 episodes shipped (Ep1, Ep5, Ep2, Ep3, Ep4, Ep12) — **all 6 used the same 6 poses**. Ep3, Ep4, and Ep12 are now three consecutive episodes with the IDENTICAL `08 → 05 → 12 → 03 → 04 → 10` sequence. The 6 underused poses (01, 02, 06, 07, 09, 11) have NEVER appeared in any shipped episode. The rotation rule has been ignored for the entire production run to date.

**Root cause of the failure:** Phase 6 has been executed without the ledger ever being loaded BEFORE the script is drafted. The SKILL.md tells the agent to "READ `references/pose-rotation-ledger.md` FIRST" but the agent has been drafting the talking-head pose plan inside `script.md` during Phase 3 from intent-matching alone, then carrying that plan straight into `chunks.json` for Phase 4 TTS, locking the poses into the audio filenames before Phase 6 ever runs. By the time Phase 6 starts, swapping a pose means renaming the WAV chunk it pairs with, and the agent silently sticks with whatever Phase 3 picked. The ledger note in the SKILL was treated as a Phase 6 instruction; it should have been a Phase 3 instruction.

**Hard rule going forward — PHASE 3 PRECONDITION, NOT PHASE 6:**

The pose sequence is decided in Phase 3 when the script is written, because `chunks.json` (Phase 4) bakes the pose into the audio filename. To actually break the drift, the ledger must be loaded BEFORE the Phase 3 talking-head pose plan is written, not before Phase 6 generates the videos. New checklist:

1. **Phase 3, BEFORE drafting the talking-head pose plan section of `script.md`:** load `references/pose-rotation-ledger.md` via `skill_view(name='brand-youtube-pipeline', file_path='references/pose-rotation-ledger.md')`.
2. For each of the 6 talking-head slots, look at the slot-by-slot history below. If the intent-best pose is in the "NUCLEAR HOT" or "HOT" category for that slot, force-swap to one of the underused poses (01, 02, 06, 07, 09, 11) that ALSO fits the line's intent at a passable level.
3. **Bookend slots (th1 cold-open and th6 outro-CTA) are no longer exempt** — six identical bookends across six episodes is monotonous, not "intentional consistency."
4. Document the swap reasoning in the script's pose plan table so future agents see the intent + rotation trade.
5. After Phase 6 ships and the user accepts, append the row to this ledger immediately. No more shipping-then-forgetting.

If three consecutive episodes ship without the underused pool appearing at all, the channel is visually monotonous and the rule has failed again — at that point the curator should hard-fail Phase 3 until the ledger is loaded.

## Slot-by-slot recent history (read this before picking — as of Ep12, May 2026)

- **th1 cold-open:** 08-pointing × 6 consecutive eps. **OVER-USED EVEN FOR A BOOKEND.** Next episode MUST switch to 07-hand-on-chin (reflective cold open), 09-palms-up (rhetorical "what did you expect"), or 11-tipping-hat (charming smooth open). Save 08-pointing for one of the inner slots where its direct-callout intent fits.
- **th2:** 05-explaining (Ep1, Ep5, Ep3, Ep4, Ep12) | 03-arms-crossed (Ep2). **NUCLEAR HOT.** 05-explaining has now run 5 of 6 episodes. Force-swap to 02-hand-on-chest (sincere setup), 07-hand-on-chin (reflective setup), 09-palms-up (rhetorical setup), or 11-tipping-hat (transitional setup).
- **th3:** 03-arms-crossed (Ep1, Ep5) | 04-gesturing (Ep2) | 12-fist (Ep3, Ep4, Ep12). **NUCLEAR HOT.** Force-swap to one of the 4 unused poses: 01, 02, 06-thumbs-up, 07, 09, 11.
- **th4:** 12-fist (Ep1, Ep5, Ep2) | 03-arms-crossed (Ep3, Ep4, Ep12). **NUCLEAR HOT** — every episode has shipped with one of just two poses in this slot. Force-swap to 06-thumbs-up (endorsing payoff), 02-hand-on-chest (sincere hard truth), or 09-palms-up (incredulous reaction).
- **th5:** 04-gesturing (Ep1, Ep5, Ep3, Ep4, Ep12) | 05-explaining (Ep2). **NUCLEAR HOT.** 04-gesturing has now run 5 of 6 episodes. Force-swap to 06, 07, 09, 11, or 02.
- **th6 outro-CTA:** 10-hand-on-hip × 6 consecutive eps. **OVER-USED EVEN FOR A BOOKEND.** Rotate to 11-tipping-hat ("and that, friends..." sign-off) or 06-thumbs-up (payoff endorsement) on episodes with a softer or more upbeat close.

## Underused poses (use these soon)

Across 6 episodes shipped, these poses have appeared **zero** times:
- **01-arms-down** (neutral baseline) — never used
- **02-hand-on-chest** (sincere/personal) — never used
- **06-thumbs-up** (endorsement/payoff) — never used
- **07-hand-on-chin** (reflective/thinking) — never used
- **09-palms-up-questioning** (rhetorical) — never used
- **11-tipping-hat** (transitional sign-off) — never used

The next 2-3 episodes MUST each introduce at least 2 of these poses in slots 2-5 to break the rotation drift. If a pose hasn't appeared in 6+ episodes, the channel is visually monotonous and the anti-repetition system has failed.

## Update protocol

After Phase 6 completes for a new episode:
1. Append a row to the "Episode-by-episode pose usage" table.
2. Recompute the slot-by-slot history.
3. If you violated the rotation rule because intent forced it, write the reason in the Notes column so it doesn't look like negligence to the next agent.
