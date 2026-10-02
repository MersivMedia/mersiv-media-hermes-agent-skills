# First PyPI release (verified 2026-10-02: jev-rag-retrieval 1.0.0, clef-rag 0.1.0, clef-finetune 0.1.0)

## Check what's actually published before you agree with "you did it before"
The user remembered jev-rag being on PyPI. It never was: it only had a GitHub release labelled v1.0.0, and `jevrag` on PyPI belongs to someone else. Check both of these before you answer:
- `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/<name>/json` for each distribution name (404 means it doesn't exist)
- `session_search` for the earlier session
Then report what really happened, with a session link, and offer the publish. Don't play along with a false memory, and don't flatly deny it without evidence.

## Credential options (offer as numbered choices)
1. **Trusted publishing**, recommended: a GH Actions release workflow plus a pypi.org "pending publisher" per project. No token ever reaches the box.
2. **API token**: the user pastes it. In this case the user just pasted a token instead of answering, so treat that as picking option 2.

Token handling, all from script files with no argv/echo:
- `write_file` the token to a temp file, then a Python script moves it into `~/.hermes/.env` as `PYPI_API_TOKEN`, sets chmod 600, deletes the temp file and prints only the path and mode.
- The upload script reads the token in-process and passes it through the `TWINE_USERNAME=__token__` / `TWINE_PASSWORD` env vars.
- Redact the token from captured output (`text.replace(tok, "***")`) and assert it's absent from the staged diff.
- Afterwards, advise rotation, and project-scoped tokens once the projects exist.

## Prep each repo (one Python script, `sub1()` asserting every old string exists)
- **Version:**
  - `X.Y.Z.devN` becomes `X.Y.Z` in both `pyproject.toml` and `__init__.__version__`. Grep the docs for the dev string too (KNOWN_ISSUES said "Fixed in 1.0.0.dev0").
  - A first-time package with no real-model results gets `0.1.0` and `Development Status :: 3 - Alpha`. A measured one gets 4 - Beta.
- **README links:** relative links (`docs/X.md`, `examples/dir`) break on pypi.org. Rewrite them to `https://github.com/<o>/<r>/blob|tree/main/<path>`, using blob when the path has a file extension and tree when it doesn't, and leave `http`, `mailto` and `#` links alone. Assert that zero relative links remain.
- **Install text:** "Until the first PyPI release, install from GitHub: pip install x @ git+..." becomes `pip install "x[extra]"`. Fix cross-package `pkg@git+` lines too. If examples/configs live only in the repo, keep a "clone for starter kits" block.
- **Metadata:** classifiers, keywords, `[project.urls]` (Homepage/Issues/Known issues), and an upper bound on `requires-python`. An SPDX string `license = "Apache-2.0"` needs `setuptools>=77` in build-system.

## Build and check (before any upload)
- If a `dist/` already exists, move it to quarantine rather than `rm -rf` it. Confirm `dist` is git-ignored.
- `uv build --out-dir dist .`, then `uvx twine check --strict dist/*`.
- Inspect the wheel's file list with zipfile: package-data templates and vendored files must be present, and `.env`/`.venv` must be absent from the sdist.
- Install the **wheel** into a fresh `uv venv` and run `--help`/`--version` on each CLI, plus `importlib.resources` reads of the package data.
- For a torch-heavy package, install CPU torch first from `https://download.pytorch.org/whl/cpu`, then run one real command (e.g. `make-tiny`).

## Publish, in one script and in this order per repo
1. `git fetch` and assert `HEAD..@{u}` = 0, since the user hand-edits on GitHub.
2. Run the test suite and record the pass line.
3. Commit, push.
4. `uvx twine upload --disable-progress-bar dist/*`.
5. `git tag -a vX.Y.Z`, push the tag, `gh release create vX.Y.Z dist/* --notes "pip install ..."`.

Run it in the background with notify, and log to a file.

## Verify from outside
- After a ~20 s wait, the PyPI JSON should show the version, both files and the license.
- Install from `--index-url https://pypi.org/simple --no-cache` in a fresh venv, then check `__version__` and the CLI `--version`.
- `gh release list`, and wait for CI on the release commit. Report the CI result, not the local one.
- Remind the user that a PyPI version can never be re-uploaded, so every fix needs a version bump.
