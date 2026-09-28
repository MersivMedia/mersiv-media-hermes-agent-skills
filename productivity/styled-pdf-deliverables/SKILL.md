---
name: styled-pdf-deliverables
description: Markdown to a styled client-ready PDF deliverable.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [pdf, deliverables, consulting, weasyprint, typography]
    category: productivity
    related_skills: [pdf, docx, ai-opportunity-discovery, google-workspace]
---

# Styled PDF Deliverables Skill

Turns a long markdown document — an evaluation, assessment response, proposal,
architecture writeup, or research brief — into a single professionally typeset
PDF the user can send to a client. This is the HTML/CSS route (markdown →
styled HTML → WeasyPrint), which handles tables, ASCII diagrams, and page
furniture far better than reportlab specs.

Not for: fillable forms, merging/splitting, or manipulating an existing PDF —
use the `pdf` skill. Not for Word deliverables — use `docx`.

## When to Use

- "Give me all of this as a clean PDF"
- Consulting or candidate-assessment output that must look client-ready
- A multi-part document assembled from several turns of a conversation
- Any deliverable with wide comparison tables or a monospace architecture diagram
- "Turn my Google Doc into a beautiful themed PDF, keep all the text and images"
  → follow `references/illustrated-source-docs.md`

## Prerequisites

- `markdown` and `weasyprint` in a Python environment. On PEP 668 systems these
  usually live in a project venv, NOT system python — check which interpreter
  actually has them before assuming the import fails:
  ```bash
  python3 -c "import markdown, weasyprint, sys; print(sys.executable)"
  ```
  If absent: `python3 -m venv .venv && ./.venv/bin/pip install -q markdown weasyprint`
- `pypdf` for verification (`pip install pypdf`). A `weasyprint` binary on PATH is
  a convenience wrapper only; calling the library from Python is more controllable.

## How to Run

```bash
python3 ~/.hermes/skills/productivity/styled-pdf-deliverables/scripts/md_to_pdf.py \
    doc.md "Client Name - Document Title.pdf" \
    --footer "Client Name - Document Title"
```

Options: `--accent "#0b1d33"` (header/table colour), `--body-size 9.7`,
`--mono-size 7.1` (shrink for wide ASCII diagrams), `--keep-html` to debug styling.

**Script:** `scripts/md_to_pdf.py` — the full markdown → HTML → PDF renderer,
with the house stylesheet baked in.
**Reference:** `references/consulting-assessment-structure.md` — section order,
analytical moves, build-vs-buy table pattern, HITL framing, and risk ordering
for "evaluate this bottleneck and propose how you'd solve it" deliverables.
**Reference:** `references/illustrated-source-docs.md` — converting an existing
Google Doc / Word doc that contains images into a themed PDF: HTML export to
harvest base64 images, OCR-driven image placement, no-crop sizing, full-bleed
cover pages, and mechanical placement verification.

## Quick Reference

| Need | Move |
|---|---|
| Assemble multi-turn output | Write ONE markdown file first, with a Part I / Part II split and a contents list |
| Wide comparison table | Body 9.7pt, table 8.4pt; the CSS already handles it |
| ASCII architecture diagram | Fenced code block; drop `--mono-size` to 7.0–7.2 so it fits Letter width |
| Client-facing filename | `"<Client> - <Title> - <Firm>.pdf"` — spaces are fine, quote the path |
| Page count / spot check | `pypdf` extract on page 1 and the last page |

## Procedure

1. **Assemble the source markdown as one file.** When the deliverable spans
   several conversation turns, merge them into a single document with a header
   block (prepared-for / engagement / subject), a numbered contents list, and
   `# Part I` / `# Part II` divisions. Renumber sections continuously across
   parts — do not leave two independent `## 1.` headings.
2. **Normalise the prose for print.** Chat-native artefacts read badly on paper:
   convert em-dash asides that were fine in chat, expand "§4" style back-references
   into named sections, and make sure every quote attributed to a stakeholder is
   reproduced verbatim.
3. **Render** with `scripts/md_to_pdf.py`.
4. **Verify with `pypdf` before reporting success** (see Verification). Never claim
   the PDF is correct off the exit code alone.
5. **Clean up intermediates.** Remove the temporary `.md`/`.html` from the repo
   working directory unless the user asked to keep the source.
6. **Report** the absolute path, the page count, and a one-line summary of what is
   in the document. Offer one concrete improvement (e.g. redrawing an ASCII diagram
   as vector) rather than a list of options.

## Typography (user preference — do not override)

The user explicitly rejects serif faces (Georgia and similar) as hard to read.

- **Sans-serif always** — DejaVu Sans / Arial / Helvetica stack.
- Body ~9.7–11pt, line-height 1.5, ink `#202124`.
- Table headers dark with white text, zebra `#f6f8fa` rows, 8.4pt.
- Navy accent `#0b1d33` for headings and rules.
- Same palette as the user's Google Docs deliverables — a PDF and a Doc for the
  same engagement should look like siblings.

## Pitfalls

- **`import weasyprint` failing under system python does not mean it is missing.**
  Check `sys.executable`; the deps usually live in the project venv. Do not
  reinstall or declare the tool broken.
- **ASCII diagrams overflow Letter width silently.** WeasyPrint will not warn —
  it clips. Verify the diagram page by extracting its text with `pypdf` and
  confirming the right-hand edge characters survived.
- **`page-break-inside: avoid` on `tr`, not `table`.** Avoiding breaks on the whole
  table forces huge tables onto a fresh page and leaves half a page blank.
- **Suppress the footer on page 1** with `@page :first` or the cover looks like a
  numbered body page.
- **Unicode symbols (◆ ▲ ⚠ ①) need a font that has them.** DejaVu Sans does; a bare
  `Arial` stack on a minimal Linux box may not. Keep DejaVu first in the stack.
- **Quote the output path.** Client-facing filenames contain spaces, and an
  unquoted path silently writes two files.
- **Never place images by document export order alone.** Infographics often
  carry their own title banner ("PHASE 5 — …"), and the export order routinely
  disagrees with it, so graphics land under the wrong heading while still
  looking plausible. OCR the banner and place by what it says — see
  `references/illustrated-source-docs.md`.
- **`object-fit: cover` on images crops the top off.** That decapitates exactly
  the title banners the reader needs. Use `contain` with `width/height: auto`.
- **"Cover should just be the image" means remove the overlay markup**, not
  restyle it. Verify with `pages[0].extract_text() == ''`.
- **Re-uploading to Drive creates a new file ID and link.** `google_api.py` has
  no in-place update. Delete the old ID and re-upload on each revision, or wait
  and upload once the deliverable is final.
- **Long inline Python heredocs can trip shell guards.** For anything iterative,
  write `build.py` with `write_file` and run it — patchable between rounds.

## Verification

```bash
python3 -c "
import pypdf; r = pypdf.PdfReader('OUT.pdf')
print('PAGES:', len(r.pages))
print(r.pages[0].extract_text()[:400])
print('--- last ---'); print(r.pages[-1].extract_text()[:300])"
```

- [ ] Page count is plausible for the source length
- [ ] Page 1 shows the title block, not body text mid-sentence
- [ ] The last page ends on the intended closing section, not mid-table
- [ ] Any code-block diagram extracts intact (grep the page text for a distinctive
      right-edge token)
- [ ] If the source had images: every image is on the page whose heading its own
      title banner names (map XObjects → source files; see the illustrated-source
      -docs reference), and no image sits alone on an otherwise-blank page
- [ ] Intermediate `.md` / `.html` removed
- [ ] Output path reported as an absolute path
