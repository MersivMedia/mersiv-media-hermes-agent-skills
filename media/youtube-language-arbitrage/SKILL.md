---
name: youtube-language-arbitrage
description: "Use when planning a YouTube channel in a non-English market."
version: 1.0.0
author: Hermes Agent (from @boomerrbryan's X post, 2026-10-04, tested + corrected)
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [python3, curl]
metadata:
  hermes:
    tags: [youtube, faceless, localization, dubbing, niche-research, international, content-strategy]
    related_skills: [hyperframes, motion-graphics, elevenlabs-narrator-revoice, agent-reach, social-post-extraction, grounded-citations]
---

# YouTube language arbitrage (proven topics → under-served languages)

## When to Use

Use this skill when someone wants to:
- launch a faceless or AI-presented YouTube channel in Spanish, Portuguese, German, Japanese or another language, based on a niche already proven in English;
- localize their own or a client's channel; or
- check "is this niche crowded in language X?"

**Source:** Bryan Ng (@boomerrbryan) on X, 2026-10-04, https://x.com/boomerrbryan/status/2106803788887789754. The full text is in `references/source-post.md`.

**What the post claims** (none of it verified):
- A Portugal-based creator copied every script from a 400K-sub English retirement channel and AI-translated them.
- An AI character delivers them in Brazilian Portuguese.
- The channel has 86K subs, earns $14,000/month, and costs under $10 per video.
- Most niches in other languages have 5% of English competition: 1–2 serious channels, some with none.

The post ends with an ad for the author's channel-building service, so treat it as lead-gen.

## The part the post gets wrong (read before anything else)

**The method as literally described, copying another channel's scripts, is the one version not to build:**

1. **Copyright.** A translation of someone's script is a derivative work and needs their permission. Copying the scripts invites DMCA strikes; three strikes terminates the channel.
2. **YouTube Partner Program policy.** "Reused content" (repurposing existing content without significant original value) and "inauthentic content" (mass-produced/templated, renamed from "repetitious" on 2025-07-15) are both ineligible for monetization. A translated clone with a stock AI host is exactly what reviewers flag. Source: https://support.google.com/youtube/answer/1311392
3. **Synthetic-media disclosure.** Realistic AI presenters and voices must be disclosed with YouTube's altered/synthetic content label.
4. **The economics are inflated.** Brazil and most of Latin America have ad RPMs that are typically a small fraction of US RPMs [UNVERIFIED for any specific niche: check the channel's actual RPM data, never the post's]. $14K/month from 86K Portuguese subscribers would need either an outlier RPM or non-AdSense income (sponsors, affiliates, a product). Treat the $14K figure as unverified.

**What survives, and is legitimate:** *topics* and *formats* aren't copyrightable, and demand really does translate (retirement fear in Ohio ≈ retirement fear in São Paulo). So the defensible versions are:

| Route | What it is | When |
|---|---|---|
| **A. Original channel, proven topics** | Use the English channel's top-performing *topics, angles and formats* as a research map. Write **original** scripts natively for the target market (local laws, prices, institutions such as INSS in Brazil or Rentenversicherung in Germany). | Default for a new channel. |
| **B. Dub your own catalog** | Add dubbed audio tracks to existing videos with YouTube's multi-language audio (rolled out to all creators with Advanced features, Sept 2025; channels reported >25% of watch time from non-primary languages, per YouTube via TechCrunch 2025-09-10). | The user or client already owns a channel. |
| **C. Licensed localization** | A written license from the original creator to translate (revenue share is common). | The user specifically wants a 1:1 version. |

## Steps

1. **Pick the niche from proven demand.** Choose an English channel (or several) with strong views and an evergreen, emotional topic: money, retirement, health, relationships, history, true crime, tech how-tos. List its 20 most-viewed video *topics*, not scripts. (Screenshot the channel's Popular tab, or ask the user for the list. Fetching `/@handle/videos` through Jina wasn't verified on this box.)
2. **Measure competition per language** with 3–5 queries per language in each market's own terms (not literal translations), using the bundled scanner:
   ```bash
   S=~/.hermes/skills/media/youtube-language-arbitrage/scripts/yt_niche_scan.py
   python3 $S --q "en:retirement planning tips" --q "pt:dicas de aposentadoria" --q "pt:aposentadoria INSS" \
              --q "es:consejos para la jubilación" --q "de:Rente Tipps" --out ~/.hermes/data/yt-arbitrage/<niche>
   ```
   It reports, per query, the channels parsed, the **serious** count (≥10K subs by default, `--serious N`), and the top and median subscriber counts, then saves JSON. Run it bare; don't pipe it.
3. **Score each market:** serious-channel count, the strongest incumbent's size, ad market (RPM tier), speaker population, and whether the topic needs **local** expertise (retirement/tax/legal do, which helps you since a translation can't fake it, but the scripts need real localization and a fact-check). Prefer markets with few serious channels, decent RPM and localizable topics.
4. **Pick the route** (A, B or C above) and get the user's sign-off before producing anything.
5. **Production (route A):**
   - Native-language script per topic: an LLM draft, then a fact-check against local official sources. Have a native speaker review the first 5 videos.
   - Voice: ElevenLabs multilingual (`elevenlabs-narrator-revoice` patterns), or the user's preferred presenter tool. Turn on the synthetic-content disclosure.
   - Visuals: `hyperframes` (`faceless-explainer` workflow) or `motion-graphics`. Thumbnails follow the *format* of the proven English ones, never copies of them.
   - Metadata natively written in the target language (titles, descriptions, tags, chapters).
6. **Validate before scaling.** Publish 10–15 videos, then judge on CTR, average view duration, subs per 1K views and the real RPM in YouTube Studio. Set kill or continue criteria up front with the user.

## Pitfalls

- **The scanner measures crowding by channel *search*,** a proxy. It counts channels matching the query, not every channel covering the topic or video-level competition. Use several queries per language and read the top channels (a big generalist channel can dominate a topic without matching the name).
- **The keyless backend is rate-limited.** It renders YouTube through r.jina.ai: about 3.5 s between queries, 429 backoff built in, and subscriber counts are YouTube's rounded display values ("4.25K"). For exact counts and higher volume, set `YOUTUBE_API_KEY` (YouTube Data API v3, free 10,000 units/day ≈ 95 queries) in `~/.hermes/.env`. Our Google OAuth token has Drive/Gmail scopes only, so YouTube calls return 403 with it.
- **YouTube blocks yt-dlp from this box's IP.** Don't plan on downloading reference videos here; the user supplies files.
- **Literal-translation queries miss the market's real search terms** ("retirement tips" → Brazilians search "aposentadoria INSS", "como se aposentar"). Ask an LLM for native search phrasing per market, then scan those.
- **The post's numbers are lead-gen copy.** Quote them as claims, with the source and date.
- **Channel search undercounts competition.** YouTube channel search matches channel NAMES, so topic owners with
  generic names never show up. German retirement scored 0-1 serious channels by channel search, but the owners of
  its top videos were Finanzfluss (1.65M), Finanztip (588K) and a dedicated pension channel (207K). Measure
  competition from the channels that own the top ~20 VIDEOS (look up their subscriber counts), as in
  `dive_de_retirement.py`. Treat channel-search counts only as a cheap first filter / lower bound.
- **Language-filtered search still returns global content.** French DIY looked like 1.17M median views, but the
  big videos were international hack compilations and English renovation timelapses, both needing real footage.
  Before trusting a niche, check that top-video titles are in the target language, owners are local, and the
  format is reproducible faceless. Score only those videos. Automated check:
  `~/.hermes/data/yt-arbitrage/niches/lang_check.py niche/lang ...` (title-language classifier; reports native
  share, native-only median and breakouts). It killed German/Spanish robotics (0-1 of 20 native) and German AI
  news (1 of 17) on 2026-10-05.
- **Small channels winning big views is the real opening signal**, not an empty search page (e.g. an 18.9K-sub
  channel with a 1.1M-view video).
- **Always re-check a "gap" with a second, differently-worded query.** In the 2026-10-04 niche scan, 2 of 6
  single-query gaps vanished (ja investing 3 -> 9 serious, es psychology 0 -> 7).
- **"Empty" can mean "no demand".** Check median views of the top videos too: de small business had 0 serious
  channels and 5,200 median views.
- **High views + no dedicated channels = generalist incumbents** (broad finance channels, broadcasters) own the
  topic. Still an opening for a specialist, but not "zero competition".
- **Spanish and Portuguese are not the empty markets the post claims.** Across 14 niches the median serious-channel
  count was de 1.5, fr 3, pt 8, ja 9.5, es 10.5, en 10.5, and DE/FR pay ~50-80% of US RPM vs ~15-40% for BR/MX.
  Full method and data: `~/.hermes/data/yt-arbitrage/niches/FINDINGS.md` (scanner: `niche_scan.py` there).

## Verification

Last run 2026-10-04 (keyless backend):

| Language | Query | Channels parsed | Serious (≥10K) | Top channel |
|---|---|---|---|---|
| en | retirement planning tips | 18 | 6 | 83.2K |
| pt | dicas de aposentadoria | 20 | 3 | 483K |
| es | consejos para la jubilación | 14 | 1 | 23.2K |
| de | Rente Tipps | 16 | 1 | 207K |

So the direction holds (fewer serious channels outside English), but not "zero competition": every market had at least one large incumbent. Re-run the scanner to confirm it parses; expect a non-empty table and a JSON file in `--out`.
