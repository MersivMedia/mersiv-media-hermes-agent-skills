# <Company>: PRD for <Initiative>

**Status:** Draft v0.1, hypothetical. Written from outside the company, before discovery.
**Author:** <Role> (candidate)
**Partner owner:** <department owner, often a newly hired role>
**Sponsor:** <interviewer / hiring manager>
**Prepared:** <Mon YYYY>

## Summary

Write 2–3 short paragraphs covering:
- What goes wrong today, quoting the department's own job posting.
- What the system does, as a short list of components.
- What it never does, for example "Never submits to <external platform>."

**Evidence classes.** Class A is verified and cited. Class B covers design
choices and estimates, tagged `[ASSUMPTION]` or `[DECISION]`. Every volume
figure is a placeholder until discovery.

## 1. Problem
### What the company has said (Class A)
- One cited bullet per admission, quoted from the postings.
### What this implies (Class B, <confidence>)
- Inferred current-state pains.

## 2. Goals and non-goals
| ID | Goal | Measure |
|---|---|---|

Non-goals must include:
- Human-only judgement areas stay human.
- No automatic external submissions.
- No duplication of the in-house platform or engineering pipelines.
- Adjacent scope that belongs to another team.

## 3. Users
| User | Needs | Main surface |
|---|---|---|

## 4. Current state (hypothesis, to validate)
- A numbered walkthrough of the process as it probably works today.
- **Discovery tasks for weeks 1–3:** shadow the process, count re-typed
  fields and chases, time each step, collect past artifacts.

## 5. Proposed solution
### Plain-language flow
One paragraph a department head would understand without help.

### Components
| # | Component | Built with | Phase |
|---|---|---|---|

`[DECISION]` Start the MVP on the stack the team already uses, for example a
Sheet as the registry. Design it as normalized tables so it can move to a
database later.

## 6. Functional requirements
Use a prefixed ID scheme (e.g. ON-1, PC-1). Priority P0 means MVP, P1 phase 2,
P2 later. Group the tables by component. Include:
- validation that blocks partial records,
- idempotency so running twice doesn't duplicate anything,
- a rule that credentials and secrets are never stored,
- a human approval step before any AI output is used.

## 7. Data model
| Table | Key fields |
|---|---|

Include an events table (status and timestamps) so cycle time per stage can
be measured.

## 8. Integration and architecture
| System | Role | Method | Notes |
|---|---|---|---|

- Cite the vendor docs for every webhook, notification and plan-gating claim.
- Include a platform-limits table, e.g. Apps Script quotas, with what each
  limit means for the design.
- `[DECISION]` Choose where webhooks are received (Make/Zapier vs a hosted
  receiver), and say which parts engineering owns.
- Automations run under a service account, never a personal login.

## 9. Permissions and security
Cover who can edit and who can only view, which data is restricted, what
gets posted to Slack, and how offboarding removes access.

## 10. Success metrics
| Metric | Baseline | Target |
|---|---|---|

Baselines are "measure in discovery." Show the sizing arithmetic with every
input tagged `[ASSUMPTION]`, and say where the value is revenue protected
rather than hours saved.

## 11. Rollout
| Phase | Weeks | Scope | Exit criteria |
|---|---|---|---|

Pilot alongside the current process, and only retire the old way after the
owner signs off.

## 12. Risks
| Risk | Likelihood | Mitigation |
|---|---|---|

Always include:
- adoption and logging overhead,
- the tool running ahead of the process it supports,
- unnoticed webhook failures, caught by a daily reconciliation check,
- data exposure.

## 13. Dependencies
List the people, admin access, license tiers and policies this needs.

## 14. Open questions
5–7 numbered questions that would change the design.

## 15. Acceptance criteria (MVP)
- [ ] Testable, observable checks, including that someone other than the
  author has followed the runbook successfully.

## Sources
