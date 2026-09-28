#!/usr/bin/env python3
"""Pose selector for [brand] talking-head clips.

Given the 6 talking-head transcript snippets from an episode (and optionally
the recent-history of poses used in prior episodes), returns the chosen pose
filename for each talking-head clip — content-driven, anti-repetition.

Used inside Phase 6 of the brand-youtube-pipeline skill.

USAGE (programmatic):
  from select_poses import select_poses
  picks = select_poses(transcripts=[...6 strings...], history=[...recent picks...])
  # -> [{"clip": "th-1", "pose": "01-arms-down", "reason": "..."}, ...]

USAGE (CLI):
  python3 select_poses.py path/to/talking-heads.json
  # talking-heads.json schema:
  # {"history": [["02","04","06"], ["01","03","05"]],   # optional, last N episodes
  #  "clips": [{"id":"th-1","text":"..."},...]}
"""
from __future__ import annotations
import json, sys, re
from pathlib import Path
from dataclasses import dataclass
from collections import Counter

# Pose library — every pose with the cues that should pick it.
# Order matters: first match wins among ties.
POSE_LIBRARY = [
    {
        "id": "01-arms-down",
        "file": "character-pose-01-arms-down.png",
        "intent": "SETUP",
        "vibe": "neutral / open / baseline",
        "best_for": "calm setup beats, situation framing, intro hooks, default narration",
        "cues": [
            r"\b(today|here(?:'s| is)|let me|we(?:'re| are) (?:going to|gonna) (?:talk|cover|look)|the (?:situation|setup|background))\b",
            r"\b(first(?:ly)?|to start|to begin)\b",
        ],
    },
    {
        "id": "02-hand-on-chest",
        "file": "character-pose-02-hand-on-chest.png",
        "intent": "SINCERE",
        "vibe": "personal, hand-over-heart sincerity",
        "best_for": "values statements, 'this matters because…', earnest beats",
        "cues": [
            r"\b(this matters|i(?:'ve| have) (?:learned|seen)|honest(?:ly)?|the truth (?:is|of it)|believe me|trust me|here(?:'s| is) why)\b",
            r"\b(genuine|sincere|personal|for real)\b",
        ],
    },
    {
        "id": "03-arms-crossed",
        "file": "character-pose-03-arms-crossed.png",
        "intent": "SKEPTICAL",
        "vibe": "skeptical, authoritative, contrarian",
        "best_for": "calling BS, 'actually…', contrarian takes, weighing claims",
        "cues": [
            r"\b(actually|the truth is|don(?:'t| not) (?:believe|buy)|nonsense|that(?:'s| is) (?:wrong|false|bs|bullshit|nonsense))\b",
            r"\b(skeptic(?:al)?|doubt(?:ful)?|suspicious|hold on)\b",
        ],
    },
    {
        "id": "04-one-hand-gesturing",
        "file": "character-pose-04-one-hand-gesturing.png",
        "intent": "POINT-MAKING",
        "vibe": "making a specific point, building the argument",
        "best_for": "'but here's what they won't tell you', specific revelations",
        "cues": [
            r"\b(but here|here(?:'s| is) (?:the thing|what)|they (?:won(?:'t| not)|will not) tell you|the (?:catch|kicker|secret))\b",
            r"\b(specifically|notably|importantly|key point)\b",
        ],
    },
    {
        "id": "05-both-hands-explaining",
        "file": "character-pose-05-both-hands-explaining.png",
        "intent": "EXPLAINING",
        "vibe": "structured walk-through, framing a concept",
        "best_for": "explaining mechanics, walking through how X works, mid-video setup",
        "cues": [
            r"\b(how (?:it|this) works|let me (?:show|walk|explain)|think (?:of|about) it (?:like|as)|the way (?:it|this) works)\b",
            r"\b(step by step|the (?:process|mechanism|structure)|consider this)\b",
        ],
    },
    {
        "id": "06-thumbs-up",
        "file": "character-pose-06-thumbs-up.png",
        "intent": "ENDORSING",
        "vibe": "approval / endorsement / celebration",
        "best_for": "good news, payoff lines, celebrating wins, 'this is the upside'",
        "cues": [
            r"\b(good news|the upside|the win|great move|nice (?:work|job)|paid off|big win)\b",
            r"\b(love this|nailed it|smart play|exactly right)\b",
        ],
    },
    {
        "id": "07-hand-on-chin",
        "file": "character-pose-07-hand-on-chin.png",
        "intent": "REFLECTIVE",
        "vibe": "thoughtful, weighing, considering",
        "best_for": "trade-off analysis, 'let's think about this', posing a question",
        "cues": [
            r"\b(think about (?:this|it)|consider (?:this|that)|on the other hand|trade(?:-| )off|weigh(?:ing)?)\b",
            r"\b(what (?:if|do you think)|why (?:does|do)|the question (?:is|becomes))\b",
        ],
    },
    {
        "id": "08-pointing-at-camera",
        "file": "character-pose-08-pointing-at-camera.png",
        "intent": "DIRECT-ADDRESS",
        "vibe": "calling out the viewer directly",
        "best_for": "'if you're holding X, listen up', personal confrontation, second-person address",
        "cues": [
            r"\b(if you(?:'re| are) (?:holding|investing|thinking|considering|buying)|listen (?:up|to me)|you (?:need to|have to|must))\b",
            r"\b(yes you|i(?:'m| am) (?:talking|looking) (?:to|at) you)\b",
            r"\b(your host (?:here|speaking))\b",
            r"\b(most of you|some of you|those of you|you (?:assume|think|believe))\b",
        ],
    },
    {
        "id": "09-palms-up-questioning",
        "file": "character-pose-09-palms-up-questioning.png",
        "intent": "RHETORICAL",
        "vibe": "incredulous, 'come on now'",
        "best_for": "rhetorical reactions, 'what did you expect', incredulity",
        "cues": [
            r"\b(come on|seriously\??|what did (?:you|we) expect|are (?:you|we) (?:kidding|serious)|how (?:is|did) (?:this|that) (?:happen|make sense))\b",
            r"\b(give me a break|you can(?:'t| not) be serious)\b",
        ],
    },
    {
        "id": "10-hand-on-hip",
        "file": "character-pose-10-hand-on-hip.png",
        "intent": "CONFIDENT",
        "vibe": "cocky, told-you-so, swagger",
        "best_for": "confident calls, 'I saw this coming', vindication beats",
        "cues": [
            r"\b(told you|called (?:it|this)|saw (?:this|that) coming|knew it|exactly what (?:we|i) (?:said|predicted))\b",
            r"\b(confident(?:ly)?|no surprise|obviously|of course)\b",
        ],
    },
    {
        "id": "11-tipping-hat",
        "file": "character-pose-11-tipping-hat.png",
        "intent": "TRANSITIONAL",
        "vibe": "smooth sign-off, charming punctuation",
        "best_for": "transitions, sign-offs, 'and that, friends…', section enders",
        "cues": [
            r"\b(and that(?:'s| is)|so (?:there|here) you (?:have|go)|that(?:'s| is) (?:that|all)|moving (?:on|forward))\b",
            r"\b(until next time|see you (?:next|later)|farewell|signing off)\b",
        ],
    },
    {
        "id": "12-fist-at-chest",
        "file": "character-pose-12-fist-at-chest.png",
        "intent": "EMPHATIC",
        "vibe": "hard truth, climax line",
        "best_for": "emphatic delivery, 'this is what matters', climax / payoff",
        "cues": [
            r"\b(this is what (?:matters|counts)|the (?:hard|cold) truth|bottom line|at the (?:end|heart) of (?:it|this))\b",
            r"\b(non(?:-| )negotiable|essential|critical|the (?:point|whole point) is)\b",
        ],
    },
]

# Visually-similar pairs that should not be adjacent
ADJACENT_CONFLICTS = {
    ("04-one-hand-gesturing", "05-both-hands-explaining"),  # both single-arm-up
    ("08-pointing-at-camera", "04-one-hand-gesturing"),     # both right-hand-up
    ("08-pointing-at-camera", "06-thumbs-up"),              # both right-hand-up
    ("06-thumbs-up", "12-fist-at-chest"),                   # both closed-fist at chest
    ("04-one-hand-gesturing", "06-thumbs-up"),              # both right-hand-up
    ("01-arms-down", "10-hand-on-hip"),                     # both relaxed standing
}
# Make symmetric
ADJACENT_CONFLICTS = ADJACENT_CONFLICTS | {(b, a) for a, b in ADJACENT_CONFLICTS}


def score_pose(pose: dict, text: str) -> int:
    """Return number of cue regex hits in the text."""
    score = 0
    low = text.lower()
    for cue in pose["cues"]:
        if re.search(cue, low):
            score += 1
    return score


def select_poses(transcripts: list[str], history: list[list[str]] | None = None) -> list[dict]:
    """
    transcripts: list of 6 strings, one per talking-head clip in order.
    history: optional, list of recent episodes; each is a list of 6 pose-ids
             used in clips 1..6 of that episode. Most-recent-last preferred.

    Returns: list of 6 dicts with {clip, pose_id, pose_file, intent, reason}.
    """
    if len(transcripts) != 6:
        raise ValueError(f"need exactly 6 transcripts, got {len(transcripts)}")
    history = history or []

    # Per-slot usage count from history (cap at 3 most recent episodes)
    slot_history = [Counter() for _ in range(6)]
    for ep in history[-3:]:
        for i, pose_id in enumerate(ep[:6]):
            slot_history[i][pose_id] += 1

    picks: list[dict] = []
    used_in_this_episode: set[str] = set()

    for i, text in enumerate(transcripts):
        # Score every pose by cue matches
        scored = [(p, score_pose(p, text)) for p in POSE_LIBRARY]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Filter: not already used in this episode
        candidates = [(p, s) for p, s in scored if p["id"] not in used_in_this_episode]
        if not candidates:
            raise RuntimeError("ran out of poses — library too small?")

        # Filter: not visually-adjacent to previous pick
        if picks:
            prev_id = picks[-1]["pose_id"]
            candidates = [
                (p, s) for p, s in candidates
                if (p["id"], prev_id) not in ADJACENT_CONFLICTS
            ] or candidates  # fall back if filter eliminates all

        # Among top-tier (highest score), prefer ones least-used in this slot historically
        top_score = candidates[0][1]
        top_tier = [p for p, s in candidates if s == top_score]

        if top_score == 0:
            # No cue matched — default per-slot mapping for variety
            DEFAULT_BY_SLOT = ["01-arms-down", "05-both-hands-explaining", "03-arms-crossed",
                               "07-hand-on-chin", "04-one-hand-gesturing", "12-fist-at-chest"]
            for default_id in [DEFAULT_BY_SLOT[i]] + [p["id"] for p in POSE_LIBRARY]:
                pose = next((p for p in POSE_LIBRARY if p["id"] == default_id), None)
                if pose and pose["id"] not in used_in_this_episode:
                    if not picks or (pose["id"], picks[-1]["pose_id"]) not in ADJACENT_CONFLICTS:
                        chosen = pose
                        reason = f"no cue match, default slot-{i+1} pose ({pose['vibe']})"
                        break
            else:
                chosen = top_tier[0]
                reason = "fallback (no good candidate)"
        else:
            # Pick from top tier with least history-usage at this slot
            top_tier.sort(key=lambda p: slot_history[i].get(p["id"], 0))
            chosen = top_tier[0]
            cues_hit = sum(1 for c in chosen["cues"] if re.search(c, text.lower()))
            reason = f"intent={chosen['intent']}, {cues_hit} cue hit(s) in transcript"

        used_in_this_episode.add(chosen["id"])
        picks.append({
            "clip": f"th-{i+1}",
            "pose_id": chosen["id"],
            "pose_file": chosen["file"],
            "intent": chosen["intent"],
            "vibe": chosen["vibe"],
            "reason": reason,
            "transcript_preview": text[:80] + ("…" if len(text) > 80 else ""),
        })

    return picks


def main():
    if len(sys.argv) != 2:
        print("usage: select_poses.py path/to/input.json", file=sys.stderr)
        print('  input.json: {"clips":[{"id":"th-1","text":"..."},...],"history":[[ids],...]}', file=sys.stderr)
        sys.exit(2)
    inp = json.load(open(sys.argv[1]))
    transcripts = [c["text"] for c in inp["clips"]]
    history = inp.get("history", [])
    picks = select_poses(transcripts, history)
    print(json.dumps(picks, indent=2))


if __name__ == "__main__":
    main()
