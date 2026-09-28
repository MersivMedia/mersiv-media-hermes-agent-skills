---
name: executive-stakeholder-research
description: Map a company's executives and board from SEC primaries.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, sec, edgar, leadership, org-mapping, sales-intel, due-diligence]
    category: research
    related_skills: [grounded-citations, competitor-news-monitor, domain-intel, account-intelligence-briefing, blocked-page-recovery]
---

# Executive & Stakeholder Research Skill

Builds a sourced leadership map of a company: named executives, exact titles,
role start dates, tenure, prior roles, education, and quoted public statements.
Primary sources first (SEC filings), aggregators last and always flagged. This
skill covers US-listed and recently-delisted issuers. For private companies with
no filing history — startups, agencies, PE-backed operators — and for the common
"prep me for an interview with these two people" variant, use the substitute
source ladder in `references/private-company-no-filings.md`.

## When to Use

- "Research the leadership team / key stakeholders of \<company\>."
- Pre-sales account mapping: who owns budget, who is new and needs a win.
- Due diligence or competitive intel on an executive bench.
- Interview prep: "I'm meeting X and Y at company Z, tell me about them and the
  company." See `references/private-company-no-filings.md` for the output shape.
  If the user is the **job candidate** (interviewing for a role), also load
  `references/job-interview-candidate-mode.md` — expect a follow-up asking for
  a hypothetical first-90-days assessment.
- Any request asking for titles + tenure + quotes with citations.

## Prerequisites

- `terminal` with network access (EDGAR needs no key, but requires a
  descriptive `User-Agent` header or it returns 403).
- `web_search` for press releases, interviews, and earnings transcripts.
- No API keys required.

## How to Run

1. **Verify corporate status FIRST.** Before building any org chart, check
   whether the company still exists in the form the user assumes. Search
   "\<company\> acquisition OR merger OR delisted" and scan recent 8-K forms.
   A ticker in the user's prompt is a claim, not a fact.
2. **Pull the filing index** with `scripts/edgar_filings.py` (see below).
3. **Read the latest DEF 14A** — this is the highest-value single document.
4. **Read every 8-K since that proxy** for Item 5.02 personnel changes.
5. **Layer on press releases, interviews, and earnings transcripts** for quotes.
6. **Write the report** in the output contract below.

```bash
# 1. resolve CIK + list recent governance-relevant filings
python3 scripts/edgar_filings.py "Example Homes"

# 2. extract a filing to plain text (script handles the UA header + tag strip)
python3 scripts/edgar_filings.py --extract <url> > proxy.txt
```

## Quick Reference

| Need | Source | Where exactly |
|---|---|---|
| Exact officer names, ages, titles | DEF 14A | `MANAGEMENT` section, near the end |
| Role start dates, prior employers, degrees | DEF 14A | officer bios + `Director Nominees` |
| Board members, tenure, committee chairs | DEF 14A | `BOARD OF DIRECTORS` |
| Who is board chair | DEF 14A | `DIRECTOR COMPENSATION` — chair draws an extra retainer |
| Hires, departures, promotions, retention pay | 8-K | **Item 5.02** |
| Who the acquirer wanted to keep | Merger 8-K | Item 5.02 retention bonus agreements |
| Verbatim executive quotes | Earnings transcripts | Motley Fool via Yahoo Finance, Seeking Alpha |
| Who currently signs filings | any 8-K | signature block at the very bottom |

**Officer-disclosure ceiling.** SEC rules only require naming *executive
officers* — typically 4-6 people. VP of Operations, VP of Purchasing, VP of
Construction, and division presidents will NOT appear in filings. Say so
explicitly rather than padding the list with aggregator guesses.

## Procedure

### 1. Status check (never skip)
Recent M&A changes everything. If the company was acquired:
- The independent board almost certainly **resigned at the effective time** —
  Item 5.02 of the closing 8-K names each resigning director.
- Merger Sub's directors become the surviving corporation's directors, and
  their names are usually **not disclosed**. Mark the current board
  `[UNVERIFIED]` rather than reusing the pre-merger roster.
- Officers usually carry over: look for "the officers of the Company serving
  as of immediately prior to the Effective Time became the officers of the
  Surviving Corporation."
- The parent's executive who commented at close becomes a real stakeholder.
  Capture their quote — it states the mandate the subsidiary now operates under.

### 2. Mine the proxy
Search the extracted text for `MANAGEMENT`, `Director Nominees`, and
`DIRECTOR COMPENSATION`. Officer bios give role start date, prior employers
with date ranges, and degrees in one paragraph each. Record ages "as of" the
proxy's stated record date, and compute tenure to *today*, stating both dates.

### 3. Sweep 8-Ks forward
Every 8-K filed after the proxy date, checked for Item 5.02. This is where
post-proxy appointments and departures live. Also read the signature block —
it confirms who currently holds the CFO/GC seat.

### 4. Harvest quotes
For each priority executive, search `"<company>" earnings call transcript
<exec name>` and `"<exec name>" interview technology OR AI OR efficiency`.
Extract the transcript to text and grep for theme keywords:
`technolog|AI |artificial|digital|efficien|cycle time|cost sav|automat|SG&A`.
Prefer verbatim quotes with the call date over paraphrase.

### 5. Identify the NEW cohort
Flag anyone under ~2 years in role — they carry pressure to show visible wins.
Three things also count as "new" even when nobody crossed the 2-year line:
- an **internal promotion with expanded scope** (long tenure, new remit),
- a **first-generation role** (nobody held that title before),
- an **ownership or board change** — a new parent resets who everyone answers to.
If literally nobody is under 2 years, say that plainly and give the closest cases.

### 6. Find the real decision-maker
Reporting lines matter more than titles. Trace who the CIO/CTO reports to —
if IT reports into Marketing or Operations rather than Finance, that reveals
how the company frames technology (revenue lever vs cost centre) and tells you
which exec actually holds the budget. Appointment press releases state the
reporting line explicitly; quote it.

### 7. Sweep job postings for the layer filings don't reach
SEC filings stop at ~4-6 executive officers. Job postings reach everything
below that line, and they are written by managers describing problems they
actually have. They yield: the named technology stack, admitted internal
problems (senior JDs often confess to "technical debt", "duplication",
"complexity"), build-vs-buy posture, and **unfilled senior roles** that
represent a decision vacuum.

Corporate careers sites and Indeed are usually WAF-blocked by IP; **LinkedIn
job search renders and is readable** (see `blocked-page-recovery` route 6).
Run several role-keyword searches rather than paginating one query —
pagination duplicates heavily — dedupe on (title, location), and state that
the list may be incomplete.

For turning all of this into a meeting plan and ROI case, hand off to
`account-intelligence-briefing`.

## Output Contract

Markdown, in this order:

1. **Status banner** at the top if anything material changed (M&A, delisting,
   board dissolution). Lead with it — do not bury it under an org chart.
2. **Executive summary table** — person, role, new? — plus 2-3 findings that
   actually shape action (reporting lines, retention pay, mandates).
3. **One section per executive**, priority order: CEO, COO, CFO, CIO/CTO, CMO,
   GC, board chair. Each carries: exact title, in-role-since date, computed
   tenure, prior roles with date ranges, education, and quoted statements
   grouped by theme with the source date.
4. **A "who is NEW" section.**
5. **A "gaps and caveats" section** — missing quotes, stale sources, blocked
   pages, unread filings. Name what you did not check.
6. **`## Sources`** — numbered, grouped (Primary/SEC, company/newswire,
   transcripts, secondary), every URL live and each tied to what it supports.

Mark `[UNVERIFIED]` inline and give the reason ("aggregator source",
"page returned 403", "self-reported on LinkedIn"). Never guess a name or title
to fill a slot the user asked for — an honest "not disclosed at this level"
beats a plausible fabrication.

## Pitfalls

- **Trusting the ticker in the prompt.** Check for M&A before anything else.
  A "NYSE: XYZ" framing can be a year stale.
- **Corporate IR sites sit behind Cloudflare JS challenges.** `curl` returns
  "Just a moment... Enable JavaScript". Do not fight it — EDGAR, GlobeNewswire,
  and the IR press-release URLs surfaced in search metadata carry the same
  content. See `references/source-fallbacks.md`.
- **EDGAR 403s without a User-Agent.** Send a descriptive one; the script does.
  The format matters: `"<Company> research <email>"` works, but a User-Agent
  containing a URL (e.g. `"Tool (github.com/x/y) me@x.com"`) also gets 403
  from `data.sec.gov`. Structured facts for cross-checking a filing live at
  `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` (`dei` block,
  match rows by accession number).
- **Full-text greps on a proxy blow up your context.** The first ~40% of an
  inline-XBRL proxy is machine-readable tag soup. Slice by section offset
  (`t.find('MANAGEMENT')`) and print bounded windows — never dump the file.
- **Aggregators (RocketReach, TheOrg, Equilar, Crunchbase) go stale silently.**
  Usable for leads, never as the sole citation for a name or title.
- **LinkedIn headline claims are self-reported.** Awards and "finalist" claims
  need independent confirmation or an `[UNVERIFIED]` tag.
- **Newswire URL guessing fails.** Constructing a GlobeNewswire slug from a
  headline can silently return a *different* company's release from the same
  date. Verify the extracted body mentions your company before quoting it.
- **Do not stop at four executives and call it done.** If the user asked for
  VP-level roles, explicitly state the disclosure ceiling and hand back the
  named-but-unverified candidates with tags.

## Verification

Before delivering, confirm:
- [ ] Corporate status checked against a filing dated within the last 6 months.
- [ ] Every person has a source URL.
- [ ] Every title traced to a primary source, or tagged `[UNVERIFIED]`.
- [ ] Tenure figures state both the start date and the "as of" date.
- [ ] Every quote has a speaker, a date, and a venue.
- [ ] `## Sources` exists and every claim in the body maps to a numbered entry.
- [ ] Gaps section names what was not checked.

## Support Files

- `scripts/edgar_filings.py` — CIK lookup, filing index, and filing-to-text extraction.
- `references/source-fallbacks.md` — what to do when a source blocks you, and
  the reliability ranking of common people-data sources.
- `references/private-company-no-filings.md` — source ladder for private
  companies (ATS boards, Built In, blog bylines, interviewer posts) and the
  interview-prep output contract.
- `references/job-interview-candidate-mode.md` — when the USER is the job
  candidate: resolving an interviewer known only by title (check for multiple
  holders of that title on the team page), same-name collisions, what LinkedIn
  renders logged-out, the two-round deliverable (briefing → "as if I had the
  job" top-5 assessment built from the company's OTHER open postings, with a
  "no other owner" scoring column), and per-department question banks.
