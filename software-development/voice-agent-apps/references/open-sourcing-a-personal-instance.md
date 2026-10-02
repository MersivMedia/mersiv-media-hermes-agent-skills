# Open-sourcing a personal instance (verified Oct 2026)

The first build (a personal language tutor) became the public repo
`MersivMedia/elevenlabs-agentic-language-tutor` while the personal live app kept
running unchanged. The approach is **genericize in place**: one checkout serves as
both the public repo and the private deployment. No staged copy is needed, because
the personal values move out of the code and into env vars.

## Steps

1. **Audit.** Grep the whole tree, case-insensitive, for the following, then list every hit:
   - The learner's name
   - home paths and `.env` paths
   - agent/tool/project/team ids
   - time zone
   - deploy URL
   - persona name
   - dated comments ("user-approved 2026-10-01")
   - gendered pronouns in prompts, UI and comments
2. **Identity → `lib/config.ts`** (server-only env reads):
   - `APP_NAME`, `APP_SHORT_NAME`, `LEARNER_NAME`
   - `LEARNER_NAME_SOUND`, for the "My name is …" sound guide
   - `ICON_LETTER`, `COACH_NAME`
   - `DEFAULT_TZ`, defaulting to `UTC` (not the owner's zone)

   Pass the values to client components as props from the server `page.tsx`; don't use `NEXT_PUBLIC_*`.
3. **Curriculum name phrases** use `{name}` / `{nameSound}` placeholders filled in `lib/content.ts`. Add a unit test that no placeholder survives.
4. **Prompt**:
   - Make it pronoun-neutral ("the learner", "they").
   - Make persona, learner name and content policy dynamic variables (`{{coach_name}}`, `{{learner_name}}`, `{{topic_policy}}`).
   - Add placeholders for any new variables in `sync-agent.mjs` `dynamic_variable_placeholders`.
   - Sync the agent and redeploy back to back. A prompt with a new variable and an app that doesn't send it breaks sessions in between.
5. **Content policy toggle**: `OPEN_TOPICS=standard|adult` in `lib/topic-policy.ts`.
   - Public default: `standard`, which keeps slang and mild swearing but steers sexual content away.
   - The owner's instance keeps `adult`.
   - Both modes keep the minors hard line.
   - Unit-test both texts.
6. **Icon**:
   - Replace the hand-made PNG with a `next/og` `ImageResponse` route (`app/app-icon/route.tsx`, `force-static`) that draws `ICON_LETTER`.
   - Point `metadata.icons` and the manifest at `/app-icon`.
   - Whitelist it in the proxy matcher.
7. **Scripts**:
   - `sync-agent.mjs` pins `ELEVENLABS_AGENT_ID` when set (else matches by `AGENT_NAME`), and writes the new id into `.env.local`.
   - Add `setup-secrets.mjs`. It fills the empty secrets in `.env.local`, is idempotent, sets chmod 600 and prints nothing secret.
   - Add `setup-vercel.mjs`. It pipes `.env.local` values into `vercel env add`.
   - The E2E script reads `BASE_URL` / `LEARNER_KEY` / `ADMIN_PASSWORD` from env.
   - npm scripts use `node --env-file=.env.local`.
8. **Owner-only tooling → gitignored `.local/`**:
   - deploy, provision and identity scripts
   - the E2E wrapper that reads the owner's secrets
   - screenshot/update/reset checks with hardcoded URLs
   - the leak gate
   - the publish script

   Delete spike scripts from the public tree.
9. **Set the owner's identity env on Vercel first** (`.local/set-identity.sh`), then redeploy. Verify the live instance looks identical:
   - title, greeting and manifest
   - icon pixels
   - the dynamic variables the agent actually received (`GET /v1/convai/conversations/{id}` → `conversation_initiation_client_data.dynamic_variables`)
   - full E2E
10. **Docs**:
    - README: biggest claims and every feature first, then a "How it works" diagram, setup, a config table and costs.
    - `docs/architecture.md` and `docs/known-issues.md`.
    - `.env.example` with every variable commented.
    - MIT `LICENSE`.
11. **Publish**: run the leak gate, commit, `gh repo create --public --source . --remote origin`, `timeout 120 git push`, add topics. Then verify from a fresh clone:
    - leak gate is clean
    - `npm ci`, typecheck and tests pass
    - `setup-secrets` works
    - API tree count equals clone count
    - the repo page returns 200

## Pitfalls

- `.gitignore` with `.env*` also hides `.env.example`; add `!.env.example`. The leak gate's forbidden-file check must allow `.env.example` while still blocking `.env`, `.env.local` and `.env.diag`.
- Grep the leak gate for the **actual secret values** (read from the secrets dir and `.env`) as well as the names. Print `<secret>` instead of the value on a hit.
- Over-broad leak terms produce false positives: `conv_` matches the conversation-id validation regex, and a time-zone name appears in tz unit tests. Narrow the term (`conv_[0-9]`) rather than editing correct code.
- Git committer identity here defaults to an AI-assistant address. Commit with `-c user.name=... -c user.email=<owner public email>` and tell the user the author email is public.
- After genericizing, recheck the UI for small regressions the refactor exposes (it caught "1 phrases learned").
