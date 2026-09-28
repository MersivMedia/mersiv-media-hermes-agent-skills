#!/usr/bin/env python3
"""Convert a PRD markdown file into a docx_create.py JSON spec.

Part of the ai-opportunity-discovery skill. Handles the markdown subset the
PRD templates emit: ATX headings, paragraphs, bullet/numbered lists, GFM
pipe tables, images, blockquotes, fenced code (incl. mermaid), horizontal
rules, and inline **bold** / *italic* / `code`.

Usage:
  python3 md_to_docx_spec.py prd/client-prd.md --out build/client.spec.json \\
      --title "Acme Co — AI Opportunity Plan" \\
      --footer "Acme Co · Confidential" --toc --theme client

Then:
  python3 ~/.hermes/skills/productivity/docx/scripts/docx_create.py \\
      build/client.spec.json out/client-prd.docx

Themes: `client` (warm, wide margins, larger body) and `technical`
(denser, monospace-friendly code blocks). Both define these paragraph
styles, namespaced to avoid colliding with Word built-ins:
PRDCallout, PRDCode, PRDCaption, PRDSubtitle.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

THEMES = {
    "client": {
        "accent": "1F4E79",
        "muted": "6B7280",
        "body_font": "Calibri",
        "body_size": 11,
        "margins": {"top": 25, "bottom": 25, "left": 25, "right": 25},
        "table_style": "Light Grid Accent 1",
    },
    "technical": {
        "accent": "24506B",
        "muted": "6B7280",
        "body_font": "Calibri",
        "body_size": 10,
        "margins": {"top": 20, "bottom": 20, "left": 20, "right": 20},
        "table_style": "Light List Accent 1",
    },
}

INLINE_RE = re.compile(
    r"(\*\*\*.+?\*\*\*|\*\*.+?\*\*|__.+?__|(?<!\*)\*(?!\*).+?(?<!\*)\*(?!\*)"
    r"|_[^_]+_|`[^`]+`|\[[^\]]+\]\([^)]+\))"
)


def parse_runs(text: str) -> list:
    """Split inline markdown into docx run dicts."""
    runs = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        if m.start() > pos:
            runs.append({"text": text[pos:m.start()]})
        tok = m.group(0)
        if tok.startswith("***") and tok.endswith("***"):
            runs.append({"text": tok[3:-3], "bold": True, "italic": True})
        elif tok.startswith("**") and tok.endswith("**"):
            runs.append({"text": tok[2:-2], "bold": True})
        elif tok.startswith("__") and tok.endswith("__"):
            runs.append({"text": tok[2:-2], "bold": True})
        elif tok.startswith("`") and tok.endswith("`"):
            runs.append({"text": tok[1:-1], "italic": True})
        elif tok.startswith("["):
            label = tok[1:tok.index("]")]
            url = tok[tok.index("(") + 1:-1]
            runs.append({"text": label, "underline": True})
            runs.append({"text": f" ({url})"})
        else:
            runs.append({"text": tok.strip("*_"), "italic": True})
        pos = m.end()
    if pos < len(text):
        runs.append({"text": text[pos:]})
    return [r for r in runs if r["text"]] or [{"text": text}]


def plain(text: str) -> str:
    """Strip inline markdown — for table cells, which take plain strings."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"[*_`]", "", text).strip()


def split_row(line: str) -> list:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [plain(c) for c in line.split("|")]


def is_divider(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]*-[\s:|-]*\|?", line.strip())) and "-" in line


def convert(md: str, base_dir: str, theme: dict, skip_h1: bool = False) -> list:
    lines = md.split("\n")
    blocks: list = []
    i = 0
    seen_h1 = False

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line:
            i += 1
            continue

        # fenced code
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            if lang == "mermaid":
                blocks.append({"type": "paragraph", "style": "PRDCaption",
                               "text": "[diagram — see source markdown]"})
            for b in buf:
                blocks.append({"type": "paragraph", "style": "PRDCode",
                               "text": b or " "})
            continue

        # horizontal rule
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", line):
            blocks.append({"type": "paragraph", "text": ""})
            i += 1
            continue

        # image
        m = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if m:
            alt, src = m.group(1), m.group(2)
            path = src if os.path.isabs(src) else os.path.normpath(
                os.path.join(base_dir, src))
            if os.path.exists(path):
                blocks.append({"type": "image", "path": path, "width_mm": 155})
                if alt:
                    blocks.append({"type": "paragraph", "style": "PRDCaption",
                                   "text": alt})
            else:
                blocks.append({"type": "paragraph", "style": "PRDCaption",
                               "text": f"[missing image: {src}]"})
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            text = plain(m.group(2))
            if level == 1:
                if skip_h1 and not seen_h1:
                    seen_h1 = True
                    i += 1
                    continue
                seen_h1 = True
                if blocks:
                    blocks.append({"type": "page_break"})
            blocks.append({"type": "heading", "text": text,
                           "level": min(level, 9)})
            i += 1
            continue

        # table
        if line.startswith("|") and i + 1 < len(lines) and is_divider(lines[i + 1]):
            header = split_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                cells += [""] * (len(header) - len(cells))
                rows.append(cells[:len(header)])
                i += 1
            blocks.append({"type": "table", "header": header, "rows": rows,
                           "style": theme["table_style"], "header_bold": True})
            continue

        # blockquote
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append({"type": "paragraph", "style": "PRDCallout",
                           "text": plain(" ".join(x for x in buf if x))})
            continue

        # bullet list
        if re.match(r"^[-*+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(plain(re.sub(r"^\s*[-*+]\s+", "", lines[i])))
                i += 1
            blocks.append({"type": "bullet_list", "items": items})
            continue

        # numbered list
        if re.match(r"^\d+[.)]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                items.append(plain(re.sub(r"^\s*\d+[.)]\s+", "", lines[i])))
                i += 1
            blocks.append({"type": "numbered_list", "items": items})
            continue

        # paragraph (join soft-wrapped lines)
        buf = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", "|", ">", "```", "!["))
                    or re.match(r"^([-*+]\s|\d+[.)]\s)", nxt)
                    or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", nxt)):
                break
            buf.append(nxt)
            i += 1
        blocks.append({"type": "paragraph", "runs": parse_runs(" ".join(buf))})

    return blocks


def build_spec(args) -> dict:
    theme = THEMES[args.theme]
    with open(args.input, encoding="utf-8") as f:
        md = f.read()
    base_dir = os.path.dirname(os.path.abspath(args.input))

    blocks: list = []
    if args.title:
        blocks.append({"type": "heading", "text": args.title, "level": 1})
        if args.subtitle:
            blocks.append({"type": "paragraph", "style": "PRDSubtitle",
                           "text": args.subtitle})
        if args.toc:
            blocks.append({"type": "toc"})
        blocks.append({"type": "page_break"})

    blocks += convert(md, base_dir, theme, skip_h1=bool(args.title))

    return {
        "page": {"width_mm": 210, "height_mm": 297,
                 "margins_mm": theme["margins"]},
        "header": args.header or "",
        "footer": args.footer or "",
        "footer_page_numbers": True,
        "styles": [
            {"name": "PRDSubtitle", "base": "Normal", "font": theme["body_font"],
             "size_pt": 13, "italic": True, "color": theme["muted"]},
            {"name": "PRDCallout", "base": "Normal", "font": theme["body_font"],
             "size_pt": theme["body_size"], "italic": True,
             "color": theme["accent"]},
            {"name": "PRDCode", "base": "Normal", "font": "Consolas",
             "size_pt": 9, "color": "333333"},
            {"name": "PRDCaption", "base": "Normal", "font": theme["body_font"],
             "size_pt": 9, "italic": True, "color": theme["muted"]},
        ],
        "blocks": blocks,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="markdown PRD path")
    p.add_argument("--out", required=True, help="output spec.json path")
    p.add_argument("--title", default="", help="cover title")
    p.add_argument("--subtitle", default="", help="cover subtitle")
    p.add_argument("--header", default="", help="page header text")
    p.add_argument("--footer", default="", help="page footer text")
    p.add_argument("--toc", action="store_true", help="insert table of contents")
    p.add_argument("--theme", choices=sorted(THEMES), default="client")
    a = p.parse_args()

    if not os.path.exists(a.input):
        sys.exit(f"no such file: {a.input}")
    spec = build_spec(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    kinds: dict = {}
    for b in spec["blocks"]:
        kinds[b["type"]] = kinds.get(b["type"], 0) + 1
    print(json.dumps({"spec": a.out, "blocks": len(spec["blocks"]),
                      "by_type": kinds}, indent=2))


if __name__ == "__main__":
    main()
