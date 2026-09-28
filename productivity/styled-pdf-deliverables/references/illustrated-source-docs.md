# Illustrated Source Docs → Themed PDF

For "take my Google Doc / Word doc and make it a beautiful themed PDF, keep all
the text and pictures." The hard part is never the styling — it is getting the
images to land in the right section and not get cropped.

## 1. Pull the source with images intact

A Google Doc exported as `text/plain` loses every image. Export **HTML** instead;
images come back as base64 data URIs in document order.

```bash
GAPI="python3 ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"
$GAPI docs get DOC_ID > /tmp/doc.json          # clean body text
$GAPI drive download DOC_ID --export-mime text/html --output /tmp/doc.html
```

Split the two: use the `docs get` body text as the prose source (already
newline-clean), and the HTML purely to harvest images.

```python
import re, base64
html = open('/tmp/doc.html', encoding='utf-8').read()
imgs = re.findall(r'src="data:image/(\w+);base64,([^"]+)"', html)
for i, (ext, data) in enumerate(imgs):
    open(f'img/doc_{i}.{ext}', 'wb').write(base64.b64decode(data))
```

To see where they sit relative to headings, replace each data URI with a marker
(`IMG_0`, `IMG_1`, …), strip `<style>`, then walk the body regex-matching
markers and `<hN>` text. This gives an export-order map — a starting point, NOT
the answer. See §2.

## 2. Place images by their OWN title banner, not by export order

**This is the pitfall that cost two rounds of user correction.**

Infographic-style images frequently have a title banner rendered *into* the
image ("PHASE 5 — EDGE-AI DRONE SURVEILLANCE"). The doc's export order often
disagrees with those banners: authors move text around, images anchor to
whatever paragraph they were pasted near, and trailing images drift up a
section. Placing by export order silently produces a PDF where a Phase 7
graphic sits under the Phase 4 heading, and it *looks* plausible enough that
you will report success while it is wrong.

**Always OCR the top strip of every source image and place by what it says.**

```python
from rapidocr_onnxruntime import RapidOCR   # pip install --break-system-packages rapidocr-onnxruntime
from PIL import Image
import glob, os, re

ocr = RapidOCR()
files = sorted(glob.glob('img/doc_*'), key=lambda p: int(re.search(r'_(\d+)', p).group(1)))
for f in files:
    im = Image.open(f); w, h = im.size
    im.crop((0, 0, w, int(h * 0.16))).save('/tmp/_t.png')   # banner strip only
    res, _ = ocr('/tmp/_t.png')
    print(os.path.basename(f), '->', ' '.join(t[1] for t in (res or [])))
```

`rapidocr-onnxruntime` is pure pip (ONNX, no system `tesseract` binary, no
sudo) — the right choice when you cannot install OS packages. OCR the cropped
banner rather than the whole image: far less noise, and the title is what you
need.

Build an explicit `heading text -> [image files]` dict from the OCR output.
Images that OCR to empty (photos, not infographics) have no opinion — leave
those where the export order put them.

## 3. Render, then verify placement mechanically

Do not eyeball it. Map each drawn XObject back to its source file by byte
length and print it next to that page's headings:

```python
from pypdf import PdfReader
import re, os, glob
sig = {os.path.getsize(f): os.path.basename(f) for f in glob.glob('img/doc_*')}
r = PdfReader('out.pdf')
for i, p in enumerate(r.pages):
    d = p.get_contents().get_data().decode('latin-1')
    names = re.findall(r'/(i[0-9a-f]{32,})\s+Do', d)
    xo = (p.get('/Resources', {}).get('/XObject') or {}).get_object() or {}
    got = [sig.get(len(xo['/' + n].get_object()._data), '?') for n in names if '/' + n in xo]
    heads = [l for l in (p.extract_text() or '').split('\n')
             if l.isupper() and 'CLASSIFIED' not in l and len(l) > 6]
    print(f'p{i+1}: {got} | {heads[:2]}')
```

Every image should appear on the page whose heading its banner names.

## 4. Sizing — never crop

`object-fit: cover` with a fixed `max-height` slices the top off images and
decapitates exactly the title banners you just used for placement.

```css
figure img {
  max-width: 100%; max-height: 3.4in;
  width: auto; height: auto;
  object-fit: contain;                       /* never cover */
  border: 1px solid rgba(242,179,65,.45);
}
figure { page-break-inside: avoid; }
```

Tune `max-height` down (6.2in → 4.6in → 3.4in) until images stop landing alone
on otherwise-blank pages. Detect that case programmatically: a page with an
image draw and near-zero body text (ignoring the running footer) is an orphan.

## 5. Full-bleed cover pages

When the user says "the cover should just be the image," they mean **no overlay
at all** — no kicker, title, rule, subtitle, or bottom strip. Strip the markup,
do not merely restyle it.

```css
@page :first { margin: 0; @bottom-center { content: ""; } }
.cover { position: relative; width: 8.5in; height: 11in; page-break-after: always; }
.cover img { position: absolute; top: 0; left: 0; width: 8.5in; height: 11in;
             object-fit: contain; }
```

`contain` letterboxes onto the page background when the image aspect ratio
(e.g. 0.671) differs from Letter (0.773); `cover` fills but crops. Check the
ratio first and pick deliberately.

Verify: `r.pages[0].extract_text()` must be exactly `''`.

## 6. Build as a script, not a heredoc

Write `build.py` with `write_file` and run it. Themed PDFs go through several
correction rounds (placement, sizing, cover), and a file you can `sed`/patch
between runs beats re-pasting a giant heredoc — which also risks tripping shell
guards on long inline Python.

## Drive delivery

The `google_api.py` wrapper has no in-place file update: re-uploading creates a
*new* file with a *new* ID and link. On each revision, `drive delete <old_id>
--permanent` then upload, and give the user the fresh link. Warn them the URL
changes, or upload once at the end after the PDF is settled.
