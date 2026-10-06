#!/usr/bin/env python3
"""Turn a grounded-citations `## Sources` block into markdown list items.

md2gdoc reflows consecutive lines into one paragraph, so the rendered
`[n] url — title` lines import into Google Docs as a single run-on blob.
This writes a COPY with each source line prefixed by "- ", leaving the
ledger-verified draft untouched.

Usage: sources_to_list.py draft.md upload.md
"""
import re
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding="utf-8").read()
    marker = "## Sources"
    if marker not in text:
        print(f"no '{marker}' heading in {src}; copied unchanged", file=sys.stderr)
        open(dst, "w", encoding="utf-8").write(text)
        return 1
    head, tail = text.split(marker, 1)
    tail = re.sub(r"(?m)^\[(\d+)\] ", r"- [\1] ", tail)
    open(dst, "w", encoding="utf-8").write(head + marker + tail)
    n = len(re.findall(r"(?m)^- \[\d+\] ", tail))
    print(f"wrote {dst} ({n} source lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
