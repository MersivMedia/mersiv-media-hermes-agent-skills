# Audience identity, durability, and adaptive delivery

The three constraints a shared-screening layer cannot go public without — plus
the liveness bug that closing them exposed. This is the follow-on to
`references/live-screening-layer.md` §7, which previously declared "no auth, no
persistence across restarts, no CDN" as an accepted milestone boundary. Two of
those three are now solved; the CDN one is still real.

Everything below was verified against a running server with real concurrent
WebSocket clients in `--demo` mode.

---

## 1. An object's `id()` is not an identity

The most dangerous defect in the whole live layer, because it looked correct,
passed every test, and quietly corrupted vote tallies.

Viewer identity was keyed on the websocket object:

```python
viewer_id = f"v{id(ws)}"        # WRONG
```

`id()` returns a memory address. CPython recycles addresses aggressively as soon
as an object is collected. Measured directly:

```python
class WS: pass
seen = []
for _ in range(2000):
    w = WS()                    # freed each iteration
    seen.append(id(w))
len(set(seen))                  # -> 3 distinct values out of 2000
```

Three consequences, in increasing severity:

1. Identity does not survive a page refresh — every reload is a new voter.
2. Nothing stops one person opening N tabs and casting N ballots.
3. **A reconnecting viewer can inherit a departed viewer's id and silently
   overwrite their ballot.** The tally is wrong and nothing reports an error.

### The test that missed it is the more useful lesson

The end-to-end vote test spawned five concurrent viewers and asserted the tally.
It passed. It could *never* have caught this, because it held every socket open
**simultaneously** — so no websocket object was ever collected and no address
was ever recycled.

> When the thing under test is a pooled or recycled resource — memory
> addresses, connection-pool slots, PIDs, ephemeral ports, reused buffers — a
> parallel fan-out test is structurally incapable of finding reuse bugs. The
> test must **close and reopen sequentially**. Fan-out tests concurrency;
> churn tests identity.

### The fix: signed opaque tokens

```python
def mint() -> str:
    vid = secrets.token_urlsafe(16)
    sig = hmac.new(_secret(), vid.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{vid}.{sig}"

def verify(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    vid, _, sig = token.rpartition(".")
    want = hmac.new(_secret(), vid.encode(), hashlib.sha256).hexdigest()[:24]
    # compare_digest: a plain == leaks timing information about the signature
    return vid if hmac.compare_digest(sig, want) else None
```

- Mint on first contact via a tiny `GET /token`; the client stores it in
  `localStorage` and passes it as a query param on the WebSocket URL.
- The HMAC secret lives **outside the repo**, 0600, generated on first run.
  Never ship a hardcoded default — that makes every deployment forgeable.
- If the secret is lost, all tokens stop validating and every viewer is
  re-minted. For an anonymous screening that is an acceptable failure mode and
  much better than a shared fallback key.
- **An absent or forged token gets a freshly minted identity, not a rejection.**
  A screening should never refuse an audience member over a cookie problem.

Verified over the wire — three connections, two identities:

```
tab1  (token A)   accepted=True
tab2  (token A)   accepted=True
phone (token B)   accepted=True
server tally = {'A': 2, 'B': 0}   total ballots = 2
```

### State the bound honestly

This is **not login**. A screening is anonymous; the token only has to count one
person once. Clearing storage or opening a private window earns a new identity.

Say that plainly in the docs rather than implying Sybil resistance you do not
have. What the token *does* fix is the accidental case — refresh, reconnect,
second tab — and that is what actually corrupts a live tally. Defeating a
determined ballot stuffer needs real accounts, which is a product decision, not
a code one.

---

## 2. Append-only journal, not a snapshot

For any log whose entries have **already been shown to an audience**, a crash
must not be able to rewrite history. The canon log is the product's memory: what
the room chose, when, and by what margin.

```python
def append(self, kind: str, **fields):
    rec = {"t": round(time.time(), 3), "kind": kind, **fields}
    self._fh.write(json.dumps(rec) + "\n")
    self._fh.flush()
    os.fsync(self._fh.fileno())     # a buffered write that never reached disk
    return rec                       # is indistinguishable from no journal
```

One JSON object per line, one line per state transition: `start`, `segment`,
`vote_open`, `vote`, `decision`. Replay rebuilds the screening on boot, then
appends.

Three details that matter more than the happy path:

- **A torn final line is expected, not corruption.** A hard kill mid-write
  leaves a partial JSON object. Skip it and keep the rest — the preceding
  records are still authoritative.
- **Skip journalled artifacts whose files are gone.** A playlist entry pointing
  at a deleted segment gives the player something it cannot fetch, which is
  worse than a shorter screening. Count and report the misses.
- **Store an index, not a path.** Journalling `seg_0003.ts` breaks when the
  delivery layout changes (e.g. adding a bitrate ladder moves segments into
  per-rung directories). Journal `index=3` and let the reader construct the
  current path.

### Resuming needs two corrections beyond replay

```python
# 1. rewind the clock, or the playhead jumps to the end of published media
self.screening.started_at = time.time() - sum(s.seconds for s in segments)

# 2. skip beats already decided, or the audience re-votes settled choices
decided = {c["beat"] for c in self.screening.canon}
beats = [b for b in beats if b["id"] not in decided]
```

Verified by killing the process mid-screening:

```
resumed: 20 segments, 3 decisions
resuming with 6 beats remaining
```

---

## 3. Adaptive bitrate ladder

A single rendition is fine on wifi and stalls on a train. Without a ladder the
only outcomes on a weak connection are buffering or nothing.

Measured per 5s clip, libx264 `veryfast`, from a 1536×672 master:

| rung | width | video | size | rate | encode |
|---|---|---|---|---|---|
| low | 640 | 800k | 0.62 MB | 1.0 Mbps | 1.6s |
| mid | 960 | 1400k | 1.01 MB | 1.6 Mbps | 2.1s |
| high | 1280 | 2400k | 1.70 MB | 2.7 Mbps | 3.0s |
| | | | | | **6.7s serial** |

The rungs are independent, so encode them in parallel and the wall cost
collapses to roughly the slowest (~3s) — which the existing ~20s buffer absorbs.

### Segment alignment is mandatory

Every rendition must be cut at the same instants with keyframes at the same
positions, or a mid-stream switch lands between keyframes and produces a glitch
or a stall. Encode each rung from the **same source clip** with identical GOP
settings and scene-cut detection **off**:

```
-g 48 -keyint_min 48 -sc_threshold 0
```

`-sc_threshold 0` is the non-obvious one: left enabled, the encoder places
keyframes at content-dependent positions, which differ per rung because each rung
sees different post-scale detail. Identical GOP settings alone are not enough.

### Declare PEAK bandwidth, and list lowest first

```python
@property
def bandwidth(self) -> int:
    v = int(self.v_bitrate.rstrip("k")) * 1000
    a = int(self.a_bitrate.rstrip("k")) * 1000
    return int((v + a) * 1.1)      # + container overhead
```

Players use `BANDWIDTH` to decide whether a rung is *safe*. Understating it
(e.g. declaring the average) makes them pick a rendition they cannot sustain.

```
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=950400,RESOLUTION=640x280,CODECS="avc1.4d401f,mp4a.40.2"
/stream/low.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1628000,RESOLUTION=960x420,CODECS="avc1.4d401f,mp4a.40.2"
/stream/mid.m3u8
```

Order the master playlist **lowest-first**: a client with no throughput history
starts on the first entry, and starting low then climbing reaches a picture
faster than starting high and stalling. Keep the old single-rendition path as an
alias (`index.m3u8` → the mid rung) so existing clients keep working.

---

## 4. CPU-bound work in an async server is a LIVENESS bug

The defect the ladder exposed, and the most generalisable item here.

Three ffmpeg encodes were called directly from the event loop:

```python
self._publish(clip, beat["id"])          # ~3s of subprocess work, blocking
```

Every HTTP request and every WebSocket state push froze for the full ~3s per
clip. The symptom was not "slow encoding" — it was `curl` on an unrelated
`/state` endpoint **timing out entirely**, and it was misread at first as a
network or firewall problem.

```python
await asyncio.to_thread(self._publish, clip, beat["id"])
```

Responses went from timing out to **3–17 ms** while encoding continued.

Generalisations worth carrying:

- Anything subprocess- or compute-heavy inside `async def` needs a thread or a
  process pool. `await` on a blocking call is not concurrency.
- **The symptom to recognise:** unrelated endpoints timing out *in lockstep with
  a background task*. If the server is healthy between tasks and dead during
  them, it is a blocked loop, not load.
- Mark the function so the constraint survives refactoring:

  ```python
  def _publish(self, src, beat, kind="shot"):
      """MUST be called via asyncio.to_thread: runs three ffmpeg encodes."""
  ```

- Same discipline as the seek-loop bug in `live-screening-layer.md` §3.4 — the
  careful-looking code in the hot path is where liveness dies.

---

## 5. What is still honestly missing

- **No CDN.** Segments are served directly by the app process. A real audience
  needs a CDN or at least a caching proxy in front of the segment route; the
  ladder makes that cheaper but does not replace it.
- **Single process.** The journal survives restarts, but there is no horizontal
  scale and no shared state between instances.
- **Bounded Sybil resistance** — see §1.

Say these plainly. The pattern throughout this skill holds: an acknowledged gap
gets routed to a human decision, while an implied guarantee gets believed.
