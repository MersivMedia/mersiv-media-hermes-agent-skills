#!/usr/bin/env python3
"""Render a markdown deliverable to a styled, client-ready PDF.

Typography follows the user's stated preference: professional SANS-SERIF
(DejaVu Sans / Arial), never Georgia or any serif face. Body ~10pt, navy
headers, dark table headers with zebra rows, monospace preserved so ASCII
architecture diagrams survive.

Deps (often in the project venv, not system python):
    python3 -m venv .venv && ./.venv/bin/pip install -q markdown weasyprint

Usage:
    python3 md_to_pdf.py INPUT.md "OUTPUT.pdf" \
        --footer "Client - Document Title" \
        [--accent "#0b1d33"] [--body-size 9.7] [--mono-size 7.1] [--keep-html]

Always verify afterwards:
    python3 -c "import pypdf;r=pypdf.PdfReader('OUTPUT.pdf');print(len(r.pages));print(r.pages[0].extract_text()[:400])"
"""

import argparse
import pathlib
import sys

CSS_TEMPLATE = """
@page {{
  size: Letter;
  margin: 22mm 18mm 20mm 18mm;
  @bottom-center {{
    content: "{footer}  \\00b7  " counter(page);
    font-family: 'DejaVu Sans', Arial, sans-serif;
    font-size: 8pt; color: #9aa0a6;
  }}
}}
@page :first {{ @bottom-center {{ content: ""; }} }}

body {{
  font-family: 'DejaVu Sans', Arial, Helvetica, sans-serif;
  font-size: {body}pt; line-height: 1.5; color: #202124;
}}
h1 {{
  font-size: 20pt; color: {accent}; margin: 0 0 4pt 0;
  border-bottom: 2.5pt solid {accent}; padding-bottom: 6pt;
  page-break-after: avoid;
}}
h1 + h2 {{ margin-top: 10pt; }}
h2 {{
  font-size: 13.5pt; color: {accent}; margin: 20pt 0 6pt 0;
  padding-bottom: 3pt; border-bottom: 0.7pt solid #d3d8de;
  page-break-after: avoid;
}}
h3 {{ font-size: 10.8pt; color: #1a3a5c; margin: 14pt 0 4pt 0; page-break-after: avoid; }}
p {{ margin: 0 0 7pt 0; }}
ul, ol {{ margin: 0 0 8pt 0; padding-left: 16pt; }}
li {{ margin-bottom: 3pt; }}
strong {{ color: {accent}; }}
em {{ color: #3c4043; }}
hr {{ border: none; border-top: 0.7pt solid #d3d8de; margin: 18pt 0; }}

table {{
  width: 100%; border-collapse: collapse; margin: 8pt 0 12pt 0;
  font-size: 8.4pt; page-break-inside: auto;
}}
th {{
  background: {accent}; color: #ffffff; text-align: left;
  padding: 5pt 6pt; font-weight: bold; font-size: 8.3pt;
}}
td {{ padding: 5pt 6pt; border-bottom: 0.5pt solid #dfe3e8; vertical-align: top; }}
tr {{ page-break-inside: avoid; }}
tbody tr:nth-child(even) {{ background: #f6f8fa; }}

pre {{
  background: #f6f8fa; border: 0.6pt solid #d3d8de; border-left: 2.5pt solid {accent};
  padding: 8pt 10pt; font-family: 'DejaVu Sans Mono', monospace;
  font-size: {mono}pt; line-height: 1.35; white-space: pre;
  page-break-inside: avoid; margin: 8pt 0 12pt 0;
}}
code {{
  font-family: 'DejaVu Sans Mono', monospace; font-size: 8.4pt;
  background: #f1f3f4; padding: 0 2pt; border-radius: 2pt;
}}
pre code {{ background: none; padding: 0; font-size: {mono}pt; }}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--footer", default="Confidential")
    ap.add_argument("--accent", default="#0b1d33")
    ap.add_argument("--body-size", type=float, default=9.7)
    ap.add_argument("--mono-size", type=float, default=7.1)
    ap.add_argument("--keep-html", action="store_true")
    args = ap.parse_args()

    try:
        import markdown
        from weasyprint import HTML
    except ImportError as exc:
        print(
            f"missing dep ({exc}). Check the right interpreter first:\n"
            "  python3 -c \"import markdown, weasyprint, sys; print(sys.executable)\"\n"
            "then: pip install markdown weasyprint",
            file=sys.stderr,
        )
        return 1

    src = pathlib.Path(args.input).read_text()
    body = markdown.markdown(
        src, extensions=["tables", "fenced_code", "toc", "sane_lists"]
    )
    css = CSS_TEMPLATE.format(
        footer=args.footer.replace('"', "'"),
        accent=args.accent,
        body=args.body_size,
        mono=args.mono_size,
    )
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<style>{css}</style></head><body>{body}</body></html>"
    )

    out = pathlib.Path(args.output)
    tmp = out.with_suffix(".html")
    tmp.write_text(html)
    HTML(string=html).write_pdf(str(out))
    if not args.keep_html:
        tmp.unlink(missing_ok=True)
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
