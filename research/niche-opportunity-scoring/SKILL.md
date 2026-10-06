---
name: niche-opportunity-scoring
description: "Use when ranking niches by demand vs who owns it."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [niche-research, competition, demand, youtube, seo, market-sizing, methodology]
    related_skills: [youtube-language-arbitrage, ai-tool-niche-research, grounded-citations, blocked-page-recovery]
---

# Niche opportunity scoring (demand vs who owns it)

Class-level method for "find profitable niches" across any results-ranked market: YouTube topics, SEO keywords,
app-store categories, marketplace listings. Domain skills (`youtube-language-arbitrage` for YouTube channels,
`ai-tool-niche-research` for ad-monetized AI tools) hold the market specifics; this skill holds the scoring method
that was validated, after a public correction, on 2026-10-04.

## When to Use

- "Research profitable niches", "which niche/language/market is least crowded", "is X saturated?"
- Comparing the same topic across countries or languages, or many topics in one market.
- Before committing production budget to a channel, site or product category.

Past run results (YouTube, 9 languages, German retirement dive, multi-channel setup answer):
`references/youtube-run-2026-10-04.md`. Kids' songs and sponsored/ad-slot formats (policy risks, legitimate
version): `references/kids-songs-and-sponsored-formats.md`.

## Steps

1. **Define the grid**: niches x markets (languages/countries). Write each query in the market's own search phrasing,
   never a literal translation.
2. **Measure demand from results**: for each pair pull the top ~20 results and record the demand metric (views,
   reviews, search volume) plus recency. Use the median of the top results, and a "fresh" median (last 12 months)
   so dead evergreen topics don't score high.
3. **Measure competition from who OWNS those results**, not from name matches. Record each result's owner, then compute:
   - fragmentation = 1 - top owner's share of demand
   - distinct owners in the top 20
   - for the shortlist only (expensive lookups): each owner's size (subscribers, domain authority, review count)
4. **Breakout test (the real opening signal)**: count big results (e.g. >=50K views) owned by SMALL players
   (e.g. <50K subs). 0 breakouts with huge demand = incumbents lock it. Several breakouts = newcomers can win.
5. **Value**: demand x monetization rate for that market (country RPM/CPC relative to the US baseline). Vendor RPM/CPC
   tables disagree, so use a mean of two or more sources and show them as ranges.
6. **Re-check every shortlisted gap with a second, differently-worded query** before recommending it.
7. **Deep-dive the pick**: 15-20 subtopic queries, view share by owner, the top 30 results, dead subtopics, winning
   formats, then a concrete content plan (e.g. 20 videos grouped by format) and a risk list (expertise, regulation,
   trust).
8. **Production fit**: score whether the niche can be made with the user's pipeline. This user prefers topics that
   need NO real-world footage (space, AI, robotics, physics, tech news, explainers) so motion graphics / HyperFrames /
   Opuscar can carry the visuals. Flag niches that need filming (DIY hands-on, cooking, travel) as a production cost,
   and niches needing credentialed review (pensions, tax, health) as a trust/regulatory cost.
9. **Report**: one table (demand, value vs baseline, breakouts, biggest owners), a ranked pick list with the reason
   for each, explicit limits, and numbered next steps.

## Handling mid-run redirects ("what about X too?")

The user adds niches while scans are running. Don't kill the running job. Instead:
1. Answer immediately from data already collected (the wide scan often already has a related query, e.g. a
   beginner-Bitcoin row when asked about crypto news), clearly labeled as a proxy.
2. Write the new grid/dive config and QUEUE it behind the running job with a small runner script that waits on
   `pgrep` for the earlier job, then runs sequentially (parallel searches collide on the rate-limited reader).
3. Launch the runner with `background=true, notify=true`, and tell the user the run order and rough ETA.
4. When a better method arrives mid-run (e.g. owner-based instead of name-based), stop the flawed scan, keep its
   output labeled as a lower bound, and restart with the better method; say so plainly.
5. **"Put X ahead of Y" (reprioritize):** kill only the WAITING queue scripts and any just-started dive of the
   demoted job, rename its partial log (`*.partial.log`), and start ONE new ordered queue script
   (e.g. `run_tech_then_crypto.sh`). Expect SIGTERM (-15) completion notices from the killed waiters. Tell the
   user those are intentional, not failures.

## Pitfalls

- **Language/region filters still return global content.** French DIY looked like 1.17M median views, but the top
  results were international hack compilations (Blossom-style) and English renovation timelapses. Both need
  real footage, and real French how-to channels won on 5-14-year-old videos (new how-tos: ~2K-90K median). Before
  ranking a pair, read the top ~10 titles: are they in the target language, owned locally, and reproducible with
  the user's pipeline? Score only those results. Round 2's top pick was dropped after its deep dive for this reason.
- **Name-matched counts lie.** YouTube channel search (and "tools named X" counts) match names, so generalist owners
  with generic names vanish. German retirement scored 0-1 competitors that way; the owners of its top videos were
  1.65M, 588K and 207K-subscriber channels. That had to be corrected to the user. Never call a market "empty" from
  name matches. Report them only as a lower bound, or skip them.
- **Empty usually means no demand.** Pair every competition number with demand (de small business: 0 competitors,
  5.2K median views).
- **Single queries mislead.** 2 of 6 apparent gaps vanished on the second wording.
- **Off-topic matches inflate or deflate small markets.** Implausibly low or high numbers in small languages usually
  mean the query matched something else: sanity-read a few titles.
- **Admit corrections plainly** when a later, better measurement overturns an earlier claim. This user values honest
  correction over consistency.
- **Long scans:** run them detached (setsid nohup, resumable JSONL, one record per pair) with a completion watcher
  using notify; foreground tool calls time out around 7 minutes. Subscriber/owner lookups are the slow part, so do
  them only for the shortlist.

## Reference implementation (YouTube, keyless)

Scripts in `~/.hermes/data/yt-arbitrage/niches/`: `niche_scan3.py` (owner-based wide scan; `niche_scan4.py` is the
same method on a different topic grid, so copy it for new grids), `score3.py` (value + breakouts; derive a scorer
for another JSONL with sed on the in/out filenames), `dive.py <config.cfg>` (GENERIC deep dive; the config is JSON
`{"slug","lang","queries":[...]}`, e.g. `dive_fr_diy.json.cfg`, `dive_es_crypto_news.cfg`), and `niche_scan.py`
(shared fetch/parse helpers). `dive_de_retirement.py` is the original one-off the generic `dive.py` replaced. Fetching
goes through `https://r.jina.ai/<youtube search url>` with `X-Return-Format: markdown`, `hl=en` so view and age strings
parse uniformly, and `gl=<country>`. Throughput is about 3 s per search. Results and method notes: `FINDINGS.md`,
`ROUND2.md`, `DIVE_DE_RETIREMENT.md` in the same folder.

## Verification

A finished run has: zero error rows in the JSONL, every shortlisted pair re-checked with a second query, owner sizes
for the shortlist, and a ranked table whose top picks each show nonzero breakouts or an explicit reason why not.
