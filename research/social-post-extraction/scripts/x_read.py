#!/usr/bin/env python3
"""x_read.py - read an X (Twitter) post or long-form X Article as Markdown. No login, no API key.

Source: the public fxtwitter API (api.fxtwitter.com/<user>/status/<id>).
X Articles arrive as a Draft.js document (blocks + entityMap). Code blocks, embedded tweets, images
and dividers live in the entityMap, NOT in the block text, so naive extraction loses most of a
technical article. This script rebuilds the full document in reading order.

Usage:
  x_read.py URL_OR_ID [--out DIR] [--embeds] [--thread] [--json]
    --out DIR   write DIR/<id>.md + DIR/<id>.json (raw API reply) + DIR/<id>.links.txt
    --embeds    also fetch each embedded/quoted tweet and inline its author + text (1 call each)
    --thread    follow the author's self-replies upward (replying_to_status chain), oldest first
    --json      print the raw fxtwitter JSON instead of Markdown
Exit codes: 0 ok, 2 bad input, 3 not found / private / deleted, 4 network/API failure.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
API = "https://api.fxtwitter.com"
SYND = "https://cdn.syndication.twimg.com/tweet-result?id={id}&token=a"
ID_RE = re.compile(r"(?:status(?:es)?|i/web/status)/(\d{1,25})|^(\d{1,25})$")
USER_RE = re.compile(r"(?:x|twitter|fxtwitter|fixupx|vxtwitter|nitter\.[a-z.]+)\.com/([A-Za-z0-9_]{1,15})/status")
CODE_HOSTS = ("github.com", "gitlab.com", "huggingface.co", "codeberg.org", "pypi.org", "npmjs.com")


class Fail(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code


def get_json(url, tries=3):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise Fail(f"HTTP {e.code} for {url}", 3)
            last = e
            time.sleep(1.5 * (k + 1))
            continue
        except Exception as e:  # network
            last = e
            time.sleep(1.5 * (k + 1))
            continue
        try:
            return json.loads(body)
        except ValueError:
            # 200 with an empty/HTML body = the post doesn't exist, is private or was deleted. Retrying won't help.
            raise Fail(f"no JSON from {url} (post missing, private or deleted?): {body[:80]!r}", 3)
    raise Fail(f"failed after {tries} tries: {url}: {last}", 4)


def parse_target(s):
    s = s.strip()
    m = ID_RE.search(s)
    if not m:
        raise Fail(f"no status id in {s!r}", 2)
    tid = m.group(1) or m.group(2)
    u = USER_RE.search(s)
    return (u.group(1) if u else "i"), tid


def fetch(user, tid):
    """fxtwitter first; on failure fall back to X's syndication endpoint (plain tweets only, no articles)."""
    try:
        d = get_json(f"{API}/{user}/status/{tid}")
        if d.get("code") == 200 and d.get("tweet"):
            return d["tweet"], "fxtwitter"
        raise Fail(f"fxtwitter code {d.get('code')}: {d.get('message')}", 3)
    except Fail as e:
        try:
            s = get_json(SYND.format(id=tid))
        except Fail:
            raise e
        if not s.get("text"):
            raise e
        return {"id": tid, "url": f"https://x.com/{s.get('user', {}).get('screen_name', 'i')}/status/{tid}",
                "text": s.get("text", ""), "created_at": s.get("created_at"),
                "author": {"name": s.get("user", {}).get("name"), "screen_name": s.get("user", {}).get("screen_name")},
                "likes": s.get("favorite_count"), "_partial": "syndication fallback: no article body, no counts beyond likes"}, "syndication"


# ---------------------------------------------------------------- rendering

PREFIX = {"header-one": "# ", "header-two": "## ", "header-three": "### ", "unordered-list-item": "- ",
          "ordered-list-item": "1. ", "blockquote": "> "}


def inline_links(block, ents):
    """Apply LINK entity ranges inside a text block as [text](url). Offsets are UTF-16 in Draft.js; for BMP text
    they equal Python indices, so astral characters (emoji) can shift a link by one: the URL list keeps it exact."""
    text = block.get("text", "")
    rngs = sorted(block.get("entityRanges", []), key=lambda r: r["offset"], reverse=True)
    for r in rngs:
        e = ents.get(str(r["key"]), {})
        if e.get("type") != "LINK":
            continue
        url = e.get("data", {}).get("url", "")
        a, b = r["offset"], r["offset"] + r["length"]
        seg = text[a:b]
        if url and seg and seg != url:
            text = text[:a] + f"[{seg}]({url})" + text[b:]
    return text


def media_lookup(article):
    m = {}
    for it in (article.get("media_entities") or []):
        info = it.get("media_info", {})
        url = info.get("original_img_url")
        if not url:  # video/gif: best variant
            vs = [v for v in info.get("variants", []) if v.get("content_type") == "video/mp4"]
            url = max(vs, key=lambda v: v.get("bit_rate", 0))["url"] if vs else None
        m[str(it.get("media_id"))] = url
    return m


def article_md(a, embeds):
    ents = {str(e["key"]): e["value"] for e in a["content"].get("entityMap", [])}
    med = media_lookup(a)
    out = [f"# {a.get('title', '(untitled article)')}", ""]
    cover = (a.get("cover_media") or {}).get("media_info", {}).get("original_img_url")
    if cover:
        out += [f"![cover]({cover})", ""]
    counts = {}
    for b in a["content"]["blocks"]:
        ty = b.get("type")
        counts[ty] = counts.get(ty, 0) + 1
        if ty == "atomic":
            for r in b.get("entityRanges", []):
                e = ents.get(str(r["key"]), {})
                t, d = e.get("type"), e.get("data", {})
                if t == "MARKDOWN":
                    out += [d.get("markdown", "").rstrip(), ""]
                elif t == "DIVIDER":
                    out += ["---", ""]
                elif t == "TWEET":
                    tid = d.get("tweetId")
                    out += [embeds.get(tid) or f"> [embedded post](https://x.com/i/status/{tid})", ""]
                elif t == "MEDIA":
                    for mi in d.get("mediaItems", []):
                        url = med.get(str(mi.get("mediaId")))
                        out += [f"![image]({url})" if url else f"[media {mi.get('mediaId')} not in media_entities]", ""]
                else:
                    out += [f"[{t} entity: {json.dumps(d)[:300]}]", ""]
            continue
        line = PREFIX.get(ty, "") + inline_links(b, ents)
        if ty in ("unordered-list-item", "ordered-list-item"):
            out.append(line)  # lists stay tight
        else:
            out += [line, ""]
    return "\n".join(out).strip() + "\n", counts, ents


def collect_links(md, tweet):
    urls = set(re.findall(r"https?://[^\s)\]>\"']+", md))
    # bare domains in prose ("github.com/owner/repo", common in X Articles) have no scheme: add them too
    for m in re.finditer(r"(?<![/\w.@])((?:www\.)?(?:%s)/[\w.\-]+(?:/[\w.\-]+)?)" % "|".join(re.escape(h) for h in CODE_HOSTS), md):
        urls.add("https://" + m.group(1))
    for m in (tweet.get("media") or {}).get("all", []) or []:
        if m.get("url"):
            urls.add(m["url"])
    card = tweet.get("twitter_card") or {}
    if isinstance(card, dict) and card.get("url"):
        urls.add(card["url"])
    clean = sorted(u.rstrip(".,;:") for u in urls)
    code = [u for u in clean if any(h in u for h in CODE_HOSTS)]
    return clean, code


def tweet_header(t, source):
    au = t.get("author") or {}
    stats = " · ".join(f"{k} {t[k]}" for k in ("views", "likes", "retweets", "replies", "bookmarks") if t.get(k) is not None)
    lines = [f"**{au.get('name', '?')}** (@{au.get('screen_name', '?')}) · {t.get('created_at', '?')}",
             f"{t.get('url', '')}", f"{stats}  (via {source}, read {time.strftime('%Y-%m-%d')})"]
    if t.get("_partial"):
        lines.append(f"PARTIAL: {t['_partial']}")
    if t.get("community_note"):
        lines.append(f"Community note: {json.dumps(t['community_note'])[:400]}")
    return "\n".join(lines)


def plain_md(t):
    out = [t.get("raw_text", {}).get("text") if isinstance(t.get("raw_text"), dict) else None]
    out = [out[0] or t.get("text", "")]
    for m in (t.get("media") or {}).get("all", []) or []:
        kind = m.get("type", "media")
        out.append(f"![{kind}]({m.get('url')})" if kind == "photo" else f"[{kind}: {m.get('url')}]")
    q = t.get("quote")
    if q:
        out += ["", f"> Quoting @{(q.get('author') or {}).get('screen_name', '?')}: " + (q.get("text") or "").replace("\n", "\n> "),
                f"> {q.get('url', '')}"]
    return "\n\n".join(x for x in out if x)


def embed_text(tid):
    try:
        t, _ = fetch("i", tid)
    except Fail as e:
        return f"> [embedded post {tid}: unavailable ({e})](https://x.com/i/status/{tid})"
    au = (t.get("author") or {}).get("screen_name", "?")
    body = (t.get("text") or "").replace("\n", "\n> ")
    vids = [m.get("url") for m in (t.get("media") or {}).get("all", []) or [] if m.get("type") in ("video", "gif")]
    extra = f"\n> media: {', '.join(vids)}" if vids else ""
    return f"> **@{au}** ({t.get('created_at', '?')}): {body}{extra}\n> {t.get('url', f'https://x.com/i/status/{tid}')}"


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    flags = {a for a in argv if a in ("--embeds", "--thread", "--json")}
    out_dir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else None
    target = next(a for a in argv if not a.startswith("--") and (out_dir is None or a != str(out_dir)))
    user, tid = parse_target(target)
    t, source = fetch(user, tid)
    if "--json" in flags:
        print(json.dumps(t, indent=1))
        return 0
    chain = [t]
    if "--thread" in flags:  # walk up the author's own replies
        cur = t
        while cur.get("replying_to_status") and (cur.get("replying_to") or "").lower() == (cur.get("author") or {}).get("screen_name", "").lower():
            try:
                cur, _ = fetch(cur["replying_to"], cur["replying_to_status"])
            except Fail:
                break
            chain.insert(0, cur)
    parts, stats = [tweet_header(t, source), ""], None
    a = t.get("article")
    if a:
        tids = [e["value"]["data"].get("tweetId") for e in a["content"].get("entityMap", []) if e["value"].get("type") == "TWEET"]
        embeds = {x: embed_text(x) for x in tids} if "--embeds" in flags else {}
        body, counts, ents = article_md(a, embeds)
        types = {}
        for e in ents.values():
            types[e.get("type")] = types.get(e.get("type"), 0) + 1
        stats = f"article: {len(a['content']['blocks'])} blocks {counts}; entities {types}"
        parts.append(body)
    else:
        for i, c in enumerate(chain):
            if len(chain) > 1:
                parts.append(f"### {i + 1}/{len(chain)}  {c.get('url', '')}")
            parts += [plain_md(c), ""]
    md = "\n".join(parts).rstrip() + "\n"
    links, code = collect_links(md, t)
    md += "\n## Links found\n" + "\n".join(f"- {u}" for u in links) + "\n" if links else ""
    if code:
        md += "\n## Code / package links\n" + "\n".join(f"- {u}" for u in code) + "\n"
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{tid}.md").write_text(md)
        (out_dir / f"{tid}.json").write_text(json.dumps(t, indent=1))
        (out_dir / f"{tid}.links.txt").write_text("\n".join(links) + "\n")
        print(f"wrote {out_dir / (tid + '.md')} ({len(md)} chars)" + (f"; {stats}" if stats else ""))
        print(f"links: {len(links)} (code/package: {len(code)})" + ("".join(f"\n  {u}" for u in code)))
    else:
        sys.stdout.write(md)
        if stats:
            print(f"\n<!-- {stats} -->")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Fail as e:
        print(f"x_read: {e}", file=sys.stderr)
        sys.exit(e.code)
    except BrokenPipeError:  # piped into head
        sys.stderr.close()
        sys.exit(0)
