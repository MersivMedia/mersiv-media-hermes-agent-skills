---
name: account-intelligence-briefing
description: Turn company research into a meeting plan and ROI case.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, sales, discovery, pre-meeting, roi, account-planning, briefing]
    category: research
    related_skills: [executive-stakeholder-research, blocked-page-recovery, google-workspace, grounded-citations]
---

# Account Intelligence Briefing

Turns raw company research into three things a person can act on: a
**pre-meeting briefing**, a **discovery question set organised as falsifiable
hypotheses**, and an **ROI-sized opportunity portfolio**. It assumes the
leadership map already exists — build that first with
`executive-stakeholder-research`, then run this on top.

This skill is about judgement, not data collection. Its value is the framing
rules: what to lead with, what will get you thrown out, and how to size a
number the buyer's CFO cannot dismiss.

## When to Use

- "Prepare me for a meeting with \<company\>."
- "Where could AI / automation deliver ROI at \<company\>?"
- Pre-sales account planning, partner strategy, or investor diligence prep.
- Any request that ends in a meeting rather than a document.

## Prerequisites

- `executive-stakeholder-research` run first (leadership, tenure, quotes).
- `terminal` with network access; `web_search`.
- `blocked-page-recovery` for job boards and corporate sites behind WAFs.
- `google-workspace` if the user wants a Doc deliverable.
- No API keys required.

## How to Run

1. **Ask what they're bringing** — offering, or discovery? It changes the
   entire document. If they don't know, write it as discovery.
2. **Leadership map** (`executive-stakeholder-research`).
3. **Pull the latest quarter** — SEC 8-K Item 2.02 or the earnings release.
4. **Pull job postings** — see "Job postings are the best signal" below.
5. **Build hypotheses**, not conclusions.
6. **Size the opportunities** with visible arithmetic.
7. **Write the briefing** in the output contract.

## Quick Reference

| Signal | Where to find it | What it tells you |
|---|---|---|
| Is the pain real | Two independent sources naming it | Confidence to lead with it |
| Who holds budget | Reporting line in appointment press release | Who to meet first |
| Build vs buy | Engineering job postings | Whether they'll buy at all |
| The actual tech stack | Job posting requirements | Integration effort, credibility |
| Admitted problems | Senior job posting "responsibilities" | Quote it back — they said it, not you |
| Unfilled senior role | Posting age + seniority | A decision vacuum you can enter |
| What's culturally forbidden | Awards, careers page, CEO language | What framing gets you removed |
| Budget threshold | Last quarter's margin trend | How hard the ROI case must work |

## Procedure

### 1. Job postings are the best signal, and most people skip them

Earnings calls are rehearsed. Job postings are written by managers describing
problems they actually have, and they are rarely sanitised.

Extract from every senior/technical posting:
- **Named systems** — the stack, free. Warehouse, ERP, CRM, CMS, LOS, BI.
- **Admitted problems.** Senior postings often confess: "reduce complexity,
  duplication, technical debt, and cost." **You can quote that back. They
  wrote it.**
- **Build-vs-buy posture.** Hiring in-house developers on a modern framework
  means they build. Selling a platform into a build culture fails.
- **Vendor language.** "Vendor selection", "implementation partners",
  "strategic partnerships" in a JD = budget for outside help.
- **Unfilled senior roles** = a decision vacuum, and a clock. Note the posting
  age; if it's filled before the meeting, the entry point closes.
- **Headcount as a symptom.** Five customer-service reqs in five states is a
  load problem being solved with people.

**Getting them:** company careers sites (`careers.<company>.com`) and Indeed
are usually behind enterprise WAFs that block by IP — a real browser on the
same network gets the same 403. **LinkedIn job search renders and is
readable**; use `blocked-page-recovery` route 6. Search several role-keyword
queries (`"<company>" technology`, `... purchasing`, `... director`) rather
than paginating one query — pagination duplicates heavily. Dedupe on
(title, location) and **state in the output that the list may be incomplete.**

### 2. Build hypotheses, not conclusions

You have not spoken to them. Everything you infer is a prior.

Structure each as: **claim → evidence → confirming question → what kills it.**
Five or six is right. Label each `CONFIRMED` (disclosed in a filing),
`LIKELY` (two independent sources), or `OPEN`.

Tell the user plainly: *roughly a third of these will be wrong, and the wrong
ones are the valuable ones* — they're where the model of the business breaks.

### 3. Separate verified from inferred, visibly

Two classes, stated at the top of the document:
- **Class A — Verified.** Filings, earnings releases, quotes, job postings.
- **Class B — Inferred.** Predicted answers, sizing, ROI.

Every Class B item carries a confidence level. Conflating them is how a
briefing becomes a liability in the room.

### 4. Size opportunities with visible arithmetic

Derive everything from **disclosed** figures — revenue, margin, SG&A ratio,
unit counts, average price. Show the chain so the reader can attack it:

```
Options revenue  ≈ 10% of ASP × deliveries       → $273M
Options margin   ≈ 35%
3% attach lift   → $8.2M revenue → $2.9M gross profit
```

Mark every assumption `[ASSUMPTION]`. Give conservative and optimistic ends,
never a single number.

**Discount your biggest number.** The largest line is usually the least
attributable — a demand-side metric moved by macro, not by anything you'd
sell. A CFO will say so and be right. Pre-empt it: present that one as a
**controlled experiment with a defined cost**, not as promised value.
Volunteering to be measured is the strongest trust signal available.

Then give a **defensible subtotal excluding it**. Understating beats a
headline that triggers disbelief.

### 5. Find the guardrails before the opportunities

Every company has framings that get you removed. Look for:

- **Brand/positioning language from the CEO** ("premium", "price over pace").
  Anything reducing perceived quality is dead on arrival.
- **Workplace awards** (Fortune Best Companies, Great Place To Work). Culture
  is a public asset. **Never frame value as headcount reduction.** Reframe:
  *the same team absorbing growth without adding people.*
- **A long-tenured operator with a large retention package.** Enormous
  internal credibility. Never route around them; never hand them a black box.
- **Regulated domains.** Consumer lending, housing, health, credit → fair
  lending/housing, ECOA, GLBA, HIPAA. Put compliance in the risk register at
  critical severity, not in a footnote.

### 6. Sequence the meetings by who can say yes

Rank by (owns the budget) × (has publicly described the problem) ×
(needs a visible win). Newly-scoped executives — under ~2 years in an
expanded remit — are the strongest first meetings. Long-tenured founders are
who you get referred *up* to, not who you open with.

### 7. Pick the beachhead deliberately

Prefer a **greenfield unit** — a new division, region or product line — for
any pilot: no legacy process to fight, cleaner measurement, lower political
cost of failure. Verify it has enough history to measure; if not, fall back
to a mature unit and say why.

### 8. Design for the parent, not just the subsidiary

If the target was recently acquired, the real market is the acquirer's whole
portfolio. Build artifacts **portable** — no hard-coding to one instance —
and the eventual conversation is with the parent, not one subsidiary.

## Output Contract

Markdown, then optionally a Doc via `md2gdoc.py`.

**Drive filing convention — always follow this.** Every company gets one
folder at Drive root named exactly for the company, with documents in a
`Research/` subfolder beneath it. Never drop research docs loose in the root.

```bash
MD2GDOC="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/md2gdoc.py"

$MD2GDOC briefing.md proposal.md prd.md \
  --title "<Company> — Pre-Meeting Briefing (<Mon YYYY>)" \
  --title "<Company> — AI Opportunity Assessment & Engagement Proposal" \
  --title "<Company> — Technical PRD: <Scope>" \
  --company "<Company>"
```

That produces `<Company>/Research/` (find-or-create, safe to re-run) and files
everything inside. Re-running for the same company reuses the folder rather
than duplicating it, so the structure stays consistent across engagements:

```
Example Homes/
  Research/
    Example Homes — Pre-Meeting Briefing (Aug 2026)
    Example Homes — AI Opportunity Assessment & Engagement Proposal
    Example Homes — Technical PRD: Design Studio Option Intelligence
Acme Corp/
  Research/
    ...
```

**Title every document with the company name first** so it is identifiable
out of context — in search results, when shared, or in a notification.

**Revising something already sent?** Pass `--doc-id` so the URL, sharing and
comment threads survive. Adding `--company` at the same time moves the
existing doc into the convention without changing its link.

Document structure:

1. **Status banner** — M&A, delisting, ownership change. Never buried.
2. **"The N things you must know"** — five or six, one line each.
3. **Financial trajectory table** — two comparable periods, direction, and
   what each number *means* for the meeting.
4. **Per-executive sections** — title, tenure, how they talk (verbatim
   quotes), handling notes, and the specific landmine for that person.
5. **Job posting analysis** — stack table, admitted problems, build-vs-buy.
6. **Hypotheses** — evidence, confirming questions, what kills each.
7. **Question bank by person** — usable close to verbatim, not themes.
8. **Landmine table** — don't / why.
9. **Logistics** — venue, timing, materials, follow-up.
10. **"What good looks like"** — the outcome, not the pitch.
11. **Gaps** — what you could not verify and why.
12. **`## Sources`** — numbered, grouped, every URL live.

Mark `[UNVERIFIED]` inline with the reason. Never guess a name or number.

## Pitfalls

- **Writing a pitch when they asked for discovery.** If the user doesn't yet
  know what they're selling, a positioning deck is worse than useless. Ask.
- **Leading with the biggest number.** It's usually the least defensible and
  costs you the CFO.
- **Ignoring build-vs-buy.** A company hiring in-house engineers on a modern
  stack will build anything you could demo. Sell what's uneconomic to build.
- **Stale executive quotes presented as current.** A two-year-old interview is
  a conversation starter, not a statement of present priorities. Ask how the
  agenda evolved rather than reciting it back.
- **Skipping the latest quarter.** Financial trajectory sets the entire tone.
  A company that just missed badly is a different buyer from one that beat.
- **Carpet-bombing research in the meeting.** Deploy specifics ~3 times
  deliberately: early for credibility, mid to open the core topic, late to
  show you understand their internal reality. More looks like performance.
- **Treating aggregator org charts as fact.** SEC filings name only executive
  officers — typically 4-6. VP-level and divisional leaders are not disclosed.
  Say so; don't pad with RocketReach guesses.
- **Sizing without showing arithmetic.** An unshown number is unattackable and
  therefore untrusted.
- **Forgetting the accounting treatment.** Where a cost lands (SG&A vs COGS vs
  capitalised) can decide whether a deal happens. Ask early.

## Verification

Before delivering:
- [ ] Corporate status checked against a filing < 6 months old.
- [ ] Most recent quarter's results included.
- [ ] Class A / Class B split stated explicitly at the top.
- [ ] Every inferred claim carries a confidence level.
- [ ] Every ROI figure shows its arithmetic; assumptions tagged.
- [ ] The largest opportunity is explicitly discounted or framed as a test.
- [ ] A defensible subtotal excluding the weakest line is given.
- [ ] Cultural and brand guardrails identified with evidence.
- [ ] Regulated-domain exposure checked.
- [ ] Questions are verbatim-usable, not themes.
- [ ] Gaps section names what was not checked.
- [ ] `## Sources` complete, grouped, live.
- [ ] Docs filed in `<Company>/Research/`, not loose in Drive root.
- [ ] Each document title starts with the company name.
- [ ] Revisions used `--doc-id` so shared links still resolve.

## Support Files

- `references/roi-sizing-patterns.md` — reusable sizing formulas, worked
  example, and the honesty rules for presenting a number.
