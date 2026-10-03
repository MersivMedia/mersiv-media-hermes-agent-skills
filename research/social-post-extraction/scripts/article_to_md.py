#!/usr/bin/env python3
"""Rebuild an X long-form Article (fxtwitter JSON) as markdown, inlining code/prompt entities.

Usage: python3 article_to_md.py fx.json > article_full.md
Prints entity-type counts to stderr so you can check nothing was dropped.
"""
import json
import sys
from collections import Counter

PREFIX = {
    "header-one": "# ", "header-two": "## ", "header-three": "### ",
    "unordered-list-item": "- ", "ordered-list-item": "1. ", "blockquote": "> ",
}

d = json.load(open(sys.argv[1]))
t = d.get("tweet", d)
a = t.get("article")
if not a:
    print(t.get("text", ""))
    sys.exit(0)

em = {str(e["key"]): e["value"] for e in a["content"].get("entityMap", [])}
counts = Counter(v.get("type") for v in em.values())
out = [f"# {a.get('title', '')}", ""]
for b in a["content"]["blocks"]:
    if b["type"] == "atomic":
        for r in b.get("entityRanges", []):
            e = em.get(str(r["key"]), {})
            typ, data = e.get("type"), e.get("data", {})
            if typ == "MARKDOWN":
                out.append(data.get("markdown", ""))
            elif typ == "TWEET":
                out.append(f"[embedded tweet {data.get('tweetId')}]")
            elif typ == "DIVIDER":
                out.append("---")
            elif typ == "MEDIA":
                out.append("[media]")
            else:
                out.append(f"[{typ} {json.dumps(data)[:200]}]")
        continue
    out.append(PREFIX.get(b["type"], "") + b.get("text", ""))

text = "\n".join(out)
print(text)
print(f"article chars {len(text)}, blocks {len(a['content']['blocks'])}, entities {dict(counts)}", file=sys.stderr)
