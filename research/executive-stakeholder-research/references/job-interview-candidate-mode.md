# Job-interview mode (the user is the candidate)

Use this when the user is interviewing *for a job* at a private company. It
builds on `private-company-no-filings.md`. The request usually comes in two
rounds, so build round 1 so that round 2 can reuse it:

1. **Interview briefing**: company, interviewer, role decoded, hypotheses,
   stories to prepare, verbatim questions, landmines.
2. **"As if I had the job" assessment**: 10 candidate projects, a scored and
   scoped top 5, and questions by department. Keep worked examples in Drive under
   `<Company>/Research/`.

## Resolve the interviewer before researching them

- **Names collide.** One interviewer's name first returned a famous
  same-name CEO in another city. When search returns more than one plausible
  person, ask the user to pick. Offer each candidate as a choice with company
  and city attached.
- **The user may know only a title.** Get it from the company's
  `/about/team(s)` page and **check whether more than one person holds it**.
  One company listed both "Director of Operations" and
  "Director of Operations – Dallas". Match on the role's location and on the
  reporting line stated in the posting. State which person is likely, name
  the alternative, and tell the user how to confirm it (calendar invite or
  recruiter).
- Add a note to the doc warning about the same-name person, so the user
  doesn't prep from the wrong podcasts.

## What renders logged-out (curl with a browser UA plus a regex tag-strip)

| Source | Result |
|---|---|
| LinkedIn `/jobs/view/…` | Full posting: pay, 90-day plan, reporting line |
| LinkedIn `/in/…` | Activity (posts, reposts, likes), certifications, languages, projects. Experience titles and dates are masked with `****` |
| LinkedIn `/posts/…` and company page | Exec posts with growth numbers, hiring volume, headcount |
| ATS boards (JazzHR `*.applytojob.com`, Greenhouse, Lever) | **Every open role**, each fetchable in full |
| Business Wire via finance.yahoo.com | Press releases (use this when inc.com returns 403) |
| Glassdoor, Indeed, RocketReach, Wiza, inc.com | 403 or JS wall. Use search snippets only and tag them `[UNVERIFIED, snippet]` |

Extract the JazzHR job list with the regex
`href="(https://<co>.applytojob.com/apply/[^"]+)"[^>]*>([^<]+)<`.
Save raw pages under `~/.hermes/data/research/<company>/`.

## Reading the interviewer's activity (all MEDIUM confidence)

- **Certifications show what they value.** A Trainual training-design cert
  means they care about SOPs and documentation, so the user should bring a
  runbook they wrote.
- **Reposted job openings reveal adjacent hires** that will overlap with the
  user's role. Turn each into a "where does my role end and theirs begin"
  question.
- **Trade-show floor activity** shows how client-facing they are.

## Briefing structure (round 1)

1. The 6 things to know walking in.
2. Who's interviewing you: an identity table, then verified facts,
   snippet-only facts, and what they suggest.
3. The company and its recent momentum.
4. The role decoded: stack table, admitted problems quoted directly, **the
   posting's own 90-day plan** (build answers around it), pay and logistics.
5. Hypotheses, each with a confirming question and what would kill it.
6. A table mapping each requirement to a story the user should prepare.
7. Verbatim questions for the interviewer.
8. Landmines. Examples: asking about remote work when the posting says
   onsite and explains why, framing value as "replacing people", mixing up
   same-name people, reciting founding dates or headcounts that sources
   disagree on.
9. Culture signals, labelled as weak evidence with the sample size, plus a
   neutral question to raise instead.
10. Gaps, then Sources.

## Assessment (round 2)

- **Fetch every other open posting.** Each is a department describing its own
  pain, and a table of department | quoted admission | implication is the
  strongest evidence available from outside the company.
- **Look for contradictions between postings.** For example, "no engineering
  team" in one versus "our engineering team built the SP-API pipelines" in
  another. Hand each one to the user as a boundary question.
- **Add a "no other owner" scoring column.** If another posting or an
  in-house product already owns a problem (a new PPC principal who "builds
  toolsets", a dedicated reconciliation analyst, an in-house WMS, a
  client-facing analytics product), drop it from the top 5 and say why. This
  shows the interviewer the candidate won't build duplicates. The other
  columns are hours, scales-with-growth (weighted x2 at a hypergrowth
  company), error cost, and effort.
- **Weeks 1–3 discovery Sheet.** Columns: workflow, owner, runs/wk,
  minutes/run (timed by observation, not self-reported), people, hrs/wk
  formula, scales?, error cost, delete-first?, systems, effort, score.
- **Each top-5 scope contains:** the cited problem, likely current state,
  delete-first questions, design (trigger → steps → guardrail), partner role,
  sizing with `[ASSUMPTION]` inputs and arithmetic shown, metrics, MVP weeks,
  and what would kill it. Sequence the five onto the posting's 90-day plan.
- **Cite platform limits** for the stack. For Apps Script, Google's quota page
  gives 6 minutes per execution, 6 hours per day of trigger runtime, and
  100k URL fetches per day on Workspace. Design around them.
- **Questions by department.** Start with 3 universal questions ("last time
  this went wrong", "which spreadsheet would hurt most if it vanished", "one
  task you'd stop forever"), then 3–5 verbatim questions per function, each
  tied to the posting that prompted it.

## Pitfalls

- **Every hours figure is a guess**, because no volumes are public. Tag each
  input `[ASSUMPTION]` and tell the user to present it as "here's how I'd
  measure it".
- **`grounded-citations verify --min-coverage 0.5` fails on long advisory
  docs** because the inferred prose is deliberately uncited. Run `verify`
  without a threshold and fix only unknown ids, sentences with more than 3
  citations, and block mismatches.
- **The Sources block imports into a Google Doc as one paragraph.** Convert
  `[n] url` lines to `- [n]` list items on a copy before running md2gdoc.
- **Titles and filing:** `--company "<Co>"`, with titles such as
  `<Co> — Interview Briefing: <Role> (<Mon YYYY>)` and
  `<Co> — First 90 Days: <Area> Assessment & Top-5 Scope (Hypothetical)`.
