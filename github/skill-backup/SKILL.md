---
name: skill-backup
description: Back up the skill library to a sanitized GitHub repo.
version: 1.0.0
author: Mersiv Media + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [backup, github, skills, redaction, secrets, sync]
    related_skills: [github-repo-management, hermes-plugin-development, skill-library-maintenance]
---

# Skill Backup Skill

Mirrors `~/.hermes/skills/` into the public repo
**github.com/<owner>/hermes-skills**, redacting private data first. A
leak gate quarantines any skill that still contains a secret, a private term,
or NSFW content. It backs up automatically on every skill create/edit/delete.
It doesn't back up memory, sessions, config, or `.env`.

## When to Use

- The user asks whether skills are backed up, or to force a backup now.
- A backup failed or a skill was quarantined (the log shows `QUARANTINED`).
- New private data (another email, volume ID, server IP) needs to be added
  to the redaction list.
- Setting this up on a new machine or profile.

## Prerequisites

- `gh` authenticated as the repo owner (`gh auth status`).
- Local clone at `~/hermes-skills` with `core.hooksPath=.githooks`.
- Plugin `~/.hermes/plugins/skill-backup/` listed in `plugins.enabled`.
- Private config `~/.hermes/data/skill-backup/config.json` (chmod 600).
  It is **never** copied into the repo.

## How It Runs

| Trigger | What fires |
|---|---|
| `skill_manage` create/edit/patch/delete/write_file/remove_file succeeds | plugin `post_tool_call` spawns a detached sync (20 s debounce) |
| `write_file`/`patch` on a path under the skills dir | same |
| Hourly | cron job `skill-backup-hourly` (no_agent script) catches curator and hand edits |
| Manual | `python3 ~/.hermes/skills/github/skill-backup/scripts/sync_skills.py` |

Bursts coalesce: one sync runs, at most one waits, and any extra triggers
exit right away because the waiting sync will pick up their changes.

## Quick Reference

```bash
S=~/.hermes/skills/github/skill-backup/scripts/sync_skills.py
python3 $S --dry-run            # build + gate into /tmp, no git
python3 $S                      # sync, commit, push
python3 $S --no-push            # commit locally only
python3 $S --scan ~/hermes-skills   # gate an existing tree (hook + CI use this)
```

Logs and state are in `~/.hermes/data/skill-backup/`: `sync.log`,
`hook.out`, `last_gate_report.json`. Set `SKILL_BACKUP_DISABLE=1` to turn
backups off.

## Procedure

1. **Pipeline.** Copy with excludes (dotfiles, `.archive`, curator state,
   `.env`/keys/credentials, db/log, `__pycache__`, and `exclude_skills` from
   config), then redact, then gate, then write `INDEX.md`, then commit and
   push. The pre-commit hook re-scans the tree, and CI `leak-scan` scans it
   again on GitHub.
2. **Redactions.** The home path becomes `~`. Config `literal_redactions`
   covers account emails, the RunPod volume and the server IP. Known key
   shapes become `<REDACTED_SECRET>`, and so do quoted `api_key = "..."`
   literals, unless the value looks like a placeholder. Private Drive/Docs
   IDs become `<DRIVE_ID>`. Public Colab links are left alone.
3. **Quarantine.** A gate hit holds back that skill's new content, and its
   last published version stays in the repo. Everything else still syncs,
   and the run exits with code 3. To fix one: read `last_gate_report.json`,
   then either add a redaction, edit the skill, or add it to
   `exclude_skills`.
4. **Adding a private term.** Add it to both `literal_redactions`
   (`[term, placeholder]`) and `block_terms` in the config, then run
   `--dry-run` and diff the result against the source.
5. **Script changes.** Edit `scripts/sync_skills.py` here and copy it to
   `~/hermes-skills/tools/sync_skills.py`, so CI runs the same gate.

## Pitfalls

- **Excluded by policy:** `red-teaming/godmode` (jailbreak templates) and
  `creative/ref-character-replacement-content-pipeline` (a workflow JSON
  that contains an explicit sexual prompt). Don't remove them from
  `exclude_skills` without asking the user.
- **Placeholders are not reversible.** Restoring from the repo gives back
  `<DRIVE_ID>` and similar markers. Local skills stay the source of truth.
- **The regex gate is not a full PII audit.** New skills that mention
  private people, clients, or finances need a human or subagent review;
  regex only catches known shapes and configured terms.
- **Running sessions** load plugins at startup. After installing or
  changing the plugin, restart the gateway and open TUI sessions.
- **Never force-push.** The user edits on GitHub. The sync pulls with
  `--rebase` before building and retries the push after rebasing.

## Verification

- `tail ~/.hermes/data/skill-backup/sync.log` shows `pushed`, with 0
  quarantined or a named skill.
- `gh run list -R <owner>/hermes-skills -L 1` shows success.
- `curl -s https://raw.githubusercontent.com/<owner>/hermes-skills/main/INDEX.md | head`
  returns 200.
- After a `skill_manage` patch, a new commit titled
  `backup: patch <name>` appears within about a minute.
