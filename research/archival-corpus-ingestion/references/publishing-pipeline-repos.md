# Publishing a corpus/pipeline repo someone can actually run

Repo mechanics are covered by `github-repo-management`. These are the things
that made a published pipeline repo *wrong in practice*, learned by being
corrected.

## 1. Order the README by what the reader must do first

Write setup in **execution order for someone starting from nothing**, not the
order you built it.

A user on a freshly rented GPU box needed the agent harness installed and the
model server running *before* the repo was any use — but the README cloned the
repo first and mentioned the harness near the end. They had to point it out.

Corrected shape:

```
Part 1  install the agent harness      (verify it runs)
Part 2  install + serve the model      (verify the endpoint)
Part 3  clone the repo, install skill  (verify data + fetching)
Part 4  benchmark before spending
Part 5  pilot on a subset
Part 6  run the loop
```

Ask: *what state is the reader's machine in when they open this?* Number the
parts so the dependency chain cannot be misread.

Lead with the finding that changes their decisions. A measured result that
rules out an obvious-looking approach (e.g. "hosted APIs refuse this content")
belongs near the top — not in a subsection they reach after already doing it
the wrong way.

## 2. Never invent a command

Every CLI invocation, config key and install URL must be checked against the
real tool before commit:

```bash
curl -sI <install-url> -w "%{http_code}\n" -o /dev/null       # 200?
grep -nE '^\s*(base_url|api_key|default|provider):' ~/.<tool>/config.yaml
<tool> --help
```

Documented-but-fictional flags are worse than no documentation: the reader
trusts them and loses an hour. Read the tool's own skill or `--help` output
rather than recalling the flag names.

## 3. Wire the local model into the harness explicitly

If the pipeline serves a local model, show the reader how to point the agent at
it — otherwise the agent cannot inspect the artifacts it is meant to be
debugging. For a vLLM-style OpenAI-compatible endpoint:

```bash
hermes config set auxiliary.vision.provider openai
hermes config set auxiliary.vision.base_url http://localhost:8000/v1
hermes config set auxiliary.vision.model <model-id>
hermes config set auxiliary.vision.api_key local
```

State the role split plainly: the **agent** makes hundreds of reasoning calls
on metadata; the **bulk model** makes millions of calls on content. A small
local model is right for the second and usually too weak for the first. Price
and choose them separately.

## 4. Committing data deliberately

"Never commit data" is the default, but mirroring a hard-to-replace artifact is
a legitimate exception — an index that took a lawsuit and nine years to exist
should not hang off one unmaintained personal account.

```
GitHub hard limit    100 MB per file (rejected above)
GitHub warning        50 MB per file (accepted, warns)
```

Negate the ignore rule narrowly, ship checksums, and explain the exception in a
README beside the data:

```gitignore
*.zip
!manifest/crest1.zip
!manifest/crest2.zip
```

Then **verify the round trip** rather than trusting the push:

```bash
curl -sL "https://raw.githubusercontent.com/$OWNER/$REPO/main/manifest/x.zip" -o /tmp/dl.zip
sha256sum /tmp/dl.zip && grep x.zip manifest/SHA256SUMS
```

Update the setup steps too — once the data ships in-repo, step 2 becomes
"verify the checksums", not "curl it from upstream".

## 5. Verify the remote, not the local tree

A clean `git status` proves nothing about what is published. Fetch the file
back and diff:

```bash
curl -s "https://raw.githubusercontent.com/$OWNER/$REPO/main/path/file.md" -o /tmp/r.md
diff /tmp/r.md path/file.md && echo "remote == local"
```

This catches a common ordering mistake: copying a file into the repo *before*
patching the original leaves the local copies agreeing with each other while
the published version is stale. Checking "local == local" feels like
verification and is not.

Also confirm the default branch — `gh repo create --source=. --push` can
publish `master` while everything else assumes `main`:

```bash
git branch -M main && git push -u origin main
gh api repos/$OWNER/$REPO -X PATCH -f default_branch=main
```

## 6. Deploy platforms validate the commit author

Platforms that deploy from git validate the **commit author** against team
membership. A commit authored as `agent@local` is accepted by GitHub and then
silently refused downstream:

```
seatBlock: { blockCode: "COMMIT_AUTHOR_REQUIRED" }
```

Set the identity before the first commit:

```bash
git config user.email "<platform-account-email>"
git config user.name  "<Name>"
```

If earlier commits already carry the wrong author, **do not rewrite history** —
force-push is destructive and will be blocked. Layer one correctly-authored
commit on top; only the deployed commit is checked.

## 7. Three-check secret audit before every push

```bash
# source scan — no literals, everything via env
grep -rnE '(api[_-]?key|token|secret)\s*=\s*["\x27][A-Za-z0-9_-]{16,}' --include='*.py' .

# staged diff — provider-specific key shapes
git diff --cached | grep -nEi '(sk-ant-[A-Za-z0-9_-]{20,}|r8_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{30,})'

# remote tree — no .env, credentials, or unintended data
gh api repos/$OWNER/$REPO/git/trees/main?recursive=1 --jq '.tree[].path'
```

Eyeball the staged file list as well. Build artifacts slip in constantly —
generated HTML, `__pycache__`, `tsconfig.tsbuildinfo` — and belong in
`.gitignore`.

## 8. Ship the skill inside the repo

A pipeline repo that depends on agent knowledge should carry that knowledge:

```
skills/<skill-name>/SKILL.md
skills/<skill-name>/scripts/*.py
```

One `cp -r` installs it. Keep the in-repo copy and the installed copy in sync,
and remember §5 — patch first, copy second, then verify against the remote.
