# Public deployment hardening

Closing the three gaps `references/audience-identity-and-durability.md` §5 left
open — no CDN, no TLS, bounded Sybil resistance — plus two defects found while
closing them. This is the last layer before a screening faces strangers.

Everything measured against a running server.

---

## 1. Cacheability is a prerequisite, not an optimisation

Each viewer pulls 1–2 Mbps continuously. A hundred of them is 200 Mbps out of
one box that is *also* encoding video. A CDN fixes that only if the origin
declares what may be cached, and the segment route originally sent **no
`Cache-Control` at all** — so nothing could be cached and every byte came off
the origin.

Two rules, in opposite directions:

| Route | Header | Why |
|---|---|---|
| segments | `public, max-age=31536000, immutable` | a written segment never changes |
| playlists | `no-store, no-cache, must-revalidate` | rewritten on every publish |
| `/live`, `/token`, `/state` | never cached | live state |

**Never cache a playlist.** A cached manifest freezes a viewer at whatever the
stream looked like when they first connected, and presents to them as "it played
for a while and then stopped" — indistinguishable from the timestamp and
resync bugs, which makes it expensive to diagnose twice.

Add `Access-Control-Allow-Origin: *` to both so segments can be served from a
different hostname than the page.

With segments cacheable, origin egress becomes one fetch per segment per edge
rather than per viewer, and the machine's ceiling moves from bandwidth back to
encoding — which is where the scheduling work in
`references/scheduling-and-deadlines.md` already assumed it was.

Verify with headers, not intent:

```bash
curl -s -D - -o /dev/null http://host/segments/mid/seg_0000.ts | grep -i cache
curl -s -D - -o /dev/null http://host/stream/master.m3u8      | grep -i cache
```

---

## 2. Prefix independence is what makes a proxy possible

Absolute paths are a silent deployment blocker. Playlists emitting
`/segments/...` and a client fetching `/token` only work when the app is mounted
at the domain root, which rules out both a path-mounted reverse proxy and a
CDN-fronted subpath — and the failure appears at deploy time, not in any test.

Three changes, all cheap if done before the first deploy:

```python
# playlists: relative, resolved against the playlist's own URL
lines.append(f"{r.name}.m3u8")                        # master -> variant
lines.append(f"../segments/{rung.name}/seg_{i:04d}.ts")  # variant -> segment
```

```js
// client: derive everything from the page's own URL
const BASE = location.pathname.replace(/\/[^/]*$/, '/');
const SRC  = BASE + 'stream/master.m3u8';
await fetch(BASE + 'token');
ws = new WebSocket(`${proto}://${location.host}${BASE}live?token=${tok}`);
```

The WebSocket scheme comes from `location.protocol`, so terminating TLS upstream
automatically yields `wss://` with no config.

HLS resolves relative segment URIs against the manifest URL, so this costs
nothing and buys deployment freedom.

---

## 3. TLS via the proxy that is already running

Do not expose the app port. Plain HTTP is increasingly blocked on mobile, odd
ports are filtered on some networks, and the app has no business terminating
TLS. Check what already owns 80/443 before opening anything new.

```caddyfile
screening.example.com {
    reverse_proxy localhost:8137 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

`X-Forwarded-For` is load-bearing, not hygiene: the token rate limiter in §4
reads it, and without it **every viewer appears to come from `127.0.0.1` and
shares one bucket** — which converts a per-source cap into a global cap and
silently throttles the whole audience.

Path-mounted form, which works because of §2:

```caddyfile
example.com {
    handle_path /pipeline/* {
        reverse_proxy localhost:8137
    }
}
```

Pair it with a supervisor, or the journal's resume behaviour never gets used:

```ini
[Service]
ExecStart=/srv/pipeline/.venv/bin/python engine/server.py stories/x.json --port 8137
EnvironmentFile=/etc/pipeline/env     # 0600, service-owned, never in the repo
Restart=always
RestartSec=2
```

Confirm a restart *resumes* rather than restarting the story:

```bash
systemctl restart pipeline && journalctl -u pipeline -n 5
#   resumed: 20 segments, 3 decisions
#   resuming with 6 beats remaining
```

---

## 4. Make identity minting cost something

Signed tokens (see the neighbouring reference, §1) stop the *accidental*
duplicate — refresh, reconnect, second tab — which is the case that actually
corrupts a tally. But minting was free, so clearing storage in a loop still
produced unlimited ballots.

A per-source cap that **recycles rather than rejects**:

```python
def issue(self, ip: str) -> tuple[str, bool]:
    seen = self._issued.setdefault(ip, [])
    if len(seen) >= self.per_ip:
        return seen[0], False      # hand back the oldest identity
    tok = mint()
    seen.append(tok)
    return tok, True
```

Design choices worth copying:

- **Recycle, don't ban.** A lecture hall or a household behind one NAT is a
  legitimate crowd. The failure mode should be "you share a ballot with others
  on your router", never "you are locked out of the screening".
- **The recycled token must still verify.** It is a real identity, not a
  sentinel — test that explicitly.
- Keep the cap generous (8/source) and the client unaware: it receives a valid
  token either way.

Measured: 12 requests from one address yielded **8 distinct identities**, with
the `fresh` flag going `[T×8, F×4]`.

State the residual honestly — someone with many source addresses can still stuff
a ballot, and stopping that needs real accounts. That is a product decision.

---

## 5. Any path segment reaching the filesystem needs an allowlist

The segment route interpolated an unvalidated name straight into a path. Regex
plus an allowlist, not sanitisation:

```python
SEG_NAME   = re.compile(r"seg_\d{4}\.ts")
RUNG_NAMES = frozenset(r.name for r in LADDER)

if not SEG_NAME.fullmatch(name) or rung not in RUNG_NAMES:
    return Response(status_code=404)
```

Verify with the encoded form too — frameworks differ on when they decode:

```
mid/../../etc/passwd        -> 404
mid/..%2f..%2fetc%2fpasswd  -> 404
mid/seg_0000.ts.bak         -> 404
evil/seg_0000.ts            -> 404
```

---

## 6. Derived artifacts on disk carry the schema of whatever wrote them

The best bug in this session, and the one most likely to recur.

After changing playlists from absolute to relative URLs, the unit test passed
and **the running server still served absolute URLs**. Cause: a resumed
screening replayed its journal and reused the playlist *files left on disk by
the previous process* — files written by the previous build of the code.

```
stat playlist  ->  09:11:07
process start  ->  09:12:08     # the artifact predates the process serving it
```

The tell is a timestamp comparison, and it is worth reaching for whenever source
and live behaviour disagree.

> On resume, **regenerate every derived artifact from restored state.** Never
> trust a derived file on disk to match the current code, because its format is
> a function of the build that produced it. Replay the *source of truth* (the
> journal) and rewrite everything downstream of it.

```python
if self.resumed:
    for r in ladder.LADDER:
        ladder.write_variant(STREAM, r, self.screening.segments, False)
    ladder.write_master(STREAM)
```

This generalises past playlists to caches, manifests, indexes, thumbnails,
sitemaps — anything generated rather than authored. And it is a class of bug
component tests **cannot** catch: the test exercises the generator, while the
server serves the artifact. Only diffing the running server against the source
finds it.

---

## 7. Disk

Three ladder rungs at 5s per segment is ~3.3 MB per 5 seconds — roughly
**40 MB/min, 2.4 GB per hour** of screening.

Nothing prunes automatically, deliberately: deleting media a late joiner might
still request is a product decision, not a technical one. Either budget the disk
or write a reaper for segments well behind the playhead, and say which.

---

## 8. What remains true after all of this

- **One process, one screening.** The journal survives restarts and a CDN
  handles fan-out, but there is no horizontal scale. Two screenings is two
  processes.
- **No moderation, no auth, no admin surface.** Anyone with the URL watches and
  votes.
- **Sybil resistance is bounded** — §4.

Same principle as everywhere else in this skill: an acknowledged gap gets routed
to a human decision, an implied guarantee gets believed.
