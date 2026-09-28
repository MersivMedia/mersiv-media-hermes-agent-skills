"""Score hand labels with one skill's description overridden in process.

A/B a candidate skill description WITHOUT editing the SKILL.md: wraps the
decision plugin's live roster so one skill reports a new description (and,
optionally, a new "## When to Use" section), then scores the labels.

Written for Jermes (~/jermes); adapt the imports for another plugin.

Usage (run from the plugin repo, with the Jev key env loaded):
    JERMES_HOME=<eval dir> JERMES_CONFIG=<config.yaml> \
    PYTHONPATH=$HOME/hermes-agent:$HOME/jermes \
    .venv/bin/python score_candidate_description.py \
        <skill-name> "<new description>" <out.json> [when_to_use.md]

Then diff against a baseline scored on the CURRENT roster (not an old run):
    jermes score --json baseline.json
The roster is read live, so skills created since the last run change answers.
"""
import json
import sys
import time
from pathlib import Path

from jermes import cli, labels, replay
from jermes.points import skill_suggest

SKILL, NEW_DESC, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
NEW_WHEN = Path(sys.argv[4]).read_text() if len(sys.argv) > 4 else None

real_roster = skill_suggest.current_roster
real_body = skill_suggest.skill_body


def roster():
    out = []
    for s in real_roster():
        if s.name == SKILL:
            s = skill_suggest.Skill(s.name, NEW_DESC, s.body, s.category)
        out.append(s)
    names = {s.name for s in out}
    if SKILL not in names:
        sys.exit(f"{SKILL!r} is not in the live roster (disabled or misspelled?)")
    return out


def body(s):
    b = real_body(s)
    if s.name == SKILL and NEW_WHEN and "## When to Use" in b:
        start = b.index("## When to Use")
        nxt = b.find("\n## ", start + 5)
        b = b[:start] + NEW_WHEN.rstrip() + "\n\n" + (b[nxt + 1:] if nxt != -1 else "")
    return b


skill_suggest.current_roster = roster
skill_suggest.skill_body = body

h = cli._labelling_harness()  # batch budget: pacing + patient retries
turns = {labels.turn_key(t.session_id, t.message_id): t
         for t in replay.iter_turns(replay.default_db(), limit=100000)}
labs = labels.load_labels()


def predict(lab):
    t = turns.get(lab.key)
    return None if t is None else cli._jev_list(h, t)


for attempt in range(3):  # gateway 503 bursts: cached turns are free on retry
    rep = labels.score(labs.values(), predict)
    if not rep["errors"]:
        break
    time.sleep(45)
labels.print_score(rep)
OUT.write_text(json.dumps(rep, indent=2, default=str))
print(f"wrote {OUT}")
