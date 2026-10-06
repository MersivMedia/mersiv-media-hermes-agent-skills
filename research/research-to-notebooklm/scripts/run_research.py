#!/usr/bin/env python3
"""
Batched multi-topic research runner.

Reads /tmp/hermes/research/topics.json (array of topic dicts), and for each:
- searches DDGS with the given queries (paced for rate limits)
- ranks + dedupes by domain quality
- HEAD-checks with GET fallback (finance/SEC sites block HEAD)
- finds/creates Drive folders: <Parent>/<topic.folder>/research/
- writes sources.txt (URLs only) + video-prompt.txt (single-narrator NotebookLM Video Overview brief)
- uploads both to the research subfolder
- persists progress to /tmp/hermes/research/_manifest.json for resume

Usage:
    python3 run_research.py            # runs all topics
    python3 run_research.py 1 5        # runs topics 1-5 inclusive

Topic schema (topics.json is an array of these):
    {
      "n": 1,
      "folder": "01 - Pure-Play Space Stocks",
      "title": "The 5 Pure-Play Space Stocks You Can Actually Buy",
      "niche": "investing" | "careers" | "beginners" | "tourism" | "...",
      "queries": ["q1", "q2", "q3", "q4", "q5"],
      "prompt_focus": "1-2 sentences capturing angle, audience, tone"
    }

Configure PARENT_FOLDER_ID for the target Drive parent. Default is the user's
"Blogs" folder. Override via env var BLOGS_PARENT_FOLDER_ID.
"""
import json, time, subprocess, os, sys, re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(
    os.environ.get(
        "BRAND_RESEARCH_ROOT",
        os.path.expanduser("~/.hermes/data/research-to-notebooklm"),
    )
)
ROOT.mkdir(parents=True, exist_ok=True)
MANIFEST = ROOT / "_manifest.json"
TOPICS_FILE = ROOT / "topics.json"
PARENT_FOLDER_ID = os.environ["BLOGS_PARENT_FOLDER_ID"]
GAPI_SCRIPT = os.path.expanduser("~/.hermes/skills/productivity/google-workspace/scripts/google_api.py")

PRIORITY = {
    # Primary/official
    "nasa.gov": 100, "esa.int": 100, "stsci.edu": 100, "webbtelescope.org": 100,
    "spacex.com": 100, "rocketlabusa.com": 100, "blueorigin.com": 100,
    "virgingalactic.com": 100, "ast-science.com": 100, "axiomspace.com": 100,
    "darksky.org": 100, "spaceperspective.com": 100, "zerog.com": 100,
    # Regulator / academic
    "sec.gov": 95, "arxiv.org": 95, "nasaspaceflight.com": 90,
    # Reputable industry/news
    "spacenews.com": 90, "arstechnica.com": 85, "reuters.com": 85,
    "bloomberg.com": 85, "wsj.com": 85, "ft.com": 85,
    "nature.com": 85, "science.org": 85,
    # Investing / finance
    "levels.fyi": 85, "stockanalysis.com": 80, "seekingalpha.com": 75,
    "cnbc.com": 75, "investopedia.com": 70, "yahoo.com": 70, "fool.com": 60,
    # Science / space media
    "space.com": 65, "skyandtelescope.org": 75, "scientificamerican.com": 75,
    "phys.org": 60, "sciencealert.com": 55,
    # Code / docs
    "github.com": 80,
    # Travel
    "atlasobscura.com": 70, "nationalgeographic.com": 80, "lonelyplanet.com": 65,
    # Reference
    "wikipedia.org": 50,
    # Lower-tier
    "youtube.com": 35, "medium.com": 30,
}

JUNK_SUBSTRINGS = [
    "pinterest.", "facebook.", "twitter.com", "instagram.", "tiktok.",
    "reddit.com",
    "/tag/", "/category/",
]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def slug(name):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return s[:60]


def score(url):
    host = urlparse(url).netloc.lower().replace("www.", "")
    for dom, sc in PRIORITY.items():
        if dom in host:
            return sc
    return 20


def is_junk(url):
    u = url.lower()
    return any(j in u for j in JUNK_SUBSTRINGS)


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, indent=2))


def alive(url, timeout=8):
    """HEAD first; GET fallback. Many sites (Yahoo, MarketWatch, SEC, Tipranks) block HEAD."""
    try:
        r = subprocess.run(
            ["curl", "-fsLI", "-A", UA, "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 3,
        )
        if r.returncode == 0:
            return True
        r2 = subprocess.run(
            ["curl", "-fsL", "-A", UA, "--max-time", str(timeout), "-o", "/dev/null", url],
            capture_output=True, text=True, timeout=timeout + 3,
        )
        return r2.returncode == 0
    except Exception:
        return False


def search_topic(queries, sleep_between=2.5):
    from ddgs import DDGS
    candidates = []
    seen = set()
    with DDGS() as ddgs:
        for q in queries:
            try:
                for r in ddgs.text(q, max_results=6):
                    href = r.get("href", "")
                    if not href or href in seen or is_junk(href):
                        continue
                    seen.add(href)
                    candidates.append({
                        "title": r.get("title", "")[:200],
                        "href": href,
                        "body": (r.get("body", "") or "")[:200],
                    })
            except Exception as e:
                print(f"    ! query failed: {q[:60]} -> {e}", flush=True)
            time.sleep(sleep_between)
    for c in candidates:
        c["score"] = score(c["href"])
    return candidates


def pick_top(candidates, n=10):
    candidates.sort(key=lambda x: -x["score"])
    domain_count = {}
    picked = []
    for c in candidates:
        if len(picked) >= n + 3:
            break
        dom = urlparse(c["href"]).netloc.lower().replace("www.", "")
        cap = 3 if any(k in dom for k in ["arxiv.org", "github.com", "nasa.gov"]) else 1
        if domain_count.get(dom, 0) >= cap:
            continue
        domain_count[dom] = domain_count.get(dom, 0) + 1
        picked.append(c)

    final = []
    for c in picked:
        if len(final) >= n:
            break
        if alive(c["href"]):
            final.append(c)
        else:
            print(f"    ! dead URL: {c['href']}", flush=True)
    return final


def gapi(*args):
    cmd = ["python", GAPI_SCRIPT] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"gapi failed: {' '.join(args)}\nstderr: {r.stderr}\nstdout: {r.stdout}")
    return json.loads(r.stdout)


def find_or_create_folder(name, parent_id):
    q = (f"name = '{name}' and '{parent_id}' in parents "
         f"and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    results = gapi("drive", "search", q, "--raw-query", "--max", "5")
    if results:
        return results[0]["id"]
    created = gapi("drive", "create-folder", name, "--parent", parent_id)
    return created["id"]


AUDIENCE = {
    "investing": "Retail investors who already trade stocks but are new to the space sector. Comfortable with tickers, P/E, basic financials — not MBAs.",
    "careers": "Job seekers, career-switchers, and students considering aerospace. Mix of engineers and non-engineers.",
    "beginners": "Curious people who think space is cool but were lost by expert content. Adults who haven't thought about astronomy since school.",
    "tourism": "Travelers, bucket-listers, and astro-curious vacationers. Comfortable spending on memorable experiences.",
}


def write_prompt(topic, sources):  # noqa: ARG001 — kept for any out-of-tree caller
    """DEPRECATED: the two-section podcast/study-guide brief is no longer used.

    We now generate ONLY `video-prompt.txt` (single-narrator NotebookLM Video
    Overview brief) and reuse the resulting audio for the podcast distribution.
    Calling this function raises so accidental re-introduction is loud.
    """
    raise NotImplementedError(
        "prompt.txt generation is dropped. Use write_videoprompt() and emit "
        "only video-prompt.txt — the audio doubles as the podcast track."
    )


NICHE_FOOTERS = {
    "investing": 'Frame stocks as "things to watch," never "buys." Not financial advice.\n\n',
    "careers": "",
    "beginners": "",
    "tourism": "",
}


def write_videoprompt(topic):
    """NotebookLM Video Overview prompt — single faceless narrator, ~700-750 words,
    designed for mobile single-paste. Brand-locked boilerplate with per-topic header.

    This is the ONLY prompt we generate now. The old two-section `prompt.txt`
    (podcast/study-guide brief) has been dropped — we reuse the Video Overview
    audio for the podcast and don't need a separate brief.
    """
    audience = AUDIENCE.get(topic["niche"], "General audience curious about this topic.")
    skill_root = Path(os.path.expanduser("~/.hermes/skills/research/research-to-notebooklm"))
    tpl_path = skill_root / "templates" / "video-prompt.txt"
    if not tpl_path.exists():
        # Backward compat: accept the old un-hyphenated filename for one release
        legacy = skill_root / "templates" / "videoprompt.txt"
        if legacy.exists():
            tpl_path = legacy
        else:
            raise FileNotFoundError(
                f"Missing video-prompt template at {tpl_path}. "
                "Restore from skill or skip video-prompt generation."
            )
    tpl = tpl_path.read_text()
    return (tpl
            .replace("{TITLE}", topic["title"])
            .replace("{AUDIENCE}", audience)
            .replace("{PROMPT_FOCUS}", topic["prompt_focus"])
            .replace("{NICHE_FOOTER}", NICHE_FOOTERS.get(topic["niche"], "")))


INLINE_TEMPLATE = None  # legacy slot — `prompt.txt` is no longer generated; see write_prompt() docstring.


def process_topic(topic, manifest):
    key = f"topic_{topic['n']:02d}"
    state = manifest.get(key, {})
    if state.get("done"):
        print(f"  [skip] {topic['folder']} — already done", flush=True)
        return state

    print(f"\n>>> Topic {topic['n']:02d}: {topic['title']}", flush=True)
    local_dir = ROOT / slug(topic["folder"])
    local_dir.mkdir(parents=True, exist_ok=True)

    if "sources" not in state:
        print(f"  Searching ({len(topic['queries'])} queries)...", flush=True)
        candidates = search_topic(topic["queries"], sleep_between=2.5)
        print(f"  Got {len(candidates)} candidates", flush=True)
        sources = pick_top(candidates, n=10)
        print(f"  Picked {len(sources)} after dedupe + liveness", flush=True)
        state["sources"] = sources
        manifest[key] = state
        save_manifest(manifest)
    else:
        sources = state["sources"]
        print(f"  Reusing {len(sources)} cached sources", flush=True)

    (local_dir / "sources.txt").write_text("\n".join(s["href"] for s in sources) + "\n")
    (local_dir / "video-prompt.txt").write_text(write_videoprompt(topic))

    if "topic_folder_id" not in state:
        state["topic_folder_id"] = find_or_create_folder(topic["folder"], PARENT_FOLDER_ID)
        manifest[key] = state
        save_manifest(manifest)
    if "research_folder_id" not in state:
        state["research_folder_id"] = find_or_create_folder("research", state["topic_folder_id"])
        manifest[key] = state
        save_manifest(manifest)

    research_id = state["research_folder_id"]
    existing = gapi("drive", "search", f"'{research_id}' in parents and trashed = false",
                    "--raw-query", "--max", "20")
    # Clean up: also remove stale prompt.txt / videoprompt.txt from prior schema
    for f in existing:
        if f["name"] in ("sources.txt", "video-prompt.txt", "prompt.txt", "videoprompt.txt"):
            gapi("drive", "delete", f["id"])

    up1 = gapi("drive", "upload", str(local_dir / "sources.txt"), "--parent", research_id)
    up2 = gapi("drive", "upload", str(local_dir / "video-prompt.txt"), "--parent", research_id)
    state["sources_file_id"] = up1["id"]
    state["video_prompt_file_id"] = up2["id"]
    state["done"] = True
    manifest[key] = state
    save_manifest(manifest)
    print(f"  Uploaded: sources.txt + video-prompt.txt", flush=True)
    return state


def main(start=1, end=10**9):
    topics = json.loads(TOPICS_FILE.read_text())
    manifest = load_manifest()
    for t in topics:
        if not (start <= t["n"] <= end):
            continue
        try:
            process_topic(t, manifest)
        except Exception as e:
            print(f"  !!! topic {t['n']} failed: {e}", flush=True)
            manifest.setdefault(f"topic_{t['n']:02d}", {})["error"] = str(e)
            save_manifest(manifest)
        time.sleep(3)
    print("\n=== Done ===", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        main(int(args[0]), int(args[1]))
    else:
        main()
