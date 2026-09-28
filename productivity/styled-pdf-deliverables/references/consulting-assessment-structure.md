# Consulting Assessment Deliverable — Structure Reference

Condensed from a consulting candidate assessment on an example firm
(a 20-person consultancy whose Chief Client Officer manually assembles account
health across HubSpot, ClickUp, Slack, Fireflies, Gmail, and 20 weekly 1:1s).
The structure generalises to any "evaluate this operational bottleneck and
propose how you'd solve it" brief.

## The shape that worked

Two parts, continuously numbered, in one PDF:

**Part I — Evaluation**
1. Workflow map
2. Technical landscape
3. Build vs. buy, component by component
4. Solution approach
5. Phased path to delivery
6. Limitations & open risks
7. Human-in-the-loop guarantee

**Part II — Architecture** (added when the user names a cloud/stack)
8. Data-sensitivity analysis
9. Why this substrate
10. Reference architecture
11. Deployment tiers
12. Integration reality check
13. Revised phasing

## Analytical moves that carried the most weight

- **Separate where errors ORIGINATE from where they're NOTICED.** A two-column
  table of origin point / real defect / surface point / lag is more persuasive
  than any step list. Lag is the column that reveals the actual problem.
- **Quote the stakeholder interview back as evidence.** The most damaging line in
  discovery is usually an offhand admission ("I update the board the morning I
  know she's going to look at it"). Name it as a structural finding, not an
  anecdote.
- **Name the observer effect explicitly.** Self-reported status fields in any
  monitored system are a *performance of status*, not a record. Any solution that
  leans harder on them degrades them further. This is an organisational
  constraint wearing a data-quality costume.
- **Identify the highest-trust / least-consumed asset.** In this case call
  transcripts: 100% captured, ~10% used. That asymmetry is almost always where
  the cheapest win lives, and it requires zero behaviour change from staff.
- **Rank, don't score.** Ordinal ranking of where to spend attention beats a
  0–100 health score. Scores invite arguments about 71 vs 78; ranks invite the
  right argument — is this really more urgent than that.
- **Deliberately deprioritise the obvious fix.** Saying "I would NOT fix the
  project-board hygiene first, because that's a management problem mistaken for
  a tooling problem" reads as judgment, not evasion.
- **Ship gates, not aspirations.** Concrete pass/fail criteria over a fixed
  window (blind concordance on top-5 in ≥3 of 4 weeks; zero unexplained
  escalations; sub-2% fabrication with a named severity-1 defect class), plus an
  explicit "if these fail, here's what I'd recommend stopping."
- **Phase so the client can stop anywhere** and still hold something valuable.

## Build vs. buy, per component

Do it as a table, never as a single verdict. The reliable pattern:

| Layer | Default |
|---|---|
| Connectors, storage, inference, transcription | Buy — commodity, zero differentiation |
| Entity resolution | Build thin — client-specific naming, small and deterministic |
| Scoring / prioritisation logic | **Build** — this encodes the expert's judgment and is the proprietary asset |
| Cross-source consistency checking | **Build** — nothing off-the-shelf does it |
| Delivery surface | Buy the surface (Slack/email), build the content. No web app in phase 1. |

Generic vendor tools in an adjacent category (CS health scores built for SaaS
renewal telemetry) import someone else's model of the problem. That's the
argument against buying the one component worth owning.

## "Is the data proprietary?" — the distinction to make

Existing use of a third-party SaaS processor is **precedent**, not **permission**.
It proves leadership has already crossed the cloud-processing line — genuinely
useful — but says nothing about what client MSAs require in subprocessor
notification, whether any client sits in a regulated vertical, or what the
incumbent vendor's own terms permit downstream.

Practical framing: the data is proprietary AND it can still go to an enterprise
inference endpoint. Conflating those two questions is what makes people build
expensive self-hosted systems they didn't need. Resolve it with a scoped legal
review of 3–5 representative contracts in phase 0, and treat the hardened
managed tier as the plan with self-hosting as a costed contingency.

## Human-in-the-loop framing that landed

Stated as a guarantee list, not a caveat:

- The system ranks and evidences; it never decides
- No outbound communication, ever — nothing to clients, nothing to staff
- No autonomous writes to client-facing records; drafts are accept-or-edit by
  the original author
- Every claim cited and one click from its source artifact
- Confidence and data gaps always displayed
- **Output is interrogative** — suggested questions, never suggested actions
- Expert override is the primary feedback channel, not an error to suppress

## Risks worth surfacing in this class of engagement

Order by likelihood of killing the project, not by severity:

1. **The intervention degrades its own data source** (observer effect extends to
   the new system). No technical fix; mitigate with framing and written
   governance commitments.
2. **No ground truth** — calibrating against one expert replicates their blind
   spots behind an authoritative interface.
3. **LLM reliability on the highest-stakes extraction** — commitment semantics in
   conversational transcripts ("we'll try to get you something" vs. a promise).
   Errors run both ways and both damage credibility.
4. **Single-expert dependency + the automation-trust paradox** — trust is the goal
   and the failure mode. Mitigate with a permanent random-sample audit as
   designed friction.
5. **Upstream data problems no vendor can fix** — say which dimension of the
   output is permanently weaker as a result.
6. **Small-n and seasonality** — a four-week validation window may not span a
   business cycle.

## Tone

The user's brief was explicit: *think rigorously and be honest about where it
gets hard; don't pitch.* Concretely — state what you would NOT do and why,
name the single highest-priority unknown that could invalidate the plan, give
cost order-of-magnitude rather than false precision, and close with what you'd
flag before committing rather than a summary of strengths.
