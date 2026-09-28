# Dashboard tab for a Hermes plugin

How Jermes added a **Jermes** tab to `hermes dashboard` without core changes
(v0.9). Upstream doc: `website/docs/user-guide/features/extending-the-dashboard.md`
(read it first; the SDK list grows). Reference implementation in the Hermes
tree: `plugins/kanban/dashboard/`.

## Layout

```
<plugin repo>/dashboard/
├── manifest.json     # name, label, icon (Lucide name from the mapped list), tab.path, tab.position, entry, css, api
├── dist/index.js     # plain IIFE, no build step
├── dist/style.css    # only dashboard CSS vars (--color-card, --color-border, --color-primary, --color-destructive, --radius)
└── plugin_api.py     # FastAPI `router`, mounted at /api/plugins/<name>/ behind the dashboard login
```

`"tab": {"path": "/<name>", "position": "after:skills"}`. Icons outside the
mapped list silently become `Puzzle` (`Shield` is mapped).

## Front end rules

- Get everything from `window.__HERMES_PLUGIN_SDK__`: `SDK.React`,
  `SDK.hooks.*`, `SDK.components.{Card,CardHeader,CardTitle,CardContent,Badge,Button,...}`,
  `SDK.utils.timeAgo`. Never bundle React.
- All requests via `SDK.fetchJSON("/api/plugins/<name>/...")`; it injects the
  session token. No raw `fetch(` (a test asserts this, and it keeps the
  install scanner clean).
- Register with `window.__HERMES_PLUGINS__.register("<name>", Page)`.
- Dangerous switches (enforce) use `window.confirm` with the concrete effect
  for that feature, and the API also requires `confirm: true`, so a stray
  POST can't flip it.
- Offer only modes that do something per feature. For Jermes, `advise` acts
  only in skill_suggest / skill_overlap / memory_filter / loop_guard; on the
  others it is shadow run in the foreground (added latency, no effect). The
  status route returns a per-point `modes` list and the UI renders that list.

## Backend rules

- The API runs **inside the dashboard process**: import the plugin's own
  package via `sys.path.insert(0, <repo root>)`, fail soft, open SQLite
  read-only (`file:...?mode=ro`, short timeout), and run long jobs (a skills
  audit) on a daemon thread with a lock plus a polled status route. Refuse a
  second concurrent start with 409.
- Never return secrets: report key *presence* (env or the `.env` files Hermes
  loads), never the value; show only previews that already went through the
  plugin's redaction.
- Config writes: back up first, edit **one line** in place (keep comments
  and the other keys' original text), write to a temp file and `replace()`,
  then re-read with the plugin's own loader. A raw `yaml.safe_load` check
  failed on `mode: off` (YAML 1.1 reads it as `False`), so map `False` →
  `"off"` exactly as the loader does.
- Mode changes should reach running agents: add an mtime check (at most
  every 2 s) in the engine's `point_config()` that reloads only `points`
  when the file changed, and only for engines built from the file (not tests
  or batch tools with an explicit config dict).

## Tests

- Load `plugin_api.py` with `importlib.util.spec_from_file_location` and call
  route functions directly with `asyncio`. Unset any `JERMES_HOME`-style env
  the suite's autouse fixture sets, or data lands in the wrong dir.
- `Store.log()` stamps `time.time()`, so tests needing old rows must UPDATE
  `ts` afterwards; otherwise time-window and per-day cost tests pass for the
  wrong reason (the first browser shot showed all spend in one bar).
- `fastapi` is not in the plugin's own venv: `pytest.importorskip("fastapi")`
  locally, and install an exact-pinned fastapi in CI so the tests run there.

## Browser check (before telling the user it works)

1. Temp home: copy the plugin into `/tmp/<x>/plugins/<name>` (not the real
   `~/.hermes`), `plugins: {enabled: [<name>]}`, seed a decisions DB.
2. `HERMES_HOME=/tmp/<x> ~/hermes-agent/.venv/bin/python -m hermes_cli.main dashboard --host 127.0.0.1 --port 9131 --no-open --skip-build`
   in the background; wait for `HERMES_DASHBOARD_READY`.
3. Headless Chromium (`--remote-debugging-port`, `--remote-allow-origins=*`),
   raw CDP via websocket-client: navigate to `/<name>`, assert the page root
   and cards exist, no error elements, click a switch, confirm the config
   file changed. Screenshot at 1400 px and 390 px (phone) and inspect.
4. For `window.confirm`, listen for `Page.javascriptDialogOpening` and answer
   with `Page.handleJavaScriptDialog(accept=...)`. Trigger the click via
   `setTimeout(() => b.click(), 0)` so `Runtime.evaluate` returns before the
   dialog blocks. Test **dismiss → config byte-identical** and
   **accept → exactly one line changed**.
5. The dashboard caches the plugin list and mounted API routes at startup.
   After changing `plugin_api.py`, restart the temp dashboard; a stale
   process served the old route logic and the enforce test failed for that
   reason alone.

## Deploying to the user

The user's dashboard process must be restarted once to mount the new tab
and routes (`systemctl restart hermes-dashboard` for a service install). It
signs them out, so explain that and let the user decide. When the user
asks you to do it, run `sudo -n systemctl restart hermes-dashboard` (only
if passwordless sudo exists; it needs Hermes' service-restart approval).
Keep the command short, with no long `sleep`/journal chain, because the
restart can end the calling turn. Verify afterwards in a separate call:
`systemctl is-active`, the new `ActiveEnterTimestamp`, root returns 302
(login), `/api/plugins/<name>/status` returns 401 (mounted and login-gated),
and `_get_dashboard_plugins(force_rescan=True)` lists the tab. The live
dashboard sits behind a login; do not scrape or bypass it. The final visual
check is theirs.

Once the tab exists, users flip modes themselves. Watch for them promoting
everything at once ("I turned everything on to enforce"), and answer with a
live-log readiness check per point, not congratulations (see
`decision-point-scoring.md`, "Live shadow beats every offline set").
