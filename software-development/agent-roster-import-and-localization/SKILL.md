---
name: agent-roster-import-and-localization
description: "Use when importing third-party agent rosters or skill packs."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [agents, prompts, subagents, plugins, localization, fork, roster, personas]
    related_skills: [hermes-plugin-development, subagent-driven-development, github-repo-management, humanizer]
---

# Importing and localizing third-party agent rosters

## When to Use
- "Look at this repo and add the agents to your skills/subagents" (collections of persona/system-prompt
  markdown files: agency-agents, awesome-prompts-style repos, Claude Code agent packs).
- "Change every reference to country/market X into Y" across such a roster.
- Publishing the result as the user's own fork.
- "Add these agents and skills, merge duplicates" from repos that ship `SKILL.md` folders (awesome-llm-apps),
  "add this to the video/motion skills" for framework repos with their own skill packs (HyperFrames, Lemo-Opuscar),
  or CLI tools that ship an agent skill (Agent-Reach). See Pitfalls for vendoring, duplicate merging,
  hijacking descriptions and archive-by-path.

**Placement rule for imported skills:** attach them to the existing umbrella they serve and link both ways
(e.g. motion-graphics → `lemo-opuscar` for named art styles, `hyperframes` for footage/captions/decks; each
gets a "which engine when" line in motion-graphics' routing list). Web/research tools go under research, never
under the umbrella the user named if they don't fit it; say so in the report.

## Workflow

1. **Clone and survey first** (shallow clone to /tmp, then a working clone in `~/<repo>` on a feature branch).
   Count agents per division, read LICENSE, and look for `integrations/hermes`, `scripts/build-hermes-plugin.py`,
   `scripts/install.sh --tool hermes`. **Prefer the repo's own Hermes integration** over hand-made skills.
2. **Install shape: one lazy router plugin, never N skills.** Hundreds of agents as flat skills would bloat
   every session's skill index. A router plugin exposes ~4 tools (search / read / use / delegate a specialist)
   and loads persona text on demand. Before trusting it:
   - build into a temp dir and run `HERMES_HOME=/tmp/x hermes plugins doctor <plugin dir>` (expects
     "runtime discovery, manifest parsing, import, and registration passed");
   - grep the builder for subprocess/network/eval before running third-party code;
   - back up `~/.hermes/config.yaml` before the installer edits `plugins.enabled`.
3. **Localization: measure the scope first, then ask once.** Grep the country/demonym terms AND the
   platform names (for China: Baidu, Douyin, WeChat, WeCom, Weibo, Bilibili, Kuaishou, Xiaohongshu, Zhihu,
   Taobao/Tmall, Pinduoduo, 1688, Huawei/H3C, GaussDB, ICP/MLPS, CJK text). Split hits into:
   - incidental mentions → mechanical swap is fine;
   - agents whose whole subject is a country-only platform → a literal swap produces false statements
     ("the USA's leading short-video platform Douyin").
   Ask with `clarify` how to handle the second group (drop / rewrite into real equivalents / literal /
   keep). **This user chose "rewrite each into a real US equivalent"** (Baidu SEO → Google Search ecosystem,
   WeChat → Substack/SMS); recommend that first for this user.
4. **Mechanical pass via a script** (`localize_usa.py` pattern): ordered regexes, longest token first;
   protect URLs/domains, credits for translations, and terms where the country is factual (Japanese i18n
   examples, translation credit lines). Dry-run, review a sample diff, then apply.
5. **Rewrite the platform-specific agents with parallel subagents** (≤3 at a time), each given a
   **disjoint file list**, the old→new path and name for every file, the existing agents it must not
   duplicate, and these rules: keep the original's section structure/depth (read it via
   `git show HEAD:<path>`), accurate real-world equivalents (platforms, regulations, holidays), no invented
   statistics (replace fixed numeric targets with "measure against your baseline"), `git mv` for renames,
   run the repo linter, don't touch README, don't commit. Use `output_schema` for an old|new|name|emoji table.
   - A worker with 12 files timed out at 600 s. Keep batches ≤8 files; on timeout, diff each assigned file
     vs HEAD (leftover terms + lint + % changed) to find which are actually unfinished, and re-dispatch only
     those with "read once, write the whole file in one write_file, lint".
6. **Fix the README roster yourself** (tables link to renamed paths): regenerate rows for every changed
   agent, then check every relative link resolves.
7. **Verify with the repo's own checks and compare to upstream's baseline**: lint, division consistency,
   originality, plugin schema check. Run the linter on `git stash`ed upstream too: equal warning counts mean
   the rewrite added none. Final grep across all agents + README + examples for leftover terms and crude-swap
   phrases ("the USA's", "USA market", "American internet").
8. **Build → install → verify installed data**, not just exit codes: plugin doctor OK, `plugins list` shows
   enabled, the installed `agents.json` contains the new names and zero leftover terms. Tell the user it takes
   effect in the next session (`/new` or gateway restart).
9. **Publishing a fork** (user default: public): rename `origin` to `upstream`, `gh repo create
   <Org>/<name>-<variant> --public`, push the branch as `main`, set topics. Add a top-of-README notice
   (what changed, link to upstream, MIT kept) and a change table (original → new, linked). Verify with a
   fresh clone from GitHub, not the local copy.

## Pitfalls
- **Big multi-skill framework repos (HyperFrames: 21 skills, a router calling itself "mandatory entry point
  for any video request", plus a skill whose name clashes with ours):** vendor them under ONE Hermes entry skill's
  `references/skills/` (a support dir, so Hermes doesn't index them; no clash, no hijack). Write a thin Hermes SKILL.md
  with a routing table and an "overrides of upstream" section (skip usage/telemetry/desktop-app/self-update
  steps). Check with `agent.skill_utils.iter_skill_index_files` that nested names are NOT indexed.
- **skill_manage create refuses a name that already exists anywhere in the tree,** including nested vendored copies.
  Write the entry SKILL.md with write_file instead, then lint it.
- **Tools with "MUST USE for any research/URL" descriptions (Agent-Reach):** narrow the trigger, defer to existing
  dedicated skills, and forbid their system installs and browser-cookie extraction without per-channel consent.
- **Not every "agents" repo is a persona roster.** awesome-llm-apps-style repos are ~170 runnable code apps
  (Streamlit + Agno/ADK/OpenAI Agents SDK), not system prompts. Don't turn apps into skills or subagents:
  build ONE catalog skill (`awesome-llm-apps-catalog`, generated by `~/agency-agents-tools/build_catalog.py`:
  path | what | detected stack | overlapping agency specialist). Import only real `SKILL.md` folders.
- **Vetting third-party SKILL.md folders:** `scripts/skill_scanner.py <dir>` (install lures, undeclared
  network, credential access, obfuscation) and `scripts/skill_lint.py <skill> --strict` (agentskills.io spec;
  its warnings about `version`/`author`/`platforms` keys are expected for Hermes-format skills). Grep bundled
  scripts for subprocess/urllib/servers and check they're local-only. Back up `~/.hermes/skills` (tar) first.
- **Duplicate check before installing:** token-overlap of name+description+headings vs every live skill
  (`dup_check.py`), then read the top candidates yourself. Fold a true duplicate into the existing keeper as a
  section + `references/` (e.g. advisor-orchestrator-worker → subagent-driven-development), keep the
  upstream license file next to copied content, and soften "MANDATORY for ALL X" descriptions so an imported
  skill doesn't hijack routing from existing ones. Skip skills marked DEPRECATED upstream.
- **Archiving duplicate skills: move by PATH, not `hermes curator archive <name>`.** The curator (and
  `skill_usage._find_skill_dir`) resolves by frontmatter `name:` and returns the first match. When a stale
  pre-rename copy shares its name with the current one (e.g. `mlops/evaluation/lm-evaluation-harness` vs
  `evaluating-llms-harness`), it can archive the wrong copy. Tar the two dirs, `mv` the stale one into
  `~/.hermes/skills/.archive/`, then confirm each name resolves to exactly one live path and `hermes skills list`
  still shows it enabled. Before archiving, diff lines unique to the old copy so nothing current is lost.
- **`skill_lint.py` treats any `references/...` or `scripts/...` text as a path inside the current skill.** Pointing
  from one skill to another skill's files fails lint with "no such file". Word it as
  `skill_view(name="<other>", file_path=...)`, or wrap the cross-skill call in a small script inside this skill
  (e.g. viral-youtube-video's `voice.sh` wraps a brand pipeline's TTS emitter), then run `bash -n` on it.
- **Survey big repos in stages, writing each step to a `.sh` file:** layout + LICENSE + SKILL.md list, then
  per-skill name/description/size, then a live smoke render or CLI run on this box. Their quickstarts often
  phone home (telemetry, usage commands reading other tools' credential files, desktop-app nags): check the
  config dir they create (e.g. `~/.hyperframes/config.json` → `telemetryEnabled`) and note the override in the
  entry skill.
- Inline giant shell one-liners get hard-blocked by the command parser; put survey/verify steps in a
  `.sh` file and run it bare.
- Subagent reports are self-reports: one worker wrote visa rules "from memory". Flag such files to the user
  as needing a fact-check before serious use.
- Don't leave crude-swap nonsense in otherwise-kept files: hand-fix single lines where the swap made a false
  claim (e.g. "red = rising in American finance" → name the markets where that is true).

## References
- `references/agency-agents-usa.md`: the msitarzewski/agency-agents → MersivMedia/agency-agents-usa run
  (rename map, scripts, check commands, rebuild/sync steps).
