---
name: skill-library-maintenance
description: Merge duplicate local skills safely and verifiably.
version: 1.0.0
author: Mersiv Media + Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, curator, duplicates, merge, archive, library]
    related_skills: [hermes-plugin-development, hermes-agent-skill-authoring]
---

# Skill Library Maintenance Skill

Keeps the local skill library class-level: finds overlapping skills, folds
the duplicates into one keeper without losing content, and archives the rest
through Hermes' curator so every step can be undone. It does not cover
authoring new skills (see `hermes-agent-skill-authoring`), and it never
touches bundled, hub-installed, pinned or external skills.

## When to Use

- The user asks to find or merge similar/duplicate skills.
- A duplicate-skill audit (e.g. `hermes jermes skills-audit`) has produced
  merge suggestions and the user approved some groups.
- A new skill is about to duplicate an existing one and the user chose to
  extend the original instead.

## Prerequisites

- Hermes with the curator CLI (`hermes curator archive|restore <name>`).
- The user's go-ahead per group. Skill edits need their say-so: present the
  groups, the proposed keeper and your own read of each, then wait.

## Quick Reference

| Step | How |
|---|---|
| Find overlaps | `hermes jermes skills-audit [--limit 8]` (~2 Jev requests/skill; suggestions only) |
| Locate skill dirs | walk `~/.hermes/skills/**/SKILL.md`, read `name:` from frontmatter, skip `.archive/` |
| Back up | tar the keeper + folds to `~/.hermes/data/<tool>/backups/skills-before-merge-<ts>.tar.gz` |
| Edit keeper | `skill_manage patch` / `write_file` (references/) — by **directory name** |
| Archive a fold | `hermes curator archive "<skill name>"` (display names with spaces work, quoted) |
| Undo | `hermes curator restore <name>`, or extract the tarball |

## Procedure

1. **Audit, then judge each group yourself.** Read both descriptions and
   headings before agreeing. Jev's grouping was right on all four live
   groups. The keeper rule is now: bundled/hub first, then "contains the
   others", then (on a tie only) Jev's pick of the broadest scope, then
   length. Length alone once picked the narrower skill, because it was
   longer only from being more detailed. Still check the suggested keeper's
   scope yourself. Say which groups are clear duplicates and which are only
   partial overlaps.
2. **Start with a trial**, e.g. `--limit 8`, before the full library run.
3. **Back up first**, then map every skill in the group to its directory
   and file list (SKILL.md plus any reference, script and template files).
4. **Find inbound references before archiving.** Grep all live `*.md`
   under `~/.hermes/skills/` for each fold's name and directory slug, and
   check `~/.hermes/cron/jobs.json`. Repoint any live pointer to the keeper
   (one skill's reference file named a fold that was about to go).
5. **Read every skill in the group in full**, then fold:
   - Keep the keeper's structure; add what's genuinely new as sections, or
     move session-specific detail into a new `references/<topic>.md` with a
     one-line pointer from SKILL.md.
   - Copy the folds' reference files across (`cp -n`, then `cmp`); rename on
     a name clash rather than overwrite.
   - Where the folds contradict the keeper (e.g. one-pass vision vs an OCR
     cascade), keep both and state when each applies.
   - Tighten the description to one sentence ≤60 chars; bump `version`.
   - Add "Merged in from `<fold>` (<date>)" at the top of each new
     reference file, so provenance survives.
6. **Verify before archiving** (script it with `execute_code`):
   - list the distinct points from each fold (numbers, named techniques,
     pitfalls) and assert each string appears in the keeper or its
     references — 28 checks for a three-way merge;
   - every `references/*.md` named in SKILL.md exists, and every file in
     `references/` is named in SKILL.md (this caught one pre-existing
     unlinked file, and one fold that pointed to a file that never existed);
   - frontmatter parses; `related_skills` names resolve to live skills.
7. **Archive the folds** with `hermes curator archive`, then confirm the
   fold names no longer appear in the live set.
8. **Re-run the overlap check on the keepers only.** Success is no pair
   above the threshold (after the live merge, the closest match was 28%).
9. **Report per group:** keeper, what was folded where, anything found
   along the way, and the undo command plus backup path.

## Pitfalls

- **`skill_manage` resolves skills by directory name, not display name.**
  Skills whose frontmatter `name:` has spaces or capitals
  (e.g. "AI Tool Deployment Troubleshooting & Recovery" in
  `ai-tool-deployment-troubleshooting/`) appear under the display name in
  `skills_list`, but `skill_manage patch|write_file name=<display name>`
  returns "not found". Use the directory name. Three edits failed silently
  in a batch before this was noticed — check each result.
- **`related_skills` and prose pointers use display names.** When linking to
  such a skill from another skill, write its frontmatter `name:`, and check
  it exists in the live name set; a slug in `related_skills` doesn't resolve.
- **Don't archive before the content check passes.** Archiving is
  reversible, but a fold archived with unmerged content is easy to forget.
- **Never edit protected skills.** Bundled/hub skills can be keepers in
  suggestions ("keep the bundled one, archive your local copy, move unique
  bits to a local references file"), but their files stay untouched.
- **Large inline shell payloads can be refused** by Hermes' command parser.
  Do multi-line analysis in `execute_code` and read files with `read_file`.
- **Unexpected skill edits: check the curator ledger.**
  `~/.hermes/skills/.curator_ledger.jsonl` records every skill mutation, with
  its actor, session id and per-file sha256 before and after. Use it to
  find edits that didn't come from the user (e.g. test agents writing
  through a symlinked skills dir) and to prove a revert is exact: rebuild
  the file until its hash equals the `before` hash. A bundled skill can be
  restored from the Hermes checkout when that copy's hash matches. Keep the
  changed version in a backup dir before reverting.

- **Publishing a curated subset publicly** (not the automatic mirror): see
  `references/curated-public-release.md` — audit wide on the first pass,
  redact a staged copy, and gate to zero hits before the first push.

## Verification

- Every fold's distinct points present in the keeper (scripted check).
- No dangling or unlinked reference files in any keeper.
- No live skill or cron job still names an archived fold.
- `hermes curator archive` output shows each fold under `.archive/`.
- A fresh overlap check on the keepers finds nothing above threshold.
