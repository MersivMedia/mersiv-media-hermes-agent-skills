# Opportunity Scoring Rubric

Score each opportunity 1-5 on five axes, then compute a weighted total.

| Axis | Weight | 1 | 3 | 5 |
|---|---|---|---|---|
| **Annual value** | 0.30 | < $25k | $75k-150k | > $400k |
| **Data readiness** | 0.25 | data doesn't exist or is unstructured across silos | exists but needs cleaning/consolidation | clean, accessible, already in a system with an API |
| **Implementation effort** (inverted) | 0.20 | > 6 months, new infra, multiple integrations | 2-3 months, one integration | < 4 weeks, off-the-shelf + config |
| **Risk / blast radius** (inverted) | 0.15 | customer-facing, regulated, irreversible actions | internal-facing with review step | internal, advisory only, human approves every output |
| **Organizational readiness** | 0.10 | no exec sponsor, team resistant | sponsor exists, team neutral | sponsor engaged, team already asking for it |

`score = 0.30·value + 0.25·data + 0.20·(6 - effort) + 0.15·(6 - risk) + 0.10·readiness`

## Ranking guidance

- **Score ≥ 4.0** — Phase 1 candidate. Lead with these.
- **3.0-3.9** — Phase 2. Viable, needs a dependency resolved first.
- **2.0-2.9** — Backlog. Revisit after Phase 1 proves value.
- **< 2.0** — Recommend against, and say why in one sentence.

## Confidence label

Attach to every ROI figure, separate from score:

- **High** — volumes and costs come from the client's own numbers in the notes
- **Medium** — volumes from client, unit savings from a cited external benchmark
- **Low** — both estimated from industry averages; must be validated in discovery

Never present a Low-confidence figure as a headline number in the client PRD. Present it
as a range with the validation step named.

## Sequencing rule

The first project should be the highest-confidence, lowest-blast-radius item that still
clears $50k/yr — not the highest-dollar item. The first deployment's job is to buy trust
for the second one.
