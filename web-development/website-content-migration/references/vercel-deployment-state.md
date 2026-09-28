# Vercel deployment-state failures

A class of Vercel problems that have nothing to do with your code. The build
succeeds, the CLI may hang without printing an error, and the deployment never
becomes usable. Diagnose through the API, not the build log.

> There is also a user-owned `AI Tool Deployment Troubleshooting & Recovery`
> skill covering *build* failures (React vs static architecture, npm "Invalid
> Version", runtime config). This file covers the orthogonal case — the build
> was fine and the deployment is still not serving.

## Always check state before debugging anything

```bash
set -a && . /path/to/.env && set +a
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v6/deployments?projectId=$PRJ&limit=4" -o /tmp/d.json
python3 -c "
import json,time
for d in json.load(open('/tmp/d.json'))['deployments']:
    age=int((time.time()*1000-d['created'])/1000)
    print(f\"{d['state']:<10} {age:>5}s ago  {d['url']}\")"
```

`READY` means live. `BLOCKED` means Vercel accepted the upload and then refused
to serve it.

## `BLOCKED` → read `seatBlock`

The v6 list endpoint will not say why, and `/v3/deployments/$ID/events` returns
zero events. The reason lives on the v13 single-deployment object, in a field
that is easy to miss:

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v13/deployments/$DEPLOY_ID" -o /tmp/dd.json
python3 -c "
import json; d=json.load(open('/tmp/dd.json'))
print('state:', d.get('readyState'))
print('seatBlock:', d.get('seatBlock'))
print('errorLink:', d.get('errorLink'))
print('block/error keys:', [k for k in d if 'block' in k.lower() or 'error' in k.lower()])"
```

Two observed block codes. **They look alike and have completely different
fixes**, so read `blockCode` rather than pattern-matching on `BLOCKED`:

```
seatBlock: {"blockCode": "COMMIT_AUTHOR_REQUIRED"}
seatBlock: {"blockCode": "TEAM_ACCESS_REQUIRED", "isVerified": false}
errorLink: https://vercel.com/docs/deployments/troubleshoot-project-collaboration#team-configuration
```

### `COMMIT_AUTHOR_REQUIRED` — the one that hits agents

**This is almost always the real cause when an agent built the repo.** Vercel
refuses to deploy any commit whose **author** is not a member of the owning
team. It is a supply-chain guard: an unrecognised identity must not be able to
ship to a production domain.

Agents commit under synthetic identities, so this fires by default:

```bash
git log -2 --format='%h %an <%ae>'
#   d028ec4  agent <agent@local>        <-- will be BLOCKED, every time
```

**Fix — set the identity to the Vercel account email before the first commit:**

```bash
# The email Vercel knows you by:
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" https://api.vercel.com/v2/user |
  python3 -c "import json,sys;print(json.load(sys.stdin)['user']['email'])"

cd repo
git config user.name  "<GitHub account name>"
git config user.email "<that Vercel account email>"
```

Already have bad commits? **Do not rewrite history** — `filter-branch` plus a
force-push is destructive and will (correctly) be blocked when a user must
approve it. Vercel only checks the commit **being deployed**, so a single new
correctly-authored commit on top is enough:

```bash
git config user.email "<vercel account email>"
git commit -m "…"            # any real change, e.g. a README line
git push origin main         # auto-deploy fires -> READY
```

Verified: `BLOCKED` → `READY` in under a minute with no other change.

### `TEAM_ACCESS_REQUIRED`

The token's account is not a verified seat on the team owning the project. The
first deploy often succeeds because it *creates* the project; later ones block.
Remedy is user-side — verify the team seat, or issue a token scoped to the
personal account.

Caution learned the hard way: this code also appears when the underlying
problem is actually the commit author (the CLI path reports the seat variant).
**Check the git author before asking the user for a new token.** An entire
round-trip was wasted requesting fresh credentials for a token that was valid
the whole time.

### Both codes

Do not attempt to fix either by editing `vercel.json`, changing the build
command, or retrying with `--archive=tgz`. These are authorization states and
retries only produce more `BLOCKED` deployments. **Check `seatBlock` before the
second retry**, not after the fourth.

Rule out the cheap lookalikes first:

```bash
# Rate limit? (hobby cap is 100/day) — count deployments in the last 24h
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v6/deployments?limit=100&since=$(( ($(date +%s)-86400) * 1000 ))"

# Billing / account block?
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" https://api.vercel.com/v2/user
#   -> user.blocked, user.softBlock, billing.plan, billing.status
```

In the observed case: 3 deployments in 24h and `plan: hobby, status: active`,
so neither was the cause — which is exactly what made `seatBlock` the answer.

## Preview URL returns 302 → `ssoProtection`

A new project can default to Deployment Protection, so the `*.vercel.app` URL
redirects to a login page and whoever you send the link to sees nothing.
`curl` shows `HTTP 302` and a 15-byte `Redirecting...` body.

```bash
# Inspect
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/$PROJECT_NAME" -o /tmp/p.json
python3 -c "
import json; d=json.load(open('/tmp/p.json'))
print('ssoProtection:', d.get('ssoProtection'))
print('passwordProtection:', d.get('passwordProtection'))"
# -> ssoProtection: {'deploymentType': 'all_except_custom_domains'}

# Disable so the link is publicly viewable (VERIFIED: 302 -> 200)
curl -s -X PATCH -H "Authorization: Bearer $VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ssoProtection":null}' \
  "https://api.vercel.com/v9/projects/$PROJECT_NAME"
```

This changes a setting on the user's account. **Say so in your reply** and
offer to re-enable it.

## Git auto-deploy: confirm the push actually happened

`gh repo create --push` links the repo, so every later commit to the production
branch should auto-deploy. When the live site does not change, verify the push
**before** suspecting the integration:

```bash
git status -sb | head -1          # "## main...origin/main [ahead 1]" = NOT pushed
git rev-parse --short HEAD origin/main
```

A real failure from this session: a single chained command ran
`git commit && vercel deploy` with **no `git push`**. The commit existed only
locally, the user was told the work was "pushed to GitHub", and the obvious
question — *wouldn't it auto-deploy?* — could not be answered until the push
was found missing. Never report "pushed" without checking `origin/main` moved.

Confirm the integration exists at all:

```bash
curl -s -H "Authorization: Bearer $VERCEL_TOKEN" \
  "https://api.vercel.com/v9/projects/$PROJECT_ID" |
  python3 -c "import json,sys;print(json.load(sys.stdin).get('link') or 'NONE')"
# -> {"type":"github","repo":"...","org":"...","productionBranch":"main"}
```

With `link` present, `git push` is the whole deploy workflow — no CLI needed.
Deployments then report `source: git` instead of `source: cli`.

## CLI hygiene

- `vercel deploy` can exceed a 600s foreground cap. Run it in the background
  with completion notification rather than burning repeated wait windows.
- After `npm i -g vercel` the binary may not be on `PATH` in the current shell:
  `export PATH="$(npm config get prefix)/bin:$PATH"`.
  (`npm bin -g` was removed in npm 9+ and errors with "Unknown command".)
- The CLI can hang silently while the deployment is already `BLOCKED`
  server-side. The API is the source of truth — kill the CLI and query it.
- Verify the token before building anything:
  ```bash
  curl -s -H "Authorization: Bearer $VERCEL_TOKEN" https://api.vercel.com/v2/user
  ```
  `user.username` confirms both validity and which scope you are operating in.

## Project scaffolding note

`npm create vite@latest .` and `npx create-vite@latest .` both refuse a
non-empty directory and exit with "Operation cancelled". If content was staged
first (e.g. an extraction cache in `data/`), write `package.json`,
`vite.config.ts`, `tsconfig.json` and `index.html` directly instead of fighting
the scaffolder.
