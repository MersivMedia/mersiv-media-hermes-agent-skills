# agency-agents → agency-agents-usa (2026-10-04)

- Upstream: github.com/msitarzewski/agency-agents (MIT, 282 agents, 18 divisions, `divisions.json`).
- Fork: public github.com/MersivMedia/agency-agents-usa, local `~/agency-agents` (remote `upstream` = msitarzewski,
  `origin` = fork, branch `usa-localization` pushed as `main`). Helper scripts in `~/agency-agents-tools/`
  (localize_usa.py, fix_readme.py, final_check.sh, build_install.sh, verify_install.sh, publish.sh).
- Hermes install: plugin `agency-agents-router` in `~/.hermes/plugins/` (4 tools; data/agents.json), enabled in
  config.yaml `plugins.enabled`.

## Commands
- Checks: `bash scripts/lint-agents.sh`, `bash scripts/check-divisions.sh`, `bash scripts/check-agent-originality.sh`,
  `python3 scripts/check-hermes-plugin.py`. Upstream baseline: lint 0 errors / 58 warnings (pre-existing).
- Rebuild + install after edits: `./scripts/convert.sh --tool hermes && ./scripts/install.sh --tool hermes`.
- Sync upstream later: `git fetch upstream && git merge upstream/main`, then re-run the China-term grep on new or
  changed agents only, rewrite new China-specific ones, re-run checks, rebuild, push.

## Rename map (China platform → US equivalent)
Baidu SEO → Google Search Ecosystem; Douyin → YouTube Shorts; Kuaishou → Facebook Community; Bilibili → Twitch;
Weibo → Threads & Bluesky; Xiaohongshu → Pinterest; Zhihu → Quora & Expert Q&A; WeChat Official Account →
Substack & Newsletter; Private Domain (WeCom) → SMS & Owned-Audience (TCPA, 10DLC); Livestream Commerce →
Live Shopping; Podcast (China) → Video Podcast; China E-Commerce → US E-Commerce; China Market Localization →
US Market Entry; China Network Engineer → US Enterprise Network (Cisco/Juniper/Palo Alto, NIST/CMMC);
WeChat Mini Program → App Clip & Instant App; GaussDB → Amazon Aurora PostgreSQL.
Retargeted in place: government presales (SAM.gov/GSA/FAR/FedRAMP), recruitment (EEOC/FCRA/I-9), corporate
training, supply chain (USMCA/Section 301/UFLPA), healthcare marketing compliance (FDA OPDP/FTC/HIPAA),
study abroad (American students going abroad). Kept: README credit for the Chinese translation repo,
Japanese examples in i18n/prompt-engineer agents.

## Open caveat
Study Abroad Advisor's visa/post-study-work details were written from memory by a subagent; not fact-checked.
