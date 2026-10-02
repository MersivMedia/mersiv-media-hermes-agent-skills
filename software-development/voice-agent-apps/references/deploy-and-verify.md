# Deploy and verify on Vercel (verified Oct 2026)

How the first build (a personal language tutor) was provisioned, deployed and proven on production. Reuse the shape; swap names.

## Provision once (`.provision.sh link|env|blob|check`, gitignored)

1. **Link:** `vercel project add <name> --non-interactive` then `vercel link --yes --project <name> --non-interactive`.
2. **Secrets:** generate with `python3 -c 'import secrets;print(secrets.token_urlsafe(24))'` into `~/.hermes/data/<app>/` (chmod 700 dir, 600 files): learner_key, admin_password (word-word-word-NNN so it's phone-typable), auth_secret, cron_secret. Push with `printf '%s' "$v" | vercel env add NAME production` (repeat for preview). `vercel env rm NAME env --yes` first to make re-runs idempotent. Never echo values.
3. **Blob:** `vercel blob create-store <store> --access private --region sfo1 -e production -e preview --yes --non-interactive`. Connects the store and sets `BLOB_READ_WRITE_TOKEN`. It also writes `.env.local` (gitignored; leave it).
4. **SSO off:** `PATCH /v9/projects/<name>?teamId=…` `{"ssoProtection":null,"framework":"nextjs"}` or public URLs 302 to a Vercel login.

## Deploy

- `vercel deploy --prod --yes` (remote build). **Don't run `next build` locally on this ~1.9GB box.** It gets OOM-killed (exit 143). Typecheck with `npx tsc --noEmit -p .` and unit-test with vitest locally, then let Vercel build.
- A deploy takes ~1-2 min. Wrap it in `.deploy.sh` (SSO patch + deploy) so every redeploy is one bare command.

## Debugging production

- `vercel logs <domain> --since 5m` shows errors; add `--json` and grep the route when the text view truncates the message.
- Local scripts can't use pulled env for Blob: `vercel env pull` gives a VERCEL_OIDC_TOKEN that the store rejects for the "development" environment. Instead deploy a **temporary admin-only diagnostic route** (`/api/admin/diag`), call it via a login-then-fetch script, read the JSON, and delete the route when done.
- Measure before theorizing. The weak-ETag bug was only found by logging `get().etag` vs `head().etag` on the real docs. The first guess (instanceof failing in the bundle) was real but not the cause.

## Verification scripts

- E2E: the working example is `~/travel-language-tutor/scripts/e2e.mjs` (app-specific routes; copy and adapt). It checks with real cookies against production: wrong key sets no cookie; learner sees app; learner gets 404 on every admin path; chips per language; wrong/right admin password; dashboard HTML has the reset button and the learner HTML doesn't; a text session start returns a signed URL and lesson material; a real agent chat over the WebSocket triggers `teach_phrase`; events post back; memory persists; replaying tool ids doesn't duplicate; TTS caching (2nd call much faster, same bytes); admin session log shows messages, taught items and tool ids.
  - **Use a topic the learner hasn't started.** The agent correctly reviews known phrases instead of re-teaching them, so asserting `teach_phrase` on a familiar topic fails falsely.
- `scripts/reset-check.mjs` (in this skill; set BASE + SECRETS env): learner can't reset (404); reset without the typed RESET is refused; reset gives a new period; the learner home is now empty; the old period is archived and still viewable. It PERFORMS a real reset, so run it before the hand-off, never after.
- CDP screenshots (venv `~/.venvs/cdp`, chromium-1217 with `--use-fake-ui-for-media-stream --use-fake-device-for-media-stream`): iPhone 390x844 @2x for home/chat/phrasebook/voice, 1280 wide full-page for dashboard + session drawer + reset dialog. Look at every shot. It caught a horizontal overflow (fix: `grid-template-columns: minmax(0,1fr)` + `min-width:0` on flex children) and a placeholder that wrapped and showed a scrollbar.
- A fake mic proves the WebRTC voice path connects and the greeting plays, not real speech recognition. Tell the user that real-iPhone mic testing is still on them.

## Handing over credentials

Print links and passwords once from the secrets files with a tiny script (no argv, temp file deleted), and say where they're stored. The learner link is `/?key=<learner_key>`; the admin URL is `/admin/login`.
