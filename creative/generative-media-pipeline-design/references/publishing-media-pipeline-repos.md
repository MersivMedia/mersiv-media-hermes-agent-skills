# Publishing a generative-media pipeline to a public repo

Two properties make this class of project unusually easy to publish badly:

1. It reads **four or five provider credentials** (LLM, video, stills, TTS).
2. It sits inside **hundreds of MB of generated media** that is reproducible
   from code plus canon, and therefore should never be committed.

The audit below is cheap and catches both. Run it before the first commit — a
fresh repo has no history to scrub, which is by far the easiest time to get this
right.

## 1. Pre-flight: is the source actually clean?

Every provider client should read from the environment. The passing result of
this scan is that it returns **only** `os.environ` hits and no literals:

```bash
# key literals — adjust patterns to your providers
grep -rnEi '(sk-[A-Za-z0-9]{20,}|r8_[A-Za-z0-9]{20,}|xi-api-key:[[:space:]]*[A-Za-z0-9]|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{32})' \
  --include='*.py' --include='*.json' --include='*.md' --include='*.sh' .

# what the code expects to find in the environment
grep -rhoE 'os\.environ(\.get)?\[?\(?"[A-Z_]+"' engine/*.py | sort -u
```

The second command doubles as the source of truth for `.env.example` — every
variable it prints needs an entry.

## 2. Check the tree for duplicate / mangled modules

Generated-media projects accumulate scratch copies. One session had a
byte-identical copy of the fal client under a truncated name, and the renderer
imported *that* one — so edits to the real module did nothing.

```bash
ls -1b engine/            # -b reveals odd characters in names
diff engine/a.py engine/b.py && echo IDENTICAL
grep -rn "^import \|^from " engine/*.py | grep -v '^.*:import \(os\|sys\|json\)'
```

After deleting a duplicate and repointing imports, prove the package still loads:

```bash
.venv/bin/python -c 'import sys; sys.path.insert(0,"engine")
import render_scene, showrunner, writer, preprod, qc, normalize, dialogue
print("all modules import ok")'
```

## 3. Exclusions

```gitignore
# secrets
.env
*.key
*credentials*.json

# generated media — reproducible from canon + assets
assets/
renders/
runs/

# python
.venv/
__pycache__/
*.pyc

# scratch dirs this workflow creates
_quarantine/
_raw/
_v*_*/
```

Note the last group: the quarantine and versioned-backup directories that the
asset-QC workflow produces are working state, not deliverables.

## 4. Audit the staged diff, not just the working tree

This is the check that actually matters, because it inspects exactly what the
commit will contain:

```bash
git add -A
git status --porcelain                      # eyeball the file list
git diff --cached | grep -nEi '<key patterns>'   && echo '!!! SECRET !!!'
git ls-files | grep -E '^\.env$|^assets/|^renders/|^runs/|\.venv' && echo '!!! LEAK !!!'
```

## 5. Verify the REMOTE after pushing

Local cleanliness is not proof. Ask the API what was actually published:

```bash
gh api repos/<owner>/<repo>/git/trees/main?recursive=1 --jq '.tree[] | select(.type=="blob") | .path'
gh api repos/<owner>/<repo>/git/trees/main?recursive=1 --jq '.tree[].path' \
  | grep -E '^\.env$|^assets/|^renders/|^runs/' && echo '!!! LEAK !!!' || echo CLEAN
```

## 6. `.env.example` shape

Ship the variable names with empty values and a comment explaining what each key
buys, so a reader knows which accounts they need before cloning:

```bash
# Showrunner LLM (story engine, schema-validated JSON)
ANTHROPIC_API_KEY=

# Video generation — provider-exclusive model, see README
FAL_KEY=

# Reference plates / location plates
REPLICATE_API_TOKEN=

# Per-character dialogue TTS
ELEVENLABS_API_KEY=
```

## What the README should carry

For this class of project the reproducible value is **the measurements and the
failures**, not a feature list. Sections that earn their place:

- Why each validator rule exists, with the evidence that produced it (shot-length
  ceiling, retired chaining mode, required camera-geometry field).
- The lookahead-depth utilization table and the formula derived from it.
- QC gate tolerances with real pass/fail numbers, including pixel values for any
  canon property (e.g. costume RGB passing vs failing).
- Provider gotchas: endpoint-id shape, required parameters, reference-citation
  requirements.
- **Known limitations stated plainly** — retired techniques, unbuilt components,
  unreconciled behaviours. This user values honest gaps over polish.

A commit message for the initial publish should summarise the *design decisions
and measured findings*, not the file list.
