# Hand-labelled evaluation for a decision point

When the user asks "how can I score the results?", the answer is an answer key:
real turns where a human wrote down the correct decision. Agreement with what
the agent did is only a weak label, because the agent is often wrong too.
This was built as `jermes label` / `jermes score` in `~/jermes/jermes/labels.py`;
copy it as a starting point.

## Label shape

- **Labels are sets.** One turn can need several skills (a research doc needs
  the doc skill and the citation skill). An empty set means "no skill needed".
- **Storage:** append-only JSONL at `$JERMES_HOME/labels.jsonl`, one row per
  answer with a key of `session_id#message_id`. The latest row for a key wins,
  and a `{"key", "skip": true}` row removes that turn. Stopping and resuming is
  free: the next session offers only unlabelled keys.
- **Redact** the request text before writing it, since labels files get shared.
- **Validate names against the live roster.** Map typos to "did you mean"
  suggestions rather than storing a label that can never match.

## Two ways to label

1. **Terminal, one turn at a time.** Show the last 4 non-blank messages, the
   request, what the agent loaded and Jev's list. Shortcuts:
   - enter: accept Jev's list
   - `a`: accept what the agent loaded
   - `n`: no skill needed
   - comma-separated skill names
   - `s`: skip
   - `q`: quit
2. **Spreadsheet round trip (best on a phone).** Export a CSV with the columns
   `key, request, earlier_conversation, agent_loaded, jev_lists,
   correct_skills`. The user fills in `correct_skills` (names, `none`, or blank
   to skip), then import it back. Support `--import gdrive:<sheet-id>`, which
   exports the Sheet as CSV via the Drive API, so the user never downloads a
   file on the phone.

**Getting the CSV into Drive as a Google Sheet.** Upload it with
`drive.files().create(body={"name", "parents", "mimeType":
"application/vnd.google-apps.spreadsheet"}, media_body=MediaFileUpload(csv,
mimetype="text/csv"))`. Drive converts it on upload, and this needs only the
Drive API. Formatting (a frozen header, column widths, a highlighted input
column) needs the Sheets API `batchUpdate`, which is a separate API that must
be enabled on the Google Cloud project. If it returns `SERVICE_DISABLED`, ship
the unformatted Sheet and give the user the enable link. Don't block on it.
Read the Sheet back with `files().export(mimeType="text/csv")` to verify.

## Metrics: report Jev and the agent side by side

| Metric | Definition |
|---|---|
| Decision accuracy | `bool(pred) == bool(gold)` over all turns |
| Primary hit | `pred[0] in gold`, over turns that need a skill |
| Recall | `|gold ∩ pred| / |gold|`, summed over turns |
| Precision | `|pred ∩ gold| / |pred|`, summed over turns |
| False alarms | Something listed on a turn whose gold is empty |
| Misses | Nothing listed on a turn that needs a skill |

- Compare names on the leaf: `split(":")[-1].split("/")[-1].lower()`.
- Scoring the agent's own loads with the same code shows whether Jev *beats*
  the agent, not just whether it copies it. That is the question the user
  actually cares about.
- Rerun Jev at score time through the same replay path, including the rebuilt
  context. The decision cache makes this free, and it lets a changed setting
  (context size, threshold) be rescored on the same labels.

## Sizing

- About 40 labelled turns is enough to compare two settings.
- 100 or more is needed to tune thresholds.
- Mix turns where the agent loaded a skill with turns where it loaded
  nothing, or false alarms can't be measured.

## Comparing two settings on the labels

- **Pair strictly.** Score each setting with `--json`, then compare only the
  keys present in BOTH reports. If one arm lost turns to provider errors
  ("2 could not be scored"), rerun that arm after a short cooldown. Cached
  turns are free, so only the failed ones cost anything. Don't report a
  comparison over different turn sets.
- **Report per-turn changes as well as the aggregate** ("fixed N, broke M"),
  quoting each changed turn with its label and both lists. With 40 turns,
  differences of 1–3 turns are directional, not conclusive; say so.
- **Keep per-turn correctness a real `bool`.** An expression like
  `(set_a & set_b if g else not pred) and ...` returns a *set*.
  `json.dumps(..., default=str)` then writes it as a truthy string. The first
  "fixed 0, broke 2" comparison was wrong for this reason (the real answer
  was 2 and 2). Use a helper such as `_turn_ok(pred, gold) -> bool`, and test
  that it survives a JSON round trip.

## Label bias: anchoring on the shown suggestion

The sheet showed Jev's list next to the blank answer column, and 26 of 40
labels matched it exactly. The arm whose list was shown is flattered. When
reporting, state the overlap count as a caveat. For the next batch, offer a
**blind** sheet: omit the `jev_lists` column (and ideally `agent_loaded`)
so the labels are independent of both.

## Error analysis after scoring

Group Jev's wrong turns by the skill that was missed. In batch 1, one skill
(`runpod-pods`, needed on 13 turns, listed on 3–4) explained most misses. Its
description ("Rent RunPod GPUs for models too big to run locally.") covered
none of what the requests asked for (stopping pods, volumes, checking what's
running). **A skill's description is often a bigger lever than any context
or threshold setting.**

- Propose a rewrite of that description.
- The user's own skills under `~/.hermes/skills/` are theirs: show the new
  wording and get approval before editing.
- Rescore on the same labels afterwards.

### Rewriting a skill description: verify first, then A/B

The user's labels encode what they *expected* a skill to do; they said "make
sure the skill actually does those things though, I may have been wrong".
A description must never promise capability the skill lacks, or Jev routes
requests to a skill that then fails.

1. **Audit the skill's code, not just its prose.** Read `scripts/*` and map
   each capability the labels imply to a concrete command (e.g.
   `pod.py volumes / create --volume / list / stop / terminate`). Report a
   table: capability, supported yes/no/partial, how. Mark gaps honestly
   ("see what's installed" = only via `ssh`, no dedicated command).
2. **Run only the read-only commands live** (`balance`, `list`, `volumes`).
   Never create a paid resource just to test a stop/terminate path; say it
   was verified by code reading.
3. **Cross-check claims against the provider's docs** while you're in there.
   Fetch `https://docs.<provider>/<page>.md` (many doc sites serve raw
   markdown) and correct anything stale in the SKILL.md and in script output
   strings. Found this way: the skill said stopping a RunPod pod "keeps
   container disk"; RunPod docs say stop **clears** the container disk and
   keeps only `/workspace`. That's a data-loss trap, so fix it and tell the user.
4. **A/B the candidate wording before editing the file.** Score the labels
   with the skill's description (and "When to Use" body) overridden in
   process, by wrapping `skill_suggest.current_roster` and `skill_body`. The
   runnable version is `scripts/score_candidate_description.py`. Only
   write the SKILL.md once the candidate wins, then rescore from disk to
   confirm Hermes' discovery returns the new text.
5. **Keep the description short.** One sentence naming the lifecycle verbs
   users actually type (launch, check what is running, stop, terminate).
   Batch-1 result: `runpod-pods` went from being listed on 3 of the 13 turns
   that needed it to 8 of 13, and primary hit rose from 59% to 72%, with zero
   new false alarms.

### Roster drift contaminates comparisons

Because the roster is read live, a skill created by another session between
two scoring runs changes Jev's answers. During the rewrite A/B,
`job-interview-company-prep` appeared and took the first slot on two
interview turns whose labels predated it, which looked like the edit
"broke" them. **Before attributing a difference to your change, re-score the
baseline on the current roster** (same labels, same config, no edit) and
diff the two JSONs. Scan the new run's lists for skill names that aren't in
any label or earlier run. Report such skills to the user as label updates
they may want to make.

When publishing a history of changes, each "what moved the numbers" row must
use the baseline measured on the same roster as its "after". Rows can then
disagree (row 2's "before" 59% is lower than row 1's "after" 69%). Say why in
one sentence under the table rather than hiding it.

**Before quoting a drift claim, verify it** (e.g. count how many rows have the
new skill ranked first and marked wrong). The user reads the README
critically.

## Tests worth keeping

- Pin the metric maths on a 5-turn fixture covering: a correct pair, a wrong
  skill, a miss, a false alarm, and a correct none.
- An interactive session driven by a scripted `ask=`, including a typo
  re-prompt and resume.
- The CSV round trip, plus import reporting typos as problems.
- A constructed fake key never reaches the labels file.
