---
name: job-interview-company-prep
description: "Prep a job interview: company, interviewer, role plan, PRDs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, interview, job-search, briefing, prd, discovery]
    category: research
    related_skills: [account-intelligence-briefing, grounded-citations, google-workspace, blocked-page-recovery, executive-stakeholder-research]
---

# Job Interview Company Prep Skill

Candidate-side prep for a job interview. The user names a company, an
interviewer or a job posting. They get back up to three deliverables, usually
requested one after another:

① an interview briefing,
② a "first 90 days as if I had the job" assessment,
③ one PRD per top initiative.

The evidence rules match `account-intelligence-briefing`, but the reader is a
candidate, not a seller. Cover letters and resumes are out of scope (see
`resume-variant-maintenance`).

## When to Use

- "Research this company, I'm interviewing with <name> / for <posting URL>."
- "Outline an initial assessment as if I had the job, list 10 things, scope a top 5."
- "Make a PRD for <initiative> based on your research."
- "What questions should I ask different departments?"

## Prerequisites

- `web_search` and `terminal` (curl). `web_extract` may be a search-only
  backend that returns an error, so check it once and then use curl. The
  helper is in `references/source-map.md`.
- `grounded-citations` `scripts/sources.py`, with one ledger per document.
- `google-workspace` `md2gdoc.py --company "<Company>"`, which files docs
  into `<Company>/Research/`.
- A workspace at `~/.hermes/data/research/<company-slug>/`. Never `/tmp`.

## How to Run

1. **Clarify the minimum in one `clarify` call:** company, role or posting
   link, and interviewer. Users often answer the wrong box. If only an
   interviewer name comes back, search `"<Full Name>"` and offer the
   namesakes as choices. Default delivery is a Google Doc in the company
   folder.
2. **Read the posting first.** It usually gives the pay, the 90-day plan, the
   success metric, the stack, and who the role reports to.
3. **Read every other open posting.** Pull the ATS index page (for JazzHR,
   `<co>.applytojob.com`). Each department's job ad admits its own problems,
   and those admissions drive deliverables ② and ③.
4. **Identify the interviewer** from the company team page, listing everyone
   who holds that title. If the user gives only a title, match it to the
   posting's reporting line and location. Flag any second person with the
   same title.
5. **Establish company momentum** from press releases, executives' LinkedIn
   posts (recent metrics) and the company page (headcount). Note where
   sources disagree, for example on founding year or brand count, and tell
   the user not to recite those figures.
6. **Write, cite, verify, convert, and read the doc back** (Procedure §5).

## Quick Reference

| Deliverable | Load-bearing sections |
|---|---|
| ① Briefing | 6 things to know · who's interviewing (with namesake warning) · the company · the role decoded (stack, admitted problems, their 90-day plan, pay) · 6 hypotheses · stories to prepare · questions for the interviewer · landmines · weak culture signals · gaps |
| ② 90-day assessment | What the other postings reveal · tensions to resolve · weeks 1–3 discovery Sheet with a scoring formula · 10 candidates · scoring matrix · top 5 scoped · why the other 5 rank lower · tech guardrails · questions by department · risks · gaps |
| ③ PRD, one per initiative | `templates/internal-automation-prd.md` |

Title formats:
- `<Company> — Interview Briefing: <Role> (<Mon YYYY>)`
- `<Company> — First 90 Days: ... (Hypothetical)`
- `<Company> — PRD: <Initiative> (Hypothetical v0.1)`

## Procedure

### 1. Briefing (①)

- **Split what's verified from what's guessed.** State the Class A / Class B
  split at the top.
- **Structure answers around the posting's own 90-day plan.** Show how the
  candidate would run it.
- **Stories table:** map each required item to a concrete example to have
  ready. If the posting measures outcomes ("hours eliminated, not scripts
  shipped"), say what kind of artifact to bring.
- **Landmines:**
  - Questions the posting already answers, such as asking about remote work
    when it says onsite.
  - Framing value as "replacing people". Say "the same team absorbs growth"
    instead.

### 2. Assessment (②)

- **Open with a table** of what each department's posting admits, quoted
  directly.
- **Score each candidate on five columns:**
  - hours per week
  - whether it grows with the business
  - cost of errors
  - effort (lower is better)
  - "no other owner"

  The "no other owner" column pushes down work already owned by a new hire,
  an in-house platform, or engineering. Explaining those demotions is
  judgement worth showing in the room.
- **For each top-5 item, cover:**
  - the problem
  - the likely current state (Class B)
  - what to remove before automating anything
  - the design
  - who owns it with you
  - sizing, with the arithmetic shown and tagged `[ASSUMPTION]`
  - success metrics
  - MVP timeline
  - what would rule it out
- **Question bank:** 3 questions for every department, then near-verbatim
  questions per department, each tagged to the posting that prompted it.

### 3. PRDs (③)

- **Make a separate doc for each initiative.**
- **Check every integration claim against the vendor's own docs**, and cite
  it: exact webhook and notification names, which plan tier a feature needs,
  quotas. `references/source-map.md` lists vendor docs that fetch cleanly.
- **Non-goals must include:**
  - never auto-submitting to external platforms
  - not duplicating the company's in-house platform or engineering pipelines
- **Where engineering already owns a data pipeline,** the PRD adds to it. It
  doesn't propose a second connection.
- **If the user names a third-party model to build in** (for example "use
  TRIBE v2 for attention A/B tests"), vet it before designing. Check three
  things from primary sources: the license (including upstream dependencies),
  what it actually outputs versus the metric the user named, and whether
  anyone has tested it independently.
  - If any answer is unfavourable, ship the parts that don't depend on the
    model, and report the finding in chat BEFORE building a gated section
    for it. Offer: drop it, or swap in a commercially licensed alternative.
  - A gated "research track" (blocking license gate + validation design) is
    a last resort. In the Luminize session the user read the findings and
    said "let's remove the TRIBE v2 testing." The version that stayed was the
    plain pipeline: cheap rubric MVP → optional licensed tool trial → keep a
    method only if it beats a coin flip on the platform's own A/B results.
  - When asked to remove it, keep the old draft as `<doc>_v01_with_<x>.md`,
    use a fresh citation ledger (drops sources only the removed part
    needed), bump the version in the title, update with `--doc-id`, and
    grep the text export for the removed terms (should find zero).
  - See `references/third-party-model-vetting.md`.

### 3b. Keep named people current

The company's LinkedIn page (`linkedin.com/company/<slug>`, curl with a
browser UA) shows new-hire welcome posts and work anniversaries. Before the
interview, or when the user asks "check whether they hired X", fetch it and
the recruiter's profile. When an adjacent role gets filled:

- **Briefing:** add a "Who you'd work alongside" section with verbatim
  quotes. Mark the old "role is open" line as filled. Raise the confidence
  on the matching overlap hypothesis. Add a boundary question naming the
  person.
- **Every PRD:** add the person to the owner field and to dependencies. Turn
  `[ASSUMPTION]`s their job confirms into facts (e.g. "BigQuery confirmed").
  Add a risk for scope overlap, and an open question on who defines shared
  metrics.
- **Ledgers:** add the company page and the recruiter post to each doc's
  ledger, reusing an existing ID if the URL is already there.
- **Dates:** feeds show relative dates ("2d"), so write "around <date>".
  Offer to capture the permanent post URLs while the posts are still near the
  top of the feed.
- **Revise with `--doc-id`,** then grep the export for the new names and
  source URLs.

### 4. Evidence rules

- **Snippet-only facts** (Glassdoor, RocketReach, Indeed) get
  `[UNVERIFIED, snippet only]`.
- **Every volume figure in ② and ③ gets `[ASSUMPTION]`.** In chat, tell the
  user these are placeholders, to be presented as "here's how I'd measure
  it", not as findings.
- **Point out where postings contradict each other**, for example "no
  engineering team" in one and "our engineering team built the pipelines" in
  another. These make good interview questions.

### 5. Build and verify

```bash
S=~/.hermes/skills/research/grounded-citations/scripts/sources.py
export HERMES_CITATION_LEDGER=~/.hermes/data/research/<slug>/ledger_<doc>.json
python3 $S reset; python3 $S add <url> --title "..."    # at retrieval time
python3 $S render --replace-in doc.md && python3 $S verify doc.md
python3 ~/.hermes/skills/research/job-interview-company-prep/scripts/sources_to_list.py doc.md doc_upload.md
python3 ~/.hermes/skills/productivity/google-workspace/scripts/md2gdoc.py \
  doc_upload.md --title "<Company> — ..." --company "<Company>"
```

Then export the Doc as text/plain and grep for known strings: a requirement
ID from the middle, the last table, and the final source. Only report the doc
as done after that check passes.

## Pitfalls

- **Namesake collisions.** A famous person with the same name will dominate
  search results. List every match you find (company and city), ask the user
  which one, and name the one to ignore in the doc.
- **The user gives a title instead of a name mid-task.** Resolve it from the
  team page, the reporting line and the location. State your confidence and
  give a cheap way to check it, such as the name on the calendar invite.
- **LinkedIn hides experience details from logged-out viewers**, showing
  asterisks. Don't rebuild someone's history from aggregator sites and
  present it as fact.
- **md2gdoc `verified_chars` can be about half the source length** on PRDs
  that are mostly tables, because markdown syntax is stripped. That alone
  doesn't mean truncation. Read the export back instead.
- **Sources collapse into one paragraph** in Docs unless each line becomes a
  list item. `scripts/sources_to_list.py` fixes this on a copy of the file.
- **`verify --strict` fails on low coverage for design-heavy docs**, because
  most of their sentences are Class B. Use plain `verify` as the gate there:
  no unknown IDs, and the Sources block matches. Tag inferences rather than
  padding with citations.
- **More than 3 citations in one sentence** triggers a warning. Split the
  sentence so each citation sits next to its own claim.

## Verification

- [ ] Interviewer identity stated with a confidence level, and namesake warned about.
- [ ] Posting's 90-day plan and success metric quoted.
- [ ] Every other open posting fetched and used in ②.
- [ ] Every hours or volume figure tagged `[ASSUMPTION]`, with arithmetic.
- [ ] Integration names checked against vendor docs and cited.
- [ ] Any user-named third-party model checked for license, what it actually
      measures, and independent evidence before it appears as a component.
      If it fails, the user was told in chat and offered drop/swap before a
      gated section was written.
- [ ] Company LinkedIn feed re-checked for new hires and directors in
      adjacent roles; named owners carried into every PRD.
- [ ] `sources.py verify` exits 0 for every doc.
- [ ] Every Doc read back as a text export, with its middle and end present.
- [ ] Docs filed in `<Company>/Research/`, titles starting with the company name.

## Support Files

- `references/source-map.md`: which sources fetch with plain curl, which
  block, the curl and tag-strip helper, and how to handle LinkedIn's hidden
  fields.
- `templates/internal-automation-prd.md`: PRD skeleton for internal tooling
  or automation work.
- `references/third-party-model-vetting.md`: license / output / independent
  evidence checks for a user-named model; the gated-research-track pattern
  with pairwise-accuracy sample sizes; TRIBE v2 worked finding; the
  contribution-margin ACoS formulas for ad-analytics PRDs.
- `scripts/sources_to_list.py`: turns a rendered `## Sources` block into
  list items before uploading.
