---
name: research-to-notebooklm
description: Curate 8-10 high-quality sources on a topic and drop a clean URL list into Drive for the user to feed into NotebookLM. Use when the user names a topic or hands you an article to expand on.
version: 2.1.0
author: B3Fr33
license: MIT
metadata:
  hermes:
    tags: [research, notebooklm, drive, sources]
    related_skills: [google-workspace, duckduckgo-search]
---

# Research → NotebookLM source list

The user feeds the URL list into NotebookLM and generates the study guide, FAQ, Audio Overview, and blog post themselves. **My job ends at delivering a curated URL list** — no per-source markdown summaries, no transcript, no blog post.

This keeps token cost low and matches what NotebookLM does natively (it ingests URLs directly).

## Parent Drive folder

```
https://drive.google.com/drive/folders/1Ry1eiSUiFa5ewekLur3gDahllaiMDxX-
PARENT_FOLDER_ID=1Ry1eiSUiFa5ewekLur3gDahllaiMDxX-
```

All topic subfolders go inside this folder. Override at runtime with `BLOGS_PARENT_FOLDER_ID`.

## Local working directory (persistent)

The batch runner stores `topics.json`, `_manifest.json` (resume state), and per-topic working files at:

```
~/.hermes/data/research-to-notebooklm/
├── topics.json              # array of topic configs (edit this to add/modify topics)
├── _manifest.json           # per-topic state — sources, folder IDs, done flag (don't hand-edit)
├── 01-pure-play-space-stocks/
│   ├── sources.txt
│   └── video-prompt.txt
├── 02-rocket-lab-vs-spacex/
│   └── ...
```

This path is **persistent across reboots** (was previously `/tmp/hermes/research/` which wiped on reboot).
Override via `BRAND_RESEARCH_ROOT` env var if you need to run isolated batches.

The runner auto-creates this dir on first import — no manual setup needed.

## Folder layout convention

**This is the canonical layout in production. Use this exact shape unless the user is on a different brand:**

```
<Parent Blogs folder>/
  └── NN - <Topic Display Name> — <Pillar>/    # flat, numbered, pillar-tagged
      ├── sources.txt                          # one URL per line
      └── prompt.txt                           # NotebookLM brief (~700-750 words, mobile single-paste)
```

Key rules:
- **Zero-padded number prefix** (`01`, `02`, ... `28`) — pick `max(existing) + 1`. Numbers are global across the Blogs/ folder, not per-pillar.
- **Em-dash separator** between title and pillar: `28 - Space Data Centers and Orbital AI — Investing`. That's a real em-dash (U+2014), not a hyphen.
- **Four example content pillars**: `Investing`, `Careers`, `Beginners`, `Tourism`. Pick the dominant angle; if it's a tie, `Investing` wins for company/market topics, `Beginners` wins for explainer/concept topics.
- **Flat structure** — sources.txt and prompt.txt live directly inside the numbered folder. No `research/` subfolder. (The legacy `<Topic>/research/` layout is older and was abandoned; the actual Drive shows the flat numbered convention end-to-end.)
- **File names**: `sources.txt` and `prompt.txt`. Not `video-prompt.txt`. The batch runner emits `video-prompt.txt` historically but the user's current single-topic flow expects `prompt.txt`.

To pick the next number, list existing folders in Blogs/ and take max+1:

```bash
GAPI="python3 ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_api.py"
$GAPI drive search "'1Ry1eiSUiFa5ewekLur3gDahllaiMDxX-' in parents and mimeType='application/vnd.google-apps.folder'" --raw-query --max 50
```

Parse the leading `NN -` from each name. Numbers may not be contiguous if folders were renamed; always go off the max.

For other brands or one-off projects where the user doesn't want the numbered convention, fall back to the older `<Topic>/research/` layout — but confirm with the user first rather than assuming.

## What's automated vs. manual

| Step | Automated? |
|------|------------|
| Search + rank + dedupe sources | ✅ |
| Create Drive folders | ✅ |
| Upload sources.txt to Drive | ✅ |
| Upload video-prompt.txt (single-narrator NotebookLM Video Overview brief) to Drive | ✅ |
| NotebookLM ingestion / Audio Overview / Video Overview / blog post | ❌ User does this in NotebookLM |

Do NOT generate per-source markdown excerpts, transcripts, or blog posts unless the user explicitly asks. That's wasted tokens — NotebookLM does it better.

## Preconditions

```bash
GSETUP="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/setup.py"
$GSETUP --check    # must print AUTHENTICATED (Drive scope is sufficient)
```

The batch runner (`scripts/run_research.py`) imports `ddgs` (the DuckDuckGo search package). Install into the venv you'll invoke it with:

```bash
/tmp/hermes/venv/bin/pip install ddgs   # or whatever venv you use
```

If `ddgs` is missing, every topic in the batch fails fast with `No module named 'ddgs'` — the script catches per-topic exceptions and continues, so you'll see "=== Done ===" with zero successful uploads. Always tail the log before declaring success.

## Workflow

### Step 1 — Lock the topic

If the user gave you an article URL, use `web_extract` to read it and propose a topic phrasing in one sentence. Confirm before searching unless the user has already named the topic clearly.

Pick a clean display name (e.g., "James Webb Telescope") and a slug for local working files (`james-webb-telescope`).

### Step 2 — Gather candidates with multiple search angles

```python
from ddgs import DDGS
import time

queries = [
    f"{topic} site:arxiv.org",                  # papers
    f"{topic} site:github.com",                 # repos / code
    f"{topic} official documentation",          # primary docs
    f"{topic} 2024 OR 2025",                    # recent coverage
    f"{topic} overview",                        # broad intros
]

candidates = []
seen = set()
with DDGS() as ddgs:
    for q in queries:
        for r in ddgs.text(q, max_results=6):
            href = r.get("href", "")
            if href and href not in seen:
                seen.add(href)
                candidates.append(r)
        time.sleep(1.2)   # rate-limit cushion
```

### Step 3 — Rank, dedupe, pick 8-10

Score by domain quality (rough tiers):
- **100** — official sources for the topic (nasa.gov, esa.int, stsci.edu, openai.com docs, project homepages, etc.)
- **95** — arxiv.org, peer-reviewed preprints
- **85** — nature.com, science.org, ieee.org
- **80** — github.com (high-star repos)
- **70** — scientificamerican.com, skyandtelescope.org, established tech publications
- **50** — wikipedia.org (broad reference, fine to include 1)
- **20** — everything else
- **skip** — pinterest, facebook, twitter/x, instagram, tiktok, reddit, content farms

Dedupe by domain — max 1 per domain except arxiv/github/nasa-like primary sources (max 3).

Aim for a mix:
- 2-3 official / primary sources
- 1-2 papers (arxiv preferred)
- 1 repo (if code-relevant)
- 3-5 articles / news / explainers
- Optional 1 Wikipedia for breadth

### Step 4 — Sanity-check the URLs

Quick liveness check to weed out 404s before delivery. **Always try GET fallback after HEAD** — many finance, SEC, paywalled, and bot-protected sites (Yahoo Finance, MarketWatch, Tipranks, Seeking Alpha, SEC EDGAR direct links) return 403 or 405 on HEAD but 200 on GET:

```python
import subprocess
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def alive(url, timeout=8):
    # HEAD first
    r = subprocess.run(["curl", "-fsLI", "-A", UA, "--max-time", str(timeout), url],
                       capture_output=True, text=True, timeout=timeout + 3)
    if r.returncode == 0:
        return True
    # GET fallback — discard body
    r2 = subprocess.run(["curl", "-fsL", "-A", UA, "--max-time", str(timeout), "-o", "/dev/null", url],
                        capture_output=True, text=True, timeout=timeout + 3)
    return r2.returncode == 0

final = [c for c in top_picks if alive(c["href"])]
```

If a URL fails, drop it and substitute the next-ranked candidate. Topics in the **finance / investing niche regularly come up 1-3 sources short** because of bot blocks — note this in your delivery message rather than re-running endlessly.

### Step 5 — Create Drive folders

```bash
GAPI="python ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_api.py"
PARENT="1Ry1eiSUiFa5ewekLur3gDahllaiMDxX-"

# Topic folder
$GAPI drive create-folder "<Topic Display Name>" --parent $PARENT
# capture .id → TOPIC_FOLDER_ID

# Research subfolder
$GAPI drive create-folder "research" --parent $TOPIC_FOLDER_ID
# capture .id → RESEARCH_FOLDER_ID
```

If the topic folder already exists from a prior run, search first and reuse:

```bash
$GAPI drive search "<Topic Display Name>" --max 5
```

### Step 6 — Write sources.txt and video-prompt.txt, upload both

Plain URL list, one per line. No annotations — NotebookLM doesn't use them.

```bash
cat > ~/.hermes/data/research-to-notebooklm/<topic-slug>/sources.txt <<EOF
https://...
https://...
...
EOF
```

Also write `video-prompt.txt` — a brand-locked NotebookLM Video Overview brief (single faceless narrator, ~700-750 words, mobile single-paste). Template at `templates/video-prompt.txt`. `run_research.py` generates this automatically. The template is brand-locked to one [brand]; fork the template (and update the script's path) for other brands.

We deliberately do NOT emit a separate podcast/study-guide `prompt.txt` anymore. The NotebookLM Video Overview audio is reused as the podcast track, so we only need the single video brief. (See `write_prompt()` in `run_research.py` — it raises NotImplementedError if anything tries to call it.)

```bash
$GAPI drive upload ~/.hermes/data/research-to-notebooklm/<topic-slug>/sources.txt --parent $RESEARCH_FOLDER_ID
$GAPI drive upload ~/.hermes/data/research-to-notebooklm/<topic-slug>/video-prompt.txt --parent $RESEARCH_FOLDER_ID
```

**Re-runs:** if you're updating an existing topic, delete prior `sources.txt`/`video-prompt.txt` (and any legacy `prompt.txt`/`videoprompt.txt`) in the folder before uploading or you'll get duplicates with Drive-appended numbers:

```bash
# search the research folder, then delete any old sources.txt / video-prompt.txt / legacy files
$GAPI drive search "'$RESEARCH_FOLDER_ID' in parents and trashed = false" --raw-query --max 20
$GAPI drive delete <old_file_id>
```

### Step 7 — Deliver to user

Brief message — no fluff. Format:

```
◆ <N> sources curated for <Topic Display Name>.
◆ Drive: <research folder URL>

Sources:
1. <Title> — <URL>
2. ...

Paste sources.txt into NotebookLM → Add source → Website.
```

That's it. Stop. The user takes over from here.

## Single-topic on-demand flow ([brand])

For one-off "research topic X" requests, skip the batch runner and do it manually. Faster, no `topics.json` ceremony.

```bash
GAPI="python3 ${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_api.py"
BLOGS_PARENT="1Ry1eiSUiFa5ewekLur3gDahllaiMDxX-"

# 1. List existing numbered folders, find max number
$GAPI drive search "'$BLOGS_PARENT' in parents and mimeType='application/vnd.google-apps.folder'" --raw-query --max 50
# parse leading "NN -" → next number = max + 1

# 2. Pick pillar (Investing/Careers/Beginners/Tourism) and create folder
$GAPI drive create-folder "28 - <Topic> — <Pillar>" --parent $BLOGS_PARENT
# capture .id → TOPIC_FOLDER_ID

# 3. Research with web_search (8-10 sources covering multiple angles), build sources.txt
# Write to /tmp/mp_NN/sources.txt and /tmp/mp_NN/prompt.txt

# 4. Upload both
$GAPI drive upload /tmp/mp_NN/sources.txt --parent $TOPIC_FOLDER_ID
$GAPI drive upload /tmp/mp_NN/prompt.txt --parent $TOPIC_FOLDER_ID
```

The `prompt.txt` for single-topic flow is a thematic brief (not the brand-locked Video Overview template). Structure: hook, 3-5 numbered threads with bullets, tone notes, closing framing question. ~700-1000 words. Two trailing blank lines for mobile copy-paste. See `references/single-topic-prompt-structure.md` for the field-tested shape.

`python3` not `python` — on some ops boxes there is no `python` shim. Hardcode `python3` in command snippets the agent will paste.

## Multi-topic batch runs (channel content pipelines)

When the user wants research for many topics at once (e.g., 20 blog/YouTube/podcast topics for a content channel), use `scripts/run_research.py` in this skill — it handles search, ranking, dedupe, liveness check, folder creation, and upload, with a manifest for resume on failure. Load it with `skill_view(name='research-to-notebooklm', file_path='scripts/run_research.py')`.

**Workflow:**

1. Build a `topics.json` array. Each entry needs:
   ```json
   {
     "n": 1,
     "folder": "01 - Pure-Play Space Stocks",
     "title": "The 5 Pure-Play Space Stocks You Can Actually Buy",
     "niche": "investing",
     "queries": ["query 1", "query 2", "query 3", "query 4", "query 5"],
     "prompt_focus": "1-2 sentence angle + tone + audience guidance"
   }
   ```
2. Run in batches of 5-10 topics. Background the process with `notify_on_complete=true`.
3. Manifest is written to `~/.hermes/data/research-to-notebooklm/_manifest.json` — `done: true` per topic. Resume by re-running with the same range; finished topics are skipped.
4. After each batch, print a status table showing source counts per topic and flag any < 8 sources.

**Pacing (empirically validated against DDGS throttling):**
- 2.5 seconds between queries within a topic
- 3 seconds between topics
- 5 queries × 6 results × 10 topics ≈ 4 minutes per batch
- DDGS will throttle past ~50-60 rapid queries; the manifest+pacing combo avoids this

**Audience defaults by niche** (used in `video-prompt.txt` for content channels):
- `investing` — Retail investors comfortable with tickers and basic financials, NOT MBAs
- `careers` — Job seekers, career-switchers, students considering aerospace
- `beginners` — Curious adults who think the topic is cool but were lost by expert content
- `tourism` — Travelers, bucket-listers, experience-buyers

Use `templates/video-prompt.txt` for the brand-locked NotebookLM Video Overview brief (single-narrator format, the only prompt emitted by this pipeline).

## Pitfalls
- **Missing `ddgs` in the venv** — script fails fast on every topic with `No module named 'ddgs'`, but exits cleanly because per-topic failures are caught. Always check the log for `!!!` lines before declaring success. Fix: `pip install ddgs` in the active venv.
- **Misleading log line** — `run_research.py` prints `"Creating Drive folder: <name>"` even when `find_or_create_folder` *found* an existing one. If you see this for a topic you already created, don't panic — search Drive to confirm there are no duplicates (there usually aren't). Cosmetic-only; not yet patched.
- **DDGS rate limits** — sleep 1.2s between query batches for single-topic runs, 2.5s+ for multi-topic batches.
- **Finance/SEC/paywalled sources often fail HEAD checks** — use the GET-fallback alive() pattern from Step 4. SEC EDGAR, Yahoo Finance, MarketWatch, Tipranks, Seeking Alpha, investor-relations pages routinely 403 on HEAD. If a topic still comes up short (6-7 sources), ship it and note the gap rather than spinning forever.
- **Drive duplicate uploads** — Drive accepts same-name files in the same folder, creating "sources.txt (1)" / "sources.txt (2)". On re-runs, search the research folder and delete prior `sources.txt`/`video-prompt.txt` (and any legacy `prompt.txt`/`videoprompt.txt`) before uploading.
- **Drive parent folder ID** — the ID after `/folders/` in the URL, never the full URL.
- **Always pass `--parent FOLDER_ID`** on uploads or files dump into Drive root.
- **Topic-folder collisions** — if a folder by that name already exists in the parent, ask the user whether to reuse it or create one with a date suffix.
- **Dead links** — always HEAD-check before delivery. Bad URLs poison the NotebookLM ingest.
- **Don't include paywalled sources** unless the user already has access. NotebookLM can't bypass paywalls.
- **YouTube URLs** are OK — NotebookLM accepts them as sources, but verify the video exists and has captions/transcript.

## Verification before declaring done

- `sources.txt` has N URLs, one per line, no commentary
- Drive folder exists and `sources.txt` is inside the research subfolder
- All URLs return HTTP 200
- Final message includes the Drive URL and the numbered source list
