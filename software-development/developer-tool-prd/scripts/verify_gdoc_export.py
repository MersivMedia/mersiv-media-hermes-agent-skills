#!/usr/bin/env python3
"""Export a Google Doc as plain text and check that given strings survived import.

md2gdoc's verified_chars ignores table cells, so table-heavy docs trigger a false
"doc much shorter than source" warning. This checks real content instead.

Usage:
  python3 verify_gdoc_export.py DOC_ID source.md "string from last section" "string inside a table" ...
Exit code 1 if any needle is missing.
"""
import os
import subprocess
import sys
import tempfile

GAPI = os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")),
                    "skills/productivity/google-workspace/scripts/google_api.py")


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    doc_id, src, needles = sys.argv[1], sys.argv[2], sys.argv[3:]
    out = os.path.join(tempfile.gettempdir(), f"gdoc_{doc_id}.txt")
    subprocess.run([sys.executable, GAPI, "drive", "download", doc_id,
                    "--export-mime", "text/plain", "--output", out],
                   check=True, capture_output=True)
    text = open(out, encoding="utf-8-sig").read()
    src_len = len(open(src, encoding="utf-8").read())
    print(f"export {len(text)} chars / source {src_len} chars ({100 * len(text) / max(src_len, 1):.0f}%)")
    missing = [n for n in needles if n not in text]
    for n in needles:
        print(("  ok      " if n not in missing else "  MISSING ") + n)
    if needles:
        i = text.find(needles[-1])
        if i >= 0:
            print("  sample:", repr(text[i:i + 240]))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
