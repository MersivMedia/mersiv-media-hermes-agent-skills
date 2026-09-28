# Prompt 4 — Scaling / Analytics Analyst

**Replaces:** monthly content strategist retainer.
**Use:** Monthly review of channel analytics to decide what to scale,
  kill, and add. Weekly once you're past 10 published videos.
**Where to run:** Claude (your $20 sub) — paste in CSV exports from YT Studio.

---

```
You are the growth strategist for [brand]. Read the analytics dump
below and return a structured month plan.

CHANNEL CONTEXT:
- Faceless space industry channel, 4 pillars (investing / careers /
  beginners / tourism)
- Single-narrator AI voiceover (one locked ElevenLabs voice — [character], `TyJfVqGmT0iahaNbUE37`)
- Target RPM band $15-50, currently {{ACTUAL_RPM}}
- Total videos published: {{VIDEO_COUNT}}
- Months in operation: {{MONTHS_LIVE}}

ANALYTICS DUMP (paste CSV or paste-from-YT-Studio):
{{ANALYTICS}}

Each row should have at minimum: title, pillar, views, watch time,
average view duration, CTR, RPM, published date.

===== 1. TOP 20% IDENTIFICATION =====

List the top-performing 20% of videos. For each:
  - Title
  - Pillar
  - The format pattern (e.g. "earnings recap", "explainer", "list video",
    "deep-dive on one company", "news react")
  - The retention pattern (where does the average-view-duration sit
    relative to runtime — strong full-watch, mid-drop, hook-failure)
  - The single attribute most likely driving its performance
    (title hook? topic timeliness? thumbnail? pillar match?)

===== 2. FORMAT TO SCALE =====

Pick ONE format from the top 20% that:
  - Has appeared 2+ times in the top tier
  - Is producible weekly without burning out
  - Has remaining topic surface area for at least 10 more videos

Output:
  FORMAT NAME:
  WHY IT WINS:
  10 NEXT TOPICS in this format (specific, ready to script):

===== 3. FORMAT TO KILL =====

Pick ONE format that's appeared 2+ times in the bottom 50% with no top-tier
appearance. Stop making it. Explain why in one sentence.

===== 4. PILLAR REBALANCE =====

Show current pillar mix (% of videos) vs. % of views vs. % of revenue.
Recommend new pillar mix for the coming month. If one pillar is dragging
RPM, propose either dropping it OR finding a higher-RPM angle inside it.

===== 5. NEXT MONETIZATION LAYER =====

Based on current view volume, recommend which monetization layer to add
THIS month. Use this ladder and only add the next rung:

  Rung 1 (0-50k mo views): AdSense only, focus on watch time
  Rung 2 (50-200k mo views): + affiliate links (brokers, books, tools)
  Rung 3 (200-500k mo views): + sponsorship outreach
  Rung 4 (500k+ mo views): + digital product (newsletter, course, screener)

Output: current rung, ready to climb? (yes/no/almost), action items.

===== 6. RETENTION DIAGNOSTIC =====

Across the dataset, what's the most common drop-off pattern?
  - HOOK FAILURE: viewers leaving in the first 30s. Fix the cold open.
  - MID-VIDEO SAG: drop at 30-60% mark. Tighten Act II, add a loop.
  - PAYOFF MISS: drop before Act III payoff. Reset stakes in Act II.

Pick the dominant pattern and prescribe ONE script-engine adjustment to
test next month.

===== 7. 30-DAY CONTENT SLATE =====

Output a 12-15 video slate for the next 30 days using:
  - The format from §2 (60% of slate)
  - Pillar rebalance from §4
  - At least one experimental format to keep testing

Each entry: working title, pillar, format, why-this-now.

===== OUTPUT =====

Use the section headers above verbatim. No preamble. End with a single line:
  HEADLINE FOR THE MONTH: [the one thing that matters most this month]
```

## Pitfalls

- **Don't run with fewer than 8 videos of data.** Sample too small. Wait.
- **Watch time matters more than views.** A 50k-view video at 12 min watched
  beats a 200k-view video at 90 sec watched, every time.
- **Pillar drift is the silent killer.** If 80% of views come from pillar ①
  but only 30% of videos are pillar ①, the slate is mis-allocated.
- **Don't climb the monetization ladder out of order.** Adding sponsors at
  50k views per month means terrible sponsor rates and a credibility hit.
