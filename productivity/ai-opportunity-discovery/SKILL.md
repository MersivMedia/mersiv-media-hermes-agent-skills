---
name: ai-opportunity-discovery
description: Client AI opportunity analysis to dual PRDs, human-gated.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [consulting, prd, discovery, roi, ai-strategy]
    category: productivity
    related_skills: [docx, grounded-citations, xlsx, writing-plans]
---

# AI Opportunity Discovery Skill

Runs a client engagement end to end: pre-meeting intelligence on the company, its people
and its competitors plus a tailored discovery questionnaire; then, after the meeting, a
ranked AI opportunity analysis; then, after the strategist selects, two Word documents —
a technical PRD for engineering and a plain-language business case for the client with
ROI charts.

This skill does NOT invent client facts. Every pain point traces to the user's notes;
every market claim traces to a cited source. Unknowns become open questions, never
plausible guesses.

## When to Use

- User has a client meeting coming up and wants a brief plus questions to ask
- User supplies a company name and/or meeting notes and wants AI opportunity analysis
- User asks for a client-facing PRD, technical PRD, or ROI business case
- User says "run discovery on <company>" or references a prior engagement folder

## Prerequisites

- `web_search` for discovery. **Check `web_extract` works before relying on it** — when
  `web.extract_backend` is a search-only backend (ddgs) it returns an error instead of
  content. Fallback that works without any config change:
  ```bash
  curl -sL --max-time 45 -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) \
    AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36" "$URL" -o page.html
  python3 -c "
  import re,html
  t=open('page.html',encoding='utf-8',errors='ignore').read()
  t=re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>',' ',t)
  t=re.sub(r'(?s)<[^>]+>',' ',t); print(re.sub(r'\s+',' ',html.unescape(t)).strip()[:4000])"
  ```
  Corporate career subdomains and ATS tenants (Workday, Greenhouse) often 403 curl —
  those need `browser_exec`, which requires a running Chrome.
- `REPLICATE_API_TOKEN` for visual base plates (read from the repo `.env`; run those
  scripts from `terminal`, never `execute_code`, which doesn't inherit secrets)
- `python-docx`, `matplotlib`, `pillow`:
  `python3 -m venv .venv && ./.venv/bin/pip install -q python-docx matplotlib pillow`
  (a venv is required on PEP 668 "externally managed" systems)
- The `docx` skill's `scripts/docx_create.py` (this skill generates specs for it)
- Optional: LibreOffice (`soffice`) if the user also wants PDF

## How to Run

Workspace root: `~/.hermes/data/ai-opportunity-discovery/<company-slug>/`

```
<company-slug>/
├── prep/brief.md                  # pre-meeting intelligence
├── prep/questionnaire.md          # tailored questions for the meeting
├── inputs/notes.md                # verbatim post-meeting notes
├── research/findings.md           # cited market research
├── analysis/opportunities.md      # ranked register (the gate artifact)
├── analysis/selected.md           # approved subset
├── analysis/roi.json              # chart + totals input
├── prd/technical-prd.md
├── prd/client-prd.md
├── charts/*.png
└── out/*.docx                     # final deliverables
```

Create it with `terminal` on first run. Never use `/tmp`.

## Quick Reference

| Phase | Trigger | Output | Gate |
|---|---|---|---|
| 0.5 Pre-meeting | before client call | `prep/brief.md` + `prep/questionnaire.docx` | present both |
| 0 Intake | after client call | `inputs/notes.md` | ≤3 clarifying questions |
| 1 Research | | `research/findings.md` | none |
| 2 Analysis | | `analysis/opportunities.md` | **STOP — user selects** |
| 3 Technical PRD | | `out/technical-prd.docx` | none |
| 4 Client PRD | | `out/client-prd.docx` + charts | present both |

Phase 0.5 is independent — the user may invoke it alone ("I'm meeting Acme Thursday")
and return with notes days later.

**Templates:** `pre-meeting-brief.md`, `discovery-questionnaire.md`,
`opportunity-register.md`, `technical-prd.md`, `client-prd.md`.
**References:** `question-bank.md`, `scoring-rubric.md`, `architecture-patterns.md`.
**Scripts:** `make_charts.py`, `md_to_docx_spec.py`.

## Procedure

### Phase 0.5 — Pre-meeting intelligence and questionnaire

Runs before the client meeting. Goal: walk in already knowing everything public, so the
meeting is spent only on what can't be researched.

1. **Delegate the research.** Four workstreams, independent — dispatch them as a
   `delegate_task` batch (cap 3 concurrent) or run them yourself in parallel
   `web_search` calls. Each returns findings **with URLs**; discard uncited claims.

   - **Company** — what they sell, business model and unit economics, headcount and
     revenue estimates, funding/ownership, locations, recent news in the last 12 months,
     growth or distress signals.
   - **Stakeholders** — every named attendee plus the likely economic buyer. Role,
     tenure, prior companies, public talks/posts/interviews, what they were hired to
     fix. Sources: LinkedIn, company site, podcasts, conference listings, press quotes.
   - **Competitors** — 3-5 closest peers, what AI they have publicly deployed, published
     results with real numbers. This establishes whether the client is ahead or behind.
   - **Vertical and tech signals** — standard workflows and cost centers for this
     business model, regulatory regime, and **their job postings** (highest-signal
     public source for internal tooling — check the careers page).

2. **Write `prep/brief.md`** from `templates/pre-meeting-brief.md`. The load-bearing
   sections are §7 Hypotheses (3-5 specific, falsifiable guesses about where the money
   is leaking) and §8 What I Could Not Find. Everything else is context; those two
   drive the questionnaire.

3. **Build `prep/questionnaire.md`** from `templates/discovery-questionnaire.md`,
   selecting 12-18 questions from `references/question-bank.md`. Selection rules:
   - Delete every question the desk research already answered. Asking what the company
     does destroys the credibility the brief just earned.
   - Every question must feed a cell in the opportunity register or test a hypothesis.
   - Mark the ROI-critical ones ★ — volumes, minutes-per-unit, headcount, loaded
     hourly cost, error rate. Without these there is no defensible model.
   - Keep AI vocabulary out of the client-facing questions entirely.
   - Rewrite generic bank questions in the client's own domain language (their word for
     the transaction, their system names).

4. **Render the questionnaire to Word** (see Producing .docx below) so the user can
   print or take it into the meeting. Present the brief in chat as a summary: who's in
   the room, what each one wants, the hypotheses, and the opening line.

### Phase 0 — Intake

1. Save the user's notes verbatim to `inputs/notes.md`. Do not paraphrase yet.
2. If Phase 0.5 ran, reconcile: mark each hypothesis confirmed / killed / unclear, and
   fill the capture grid. Killed hypotheses get recorded — they explain later why an
   obvious-looking opportunity isn't in the register.
3. Echo back a structured summary: company, pain points, systems named, decision makers,
   budget and timeline signals.
4. One `clarify` call, max 3 questions, ONLY for un-researchable blockers still missing
   after the meeting — typically headcount, tooling, loaded hourly cost. Everything else
   is researchable; do not ask.

### Phase 1 — Market Research

Deepen Phase 0.5 with what the notes now point at. Cite every non-obvious claim.

1. **Benchmarks** for the specific workflows the client named — published time-savings
   or cost-per-task figures. Prefer vendor-neutral studies over vendor marketing.
2. **Competitive case studies** with real numbers, to cite in the client PRD.
3. **Regulatory detail** on anything the client flagged — these gate architecture.
4. **Vendor landscape** for each candidate workflow, so the technical PRD's build-vs-buy
   comparison is real rather than rhetorical.

Write `research/findings.md`. Mark unsourced figures `[UNVERIFIED — needs client data]`.

### Phase 2 — Opportunity Analysis (the gate)

1. Map every pain point in the notes to one or more candidate interventions. A pain
   point with no viable AI intervention gets said out loud — that builds credibility.
2. Fill a register entry per opportunity from `templates/opportunity-register.md`:
   traced pain point, architecture pattern from `references/architecture-patterns.md`,
   annual hours and dollars, effort, data readiness, risk, confidence, assumptions.
3. Score with `references/scoring-rubric.md`. Rank by **score, not dollars** — a cheap
   fast win outranks a speculative moonshot, and the first project's job is to buy trust
   for the second.
4. Show ROI arithmetic inline:
   `120 invoices/wk × 14 min × 52 wks × 0.7 automation ÷ 60 = 1,019 hrs/yr × $48/hr = $48,900/yr`
   Every multiplier is cited, from the notes, or flagged as an assumption.
5. Write `analysis/opportunities.md`, then **STOP**. Present the ranked table in chat and
   ask which to advance. Draft no PRD before the user answers. Record the selection and
   any stated reasoning in `analysis/selected.md`.

### Phase 3 — Technical PRD

Use `templates/technical-prd.md`. Per opportunity: problem statement, mermaid system
context, recommended architecture with a named rejected alternative, model/tooling with
cost per transaction, data pipeline, integration and auth, evaluation plan with concrete
acceptance metrics, guardrails and failure modes, HITL checkpoints, security and
compliance, phased roadmap with dependencies.

Rules: recommend patterns, not vendors, unless the stack forces one. Specify how the
system is evaluated before how it is built. Always include the "do nothing / buy
off-the-shelf / build" comparison — engineering trusts a doc that admits build isn't
always right.

### Phase 4 — Client PRD and charts

Use `templates/client-prd.md`. Eighth-grade reading level. No jargon: not "RAG" but
"the system looks up your own documents before answering."

Write `analysis/roi.json` — one object per approved opportunity with `name`,
`hours_per_year`, `dollars_per_year`, `effort_weeks`, `one_time_cost`,
`monthly_run_cost`, `start_month` (schema in the script docstring). Then:

```bash
python3 ~/.hermes/skills/productivity/ai-opportunity-discovery/scripts/make_charts.py \
  --input analysis/roi.json --outdir charts/
```

Emits `savings_by_opportunity.png`, `payback.png` (break-even month annotated),
`effort_impact.png` (quick-wins quadrant), `timeline.png`. It also prints totals and the
payback month as JSON — use **those** numbers in the PRD prose so text and charts can't
disagree. Reference images with paths relative to the markdown file.

Close with the assumptions table. Every ROI number the client sees must be traceable to
an assumption they can challenge; that is what survives a CFO review.

### Producing .docx

Both PRDs and the questionnaire ship as Word. Two steps — markdown to spec, spec to docx:

```bash
SKILL=~/.hermes/skills/productivity/ai-opportunity-discovery
DOCX=~/.hermes/skills/productivity/docx/scripts

python3 $SKILL/scripts/md_to_docx_spec.py prd/client-prd.md \
  --out build/client.spec.json --theme client --toc \
  --title "Acme Co — AI Opportunity Plan" \
  --subtitle "Prepared for Jane Doe · March 2026" \
  --footer "Acme Co · Confidential"
python3 $DOCX/docx_create.py build/client.spec.json out/client-prd.docx

python3 $SKILL/scripts/md_to_docx_spec.py prd/technical-prd.md \
  --out build/tech.spec.json --theme technical --toc \
  --title "Acme Co — Technical PRD" --footer "Internal · Draft for eng review"
python3 $DOCX/docx_create.py build/tech.spec.json out/technical-prd.docx
```

`--theme client` is warm with wide margins; `--theme technical` is denser. The converter
handles headings, tables, lists, images, blockquotes (rendered as callouts), code blocks,
and inline bold/italic/links. `--title` suppresses the markdown's own H1 so the cover
isn't duplicated; H1s become page breaks.

Verify every document:

```bash
python3 $DOCX/docx_read.py out/client-prd.docx --structure
python3 $DOCX/docx_validate.py out/client-prd.docx
```

PDF, only if asked and `soffice` exists:
`soffice --headless --convert-to pdf --outdir out/ out/client-prd.docx`

## Pitfalls

- **Never fabricate client operational data.** Missing hours, volumes, or salaries get
  asked once, then carried as an explicit labeled assumption.
- **Don't skip the Phase 2 gate.** Drafting PRDs for unapproved opportunities is the
  single most common failure of this workflow.
- **A questionnaire that asks what you already researched** wastes the meeting and reads
  as unprepared. Cut ruthlessly against the brief.
- **Stakeholder research goes stale fast.** Re-check titles the week of the meeting;
  presenting someone with a former title is a credibility hit.
- **Vendor case studies inflate.** Discount published savings claims, and say you did.
- **Compliance kills architectures late.** Surface HIPAA/GDPR/residency in Phase 0.5,
  not Phase 3.
- **Client PRD leaking technical terms** is the top reason these documents fail. Re-read
  it and strip anything an operations manager wouldn't say.
- **Mermaid diagrams don't render in Word.** The converter inserts a placeholder plus
  the source. For a client-facing diagram, produce an image instead.
- **Word fields show placeholder text until opened.** TOC and "Page X of Y" populate
  when Word/LibreOffice opens the file — not a bug; don't try to fix it.
- **Custom style names must not collide with Word built-ins.** `docx_create.py` raises
  `ValueError: document already contains style 'X'` for names like `Caption`, `Subtitle`,
  `Quote`. This skill's styles are namespaced (`PRDCaption`, `PRDCode`, `PRDCallout`,
  `PRDSubtitle`) — keep that prefix if you add more.
- **Charts overwrite on rerun.** Use a fresh `--outdir` for a revised version so you
  don't clobber images already sent to the client.

## Verification

- [ ] Questionnaire contains nothing the brief already answered, and all ★ ROI inputs
- [ ] Every pain point in `inputs/notes.md` is in the register or explicitly marked
      "no AI intervention recommended, because ..."
- [ ] Every dollar figure has visible arithmetic and a labeled assumption
- [ ] Every market claim has a URL
- [ ] Technical PRD has acceptance metrics per opportunity and a build-vs-buy comparison
- [ ] Client PRD contains zero unexplained technical terms
- [ ] PRD prose totals match `make_charts.py` printed totals exactly
- [ ] `docx_validate.py` exits 0 on every produced document
- [ ] `docx_read.py --structure` shows the expected heading outline and no missing images
