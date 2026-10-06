---
name: agent-reach
description: "Use when reading a social platform, feed or URL via CLI."
version: 1.0.0
author: Hermes Agent (wraps Panniantong/Agent-Reach v1.5.0, MIT)
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [agent-reach, curl]
metadata:
  hermes:
    tags: [research, web, twitter, reddit, youtube, github, rss, linkedin, scraping, internet-access]
    related_skills: [blocked-page-recovery, last30days, social-post-extraction, xurl, xitter, youtube-content, blogwatcher, mcporter]
---

# Agent Reach (internet access router)

## When to Use

Agent Reach is a router over per-platform CLIs and APIs (Jina Reader, yt-dlp, gh, twitter-cli, rdt-cli, bili-cli, OpenCLI, an Exa MCP and others). Its `doctor` command tells you which backend currently works for each platform. Use it to **fetch** content: web pages, RSS, GitHub, YouTube/Bilibili metadata and subtitles, X/Reddit/LinkedIn/Instagram/Facebook posts (with login), V2EX, Xueqiu quotes and Boss Zhipin jobs.

**Prefer an existing dedicated skill first** (upstream says the same):

| Need | Use first |
|---|---|
| Paywalled, blocked or WAF'd page | `blocked-page-recovery` (provenance ladder) |
| "What are people saying about X in the last 30 days" | `last30days` |
| Read an X post or Article without login | `social-post-extraction` |
| Post or read on X with the API | `xurl` / `xitter` |
| YouTube transcript to summary | `youtube-content` (but see the YouTube pitfall) |
| RSS monitoring over time | `blogwatcher` |

Use Agent Reach when none of those fit, when one fails, or to check which backend works with `agent-reach doctor`. It never posts, comments or likes; it's read-only by design.

## State on this box (2026-10-04)

- **CLI:** v1.5.0 in its own venv `~/.venvs/agent-reach`, symlinked to `~/.local/bin/agent-reach`. Only read-only `install --env=auto` and `doctor` have been run, so nothing system-level has been installed or configured.
- **Working now (4/16):**
  - any web page via `curl -s "https://r.jina.ai/<URL>"` (works **without** a JINA_API_KEY, rate-limited)
  - RSS/Atom
  - V2EX
  - Bilibili search
- **Partial:**
  - GitHub: `gh` may already be authenticated; doctor just won't probe it live.
  - YouTube: yt-dlp is installed, but this box's IP is blocked by YouTube (see MEMORY), so expect failures whatever the config.
- **Not set up:**
  - Exa semantic search: needs `npm i -g mcporter` + `mcporter config add exa https://mcp.exa.ai/mcp --scope home`. It's free and keyless, but it's a config write, so ask first.
  - X/Reddit/LinkedIn/Instagram/Facebook/Xiaohongshu/Boss Zhipin need the user's own cookies or a logged-in desktop Chrome.

## Steps

1. Run `agent-reach doctor --json` and read `active_backend` per platform. `null` means "not live-probed", not "missing".
2. Say which platform and backend you're using.
3. Read the matching reference and follow its command group and retry chain. Never guess commands:
   - `references/web.md`: web pages and RSS
   - `references/search.md`: Exa and code search
   - `references/dev.md`: GitHub
   - `references/video.md`: YouTube, Bilibili, podcasts
   - `references/social.md`: X, Reddit, Facebook, Instagram, Xiaohongshu, V2EX
   - `references/career.md`: LinkedIn, Boss Zhipin
   - `references/finance.md`: Xueqiu

   The references are upstream's and mostly in Chinese; the commands are plain shell. `references/upstream-SKILL_en.md` is upstream's English router.
4. **Broad research:** combine sources in parallel (web/Exa + X/Reddit discussion), then synthesize. Cite every claim with its source URL, following `grounded-citations`.

## Hermes guardrails (override upstream)

- **Never run `agent-reach install --system`,** `--channels=...`, `configure --from-browser`, `skill --install`, or any `npm -g` / `pipx` install without the user's explicit OK for that specific channel. Upstream's default `install --env=auto` is read-only and fine.
- **No browser-cookie extraction.** `cookie_extract.py` can read Chrome cookie stores (rookiepy/browser_cookie3). Don't use it. If the user wants an X or Reddit login, they export cookies themselves with Cookie-Editor. Store them in `~/.hermes/.env` (chmod 600); never echo them, put them in argv, or leave them in logs. Advise rotation if they were pasted in chat.
- **Don't nag about updates.** Skip upstream's "run check-update after every big task and remind the user" rule. Update deliberately (Maintenance).
- **Ignore upstream's description routing.** Its frontmatter says "MUST USE for any research or any URL", which would take over `blocked-page-recovery`, `last30days` and others. This skill is deliberately narrower.
- **Boss Zhipin / Xiaohongshu / Xueqiu / Xiaoyuzhou are China-only platforms;** use them only if the user asks. For US research, the default sources are web, Exa, X, Reddit, LinkedIn and GitHub.

## Pitfalls

- **Jina keyless responses** can be cached snapshots ("This is a cached snapshot ... retry with caching opt-out"). For time-sensitive pages add `-H "X-No-Cache: true"`, or use `blocked-page-recovery`.
- **Reddit has no zero-config path any more.** Anonymous JSON endpoints are blocked; it needs OpenCLI (desktop Chrome) or rdt-cli + cookies.
- **YouTube on this box:** IP-blocked for yt-dlp on every client. Ask the user for the audio or video file, or use a transcript site through Jina.
- **PEP 668:** keep the CLI in its venv. Upgrade with `uv pip install --python ~/.venvs/agent-reach/bin/python <git-or-zip>`.

## Maintenance

Update with `git clone --depth 1 https://github.com/Panniantong/Agent-Reach /tmp/Agent-Reach && ~/.local/bin/uv pip install --python ~/.venvs/agent-reach/bin/python /tmp/Agent-Reach`. Then re-copy `agent_reach/skill/references/*.md` → `references/` and `SKILL_en.md` → `references/upstream-SKILL_en.md`. Keep `LICENSE.agent-reach`.

## Verification

- `agent-reach version` prints v1.5.0.
- `agent-reach doctor` reports 4/16 channels available (web, RSS, V2EX, Bilibili search).
- `curl -s -A "Mozilla/5.0" "https://r.jina.ai/https://example.com" | head -3` prints `Title: Example Domain`.
