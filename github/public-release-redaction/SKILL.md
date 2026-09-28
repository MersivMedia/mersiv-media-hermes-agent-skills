---
name: public-release-redaction
description: Audit and redact private data before a public repo push.
version: 1.0.0
author: Mersiv Media + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [github, redaction, pii, secrets, audit, publishing]
    related_skills: [skill-backup, github-repo-management]
---

# Public Release Redaction Skill

Audits files for personal or sensitive data, redacts a staged copy, and
publishes that copy to a public GitHub repo. It then checks the remote itself
to confirm nothing leaked. Use it for skill subsets, project code and docs.
The automatic full skill backup belongs to `skill-backup`, not here.

## When to Use
- The user asks for an audit of files for PII, secrets or IDs before they go public.
- A one-off public repo is being made from private working material.

## Prerequisites
- `gh` authenticated (`gh auth status`).
- A list of this user's private terms: emails, volume or pod IDs, server IPs,
  home path, Drive IDs. Take them from memory.

## Procedure
1. **Audit first, then report and wait.** Output a JSON list of
   `{file, line, text, category, suggested}`. Also list the deliberate keeps
   with a reason for each: brand voice IDs that are useless without an API key,
   and titles of public articles. Say plainly that a regex audit isn't a full
   line-by-line read.
2. **Scan wide on pass one.** A narrow first pass (emails, keys, Drive URLs)
   missed several things:
   - bare Drive IDs (`\b1[A-Za-z0-9_-]{24,43}\b`, requiring both upper-case
     letters and digits)
   - `/home/<user>` paths
   - RunPod volume IDs
   - IDs hardcoded as script constants

   Grep every known private term as a literal. If a later pass finds more,
   tell the user the first report was incomplete.
3. **Redact a staged copy and leave the live source alone.** Live scripts need
   the real values. In the copy, turn hardcoded IDs into `os.environ[...]`
   lookups. Replace `/home/<user>/` with `~/`. Remove `__pycache__`, `*.pyc`
   and dotfile state. Then run `py_compile` and re-scan until the result is CLEAN.
4. **Destructive steps.** An `rm -rf` triggers an approval prompt. If the prompt
   times out, that counts as a refusal: never retry. Ask the user, and offer a
   fresh timestamped folder as the no-delete option.
5. **Name the repo.** Repo names can't contain spaces. Slugify the user's name
   and put the display name in the README title and the repo description.
   Public is the default.
6. **Push.** Run `gh repo create owner/name --public --source . --push`, and
   wrap `git push` in `timeout 120`. If that call is interrupted, the repo may
   already exist and be empty. On a later name change, run
   `gh repo rename <new> -R owner/<old> --yes` rather than creating a second
   repo. Then add the remote and push.

7. **De-brand when asked.** Brand-specific wording goes beyond the name. Replace
   brand names, handles and URLs with `[brand]`, `[brand-handle]` and `[brand-website]`,
   and characters and personas with `[character]`. Also sweep:
   - persona words (host titles, sidekick names, audience nicknames)
   - costume or logo nouns (logo shapes, props, headwear): replace with `[costume]`,
     `[costume variant N: …]` and `[brand emblem — describe your logo…]`
   - palette names and hex codes: use `[brand accent color]` and similar labels
     in prose, but keep a neutral default hex/RGB in code so the scripts still run
   - variable names (`PLASMA_GOLD` becomes `BRAND_ACCENT`) and env vars
     (`MYBRAND_*` becomes `BRAND_*`)
   - directory and file names (`git mv`), README links and voice shortcut keys

   Build the forbidden-term grep from every brand noun found. Run it to CLEAN
   **before** pushing: the first push once went out with a stale line.
8. **Check scope.** A skill subset isn't "all the skills". Tell the user the
   total count up front: all skills minus bundled (the repo's `skills/` and
   `optional-skills/` names) minus hub (`.hub/lock.json`). Scan the remaining
   personal skills and triage them into three groups: keep private (finances,
   resume, job hunt), fixable (ad publisher IDs, doc IDs, home paths) and needs
   a read-through (client or exec names). Wait for a go-ahead before adding any.

## Pitfalls
- **Git history keeps the redacted text.** Once edits are pushed after the first
  push, the earlier commits still show it. Offer to squash into one commit and
  force-push while the repo is new.
- **The commit author email is public**, even when it's scrubbed from the files.
  Disclose it, and offer the noreply address plus a history rewrite while the
  repo is still fresh.
- **raw.githubusercontent.com caches for a few minutes.** Right after a push,
  check content with `gh api repos/o/r/contents/<f> --jq .content | base64 -d`.
- **Placeholders are one-way.** Local files remain the source of truth.

## Verification
- Clone the repo fresh and re-run the leak grep on the clone: it should come back clean.
- The file count from the API tree (`git/trees/main?recursive=1`) should match the local count.
- The repo page should return HTTP 200, and `gh repo view` should show PUBLIC.
