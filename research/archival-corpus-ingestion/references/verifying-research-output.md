# Verifying Research Output Before You Ship It

Applies to any deliverable built from delegated or automated research: link
lists, tracklists, spec tables, source bibliographies, price comparisons.

---

## 1. A status code only means something with a negative control

Fetch every URL before shipping it:

```bash
while read u; do
  curl -sL -o /dev/null -w "  %{http_code} %{content_type}  $u\n" --max-time 20 \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0" "$u"
done < urls.txt
```

**Always pair it with a deliberately invalid URL on the same host:**

```bash
curl -s -o /dev/null -w "bogus:%{http_code} %{size_download}\n" \
  "https://host/track/999999999999"
curl -s -o /dev/null -w "real :%{http_code} %{size_download}\n" \
  "https://host/track/899151602"
```

Want `404` vs `200`. If the bogus URL also returns `200`, every `200` from that
host is worthless — you have verified nothing.

### The bot-wall signature

Some hosts serve a JavaScript shell to non-browser clients. The tell is
**identical `size_download` across unrelated paths**:

```
200 38382  /readingroom/document/<real-doc-id>
200 38382  /readingroom/collection/<name>
200 38382  /readingroom/sitemap.xml     ← same bytes = shell, not content
```

Three "successful" fetches, zero information. When this happens, say the data
is unverified and why — do not infer availability in either direction.

Bandcamp behaves the same way for scripted requests: `200` plus a bot-challenge
page regardless of whether the album exists. Verify such catalogue items through
a source that answers honestly (a public metadata API), and point *purchase*
links at the preferred store while being explicit that the store slug itself was
not machine-verified.

---

## 2. Cite per field, not per row

In a table-shaped deliverable, provenance belongs to individual **cells**. A row
can carry a verified URL while its numeric columns are invention.

| Track | BPM | Ref |
|---|---|---|
| Real Title | 140.15 | [ref](…) |
| Real Title | *unconfirmed* | [ref](…) |

Mark unconfirmed fields where the reader will look, and explain the marking in
the document preamble — the document outlives the chat. A blank field costs one
lookup; a confident wrong number costs the artifact's credibility.

**Never backfill because a value is "probably right."** Genre convention,
typical ranges, and what similar items usually measure are inference, not
sources. Label them as inference or leave them empty.

Also record *why* a field is missing when the reason is structural — e.g. "the
source database caps each artist page at ten alphabetically-sorted entries, so
well-known items are unreachable." That tells the reader whether more effort
would help.

---

## 3. Recovering a timed-out subagent

`status=timeout` with no summary reads like total loss. It usually is not —
children share the filesystem, so a child that spent ten minutes gathering data
has probably left it on disk.

Before re-dispatching and re-buying the work:

1. **Look for artifacts it wrote.** A research child killed mid-verification had
   already harvested a 273 KB dataset covering 22 sources; that file was on disk
   and directly usable.
2. **Read its live transcript** at the path in the completion message
   (`.../delegation/live/<deleg_id>/task-N.log`) to see what it confirmed.
3. **For children that *completed***, the parent summary is head/tail truncated.
   The **full** output is saved to a file whose path the completion message
   prints — parse that, not the transcript.

### Parsing gotcha

Do not extract JSON from the live transcript. It is a human-readable log:
long fields are elided with `…(+N chars)`, strings are escaped, and literal
control characters appear inline. Attempts to repair it fail in sequence —
`Invalid control character`, then `Unterminated string`. The saved summary file
is the clean copy:

```python
raw = open(summary_path, encoding='utf-8', errors='replace').read()
d = json.loads(raw[raw.find('{'):raw.rfind('}')+1])
```

### Prevention beats recovery

Scope each child to finish inside the wall-clock cap and say so explicitly:
*"return your verified results within N minutes with whatever you have confirmed
so far."* An exhaustive-search goal with no early-return instruction runs until
it is killed.

When the user adds a constraint mid-run, steer the child rather than restarting
it, and pair the new constraint with "then wrap up and return what you have."

---

## 4. A verifier that reports loss may be wrong about loss

Before reporting data loss from an automated verifier, confirm through a second
path that inspects the artifact itself.

Case in point: a markdown→Google-Docs converter warned that only 6,541 of 15,028
source characters landed. Exporting the finished document showed **12,009
characters with every section and all 28 entities intact** — the verifier could
not see inside tables, so on table-heavy documents its warning is a false alarm.

The general rule: a verifier measures what it measures. On a table-heavy,
image-heavy, or otherwise structured artifact, check the shipped object — export
it, grep the built bundle, fetch the live URL — before telling the user something
was lost.

Related false negative when grepping a **minified** bundle: object keys lose
their quotes, so searching `'"photo":"https'` reports 0 while `photo:` reports
16. Confirm any "MISS" by printing surrounding context before acting on it.
