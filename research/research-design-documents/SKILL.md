---
name: research-design-documents
description: "Propose a novel architecture; prove it's not a relabel."
version: 1.0.0
author: Nous Research
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [research, architecture, novelty, literature-review, falsification, delegation]
    category: research
    related_skills: [grounded-citations, research-paper-writing, arxiv, ml-paper-writing]
---

# Research Design Documents

Writing a document that **proposes a new system design** grounded in an outside
field — neuroscience, biology, physics, economics — and defends it against the
charge that it is an existing technique wearing a costume.

## When to Use

Load this when asked to research and design a novel architecture, especially
when the premise is "system X should work more like Y" where Y is a natural
system. Also load it when a proposal needs an honest novelty assessment, or
when the deliverable is a research document rather than an implementation.

For citation mechanics use `grounded-citations`. For conference submissions use
`research-paper-writing`. This skill is about the *content* of the proposal and
whether it survives scrutiny.

---

## 1. The novelty test is the whole job

Cross-domain inspiration produces proposals that sound profound and reduce, on
inspection, to something the field already does. **A design document that skips
this test reads as cosplay** and will be dismissed by exactly the readers you
want.

Every mechanism you import gets this treatment, stated explicitly in the
document:

```
mechanism            what the biology/source actually does, mechanistically
closest analog       the existing primitive it MOST resembles
genuinely different? yes/no — and if yes, in what specific respect
evidence             demonstrated at scale, toy-scale only, or theoretical
```

Run it honestly and it will kill some of your favourite ideas. That is the
point — the survivors are the parts worth building, and the rejections are what
make the document credible.

### Publish the rejections

Put a verdict table near the top: what to build, what to reject, and *why*. A
document that endorses everything it surveyed has not filtered anything.

Worked example from a brain-inspired AI proposal:

| Proposal | Verdict |
|---|---|
| Astrocyte-factorised associative memory | **Build** — supralinear capacity, a real implementation advantage |
| Activity-dependent delay learning | **Build** — ANNs have no per-edge delay parameter at all |
| Microglial synaptic pruning | *Reject* — magnitude pruning with extra steps |
| "Glia are 50% of brain cells" | *Reject* — factually contested and argumentatively weak |

That last row matters. **Abundance is not evidence of computational
importance.** When a founding intuition rests on a weak argument, keep the
intuition and replace the argument — the stronger version of the same thesis
usually exists and is more specific.

### Scope every rejection to the function you actually assessed

A verdict table invites over-broad rejections, because a row reads as a ruling
on the whole source system when the assessment covered one function of it.

The microglia row above is the cautionary case. What was assessed was
**complement-mediated synaptic pruning**, which really does reduce to iterative
magnitude pruning. What the row was then taken to mean was "microglia offer
nothing" — a much larger claim that the assessment never supported. Microglia
also mediate cytokine-driven homeostatic synaptic scaling and act as a negative
feedback controller on neuronal activity, both on slow timescales, and in that
particular document slow-timescale modulation was *the entire thesis*. The
rejection had plausibly discarded on-topic material.

Two checks before a reject verdict ships:

- **Name the function, not the system.** Write "microglial synaptic pruning —
  reject" rather than "microglia — reject". If the row names a cell type, an
  organ, a discipline, or a whole method family, the scope is probably wrong.
- **Ask what else the source system does.** Survey the source's *other*
  functions against your thesis before closing the row. A system usually has
  several mechanisms, and the famous one is not always the relevant one.

Watch for one particular inference, which is the error that produced this:

```
evidence found   "no good published work applies X to our field"
claim written    "X has nothing to offer our field"
```

Those are different propositions and the second does not follow. Absence of
good downstream work is frequently a statement about what has been *tried*, not
about the source material. Say which one the evidence supports.

**Reject verdicts need the same evidentiary standard as build verdicts.** A
line like "test it against the obvious baseline; expect little" states a
prediction as a finding. Either run the comparison or mark the row as untested
— an unargued rejection is exactly as weak as an unargued endorsement, and it
is easier to miss because it looks like rigour.

When a rejection is challenged, re-derive it rather than defending it. Dispatch
the check as two tasks — what the source system actually does, and what the
target field's existing methods actually cover — so the comparison is made
against the real state of both sides rather than against your summary of them.

### Distinguish a bridge result from an engineering result

Work proving that system Y *can implement* known technique X is scientifically
valuable and offers **zero engineering justification** — it recovers what you
already have. Cite it as a bridge; never as evidence the approach improves
anything. These papers are the most commonly over-claimed item in this genre.

### Run the novelty test a second time at PROGRAMME level

Mechanism-level novelty is not enough. A proposal can clear every individual
comparison and still be an existing *research programme* under new vocabulary.
Before shipping, name the closest programmes explicitly and say what your
proposal shares with each:

> Active inference subsumes prediction error, precision-as-attention and
> homeostatic drives in one formalism. The affect proposal here is arguably a
> special case with a specific implementation. Anyone reviewing this will
> raise it.

Include this as its own section near the end. Two reasons it is worth the
space: a reviewer who spots an unacknowledged parent programme stops trusting
the whole document, and doing the comparison forces you to state the
contribution at the right size. Usually the honest claim shrinks to a
*coupling* — each component exists somewhere, the combination does not — and
that is a defensible claim rather than an inflated one.

### Dispatch the novelty audit as its own adversarial task

Do not self-assess this. Give a subagent the thesis and a single question:
**has the field already solved this under another name?** Name the candidate
mechanisms yourself so it cannot answer by surveying only friendly territory,
and require a verdict plus a rewritten claim:

```json
{"verdict_on_novelty": "...", "qualified_claim": "...",
 "mechanisms": [{"name": "...", "timescale": "...",
                 "persists_how_long": "...", "does_it_work": "..."}]}
```

The `qualified_claim` field is what makes this work — it forces a *usable
replacement* rather than a critique you then have to act on. In the worked
example the audit returned:

> PARTIALLY DEFENSIBLE — the unqualified form is FALSE and would be caught by
> any competent reviewer.

…and supplied a three-clause version that survived. The rewrite moved the claim
from "the field lacks X" to "the field lacks a *single variable combining*
X, Y and Z", with each ingredient's existing implementation cited. Same
programme, defensible framing.

Two failure modes the audit should be told to avoid:

- **Do not present a deliberate design choice as an oversight.** Per-sequence
  state reset is intentional; the burden is to show nobody made the alternative
  *work*, not that nobody thought of it.
- **Name the live competitor.** The most dangerous prior art is recent and
  moving in your direction. Ask "what is the strongest current threat to this
  thesis?" and state in the document what you add beyond it.

---

## 2. Separate "models X" from "displays X" from "actually does X"

For any claim that a system genuinely *has* some property — understanding,
emotion, intent, preference — three categories collapse in casual discussion:

```
(a) MODELS it as data        classifies it, represents it       usually trivial
(b) DISPLAYS it as output    says it, performs it               usually trivial
(c) an internal state that
    genuinely MODULATES
    its own computation                                         ← the real target
```

**The most likely way this class of project fails while appearing to succeed is
optimising the label or the report**, because those are easy to measure and
immediately impressive. That yields (b) wearing the costume of (c).

Make (c) operational with testable criteria. For an internal-state claim:

1. **Endogenous** — computed from the system's own signals, not supplied as input.
2. **Right timescale** — slower than inference, faster than training.
3. **Broadly causal** — modulates ≥3 distinct downstream processes.
4. **Not self-writable** — the output channel cannot set it, so it cannot be gamed.
5. **Introspectable with *measured* fidelity** — any self-report's correspondence
   to the underlying variable is published as a number, not taken at face value.

On self-report specifically: it is generated by the same process that generates
every other output and is shaped by training on human descriptions. It is
evidence about the training distribution, not the interior. Say so.

### Use the vocabulary of the target field, not the folk one

Informal terms for the contested property — *feeling*, *experiences*,
*sentience*, *what it is like* — invite dismissal and obscure the actual claim.
Translate to the functional register before the document ships:

```
informal                     technical
───────────────────────────  ──────────────────────────────────
feeling / experiencing       homeostatic state variable
emotion                      affective modulation / valence signal
"actually feels"             endogenous state with causal efficacy
understands                  maintains a task-predictive internal model
the sentience question       (cut — out of scope, not argued)
```

**This costs nothing analytically.** Every testable claim survives translation
intact — the operational criteria, the ablation, the variable mapping. What goes
is the part that was never defensible and that makes a reviewer stop reading.

Then say plainly, once, that the phenomenal question is not addressed, not
required, and not decidable by any proposed experiment. Do not argue either
side; declining to claim is stronger than hedging.

Grep the finished document for the banned terms as a mechanical check — they
reappear in prose written before the decision.

### Write in the register of a paper, not a manual

A design document is a scientific white paper. Three habits leak in from
note-taking and working drafts, and all three need a mechanical sweep before
shipping:

```bash
grep -niE '\byou\b|\byour\b' doc.md        # second person — should be ZERO
grep -niE 'earlier draft|we had before|previously stated' doc.md
grep -n '^#.*\b(corrected|fixed|updated)\b' doc.md   # headings about process
```

- **No second person.** "Use (c) as the substrate" is instruction-manual voice.
  A paper says what the architecture does, or what a practitioner would do —
  never what *you* should do. This survives even in quoted principles: rewrite
  "conditioned on your own actions" as "conditioned on the system's own
  actions."
- **No references to the document's own history.** "An earlier draft cited
  figures that…" is working-notes register. The published artifact has no
  drafts; it has findings. State the established value and move on.
- **Name sections for content, not process.** "Spatial simulation" — not
  "Spatial simulation, with the numbers corrected."

The user's framing is worth keeping verbatim as the test: *this is not an
instruction manual, it is a scientific white paper and should be written as
such.*

### State the domain in the first sentence

A document about applying field Y to field X must name **X** — the target
domain — in the title and in the opening sentence. A title like "Persistent
Modulatory State in Neural Architectures" reads as neuroscience; "…for
Artificial Intelligence Modeling" does not. Readers arriving from the target
field should never have to infer that the document is for them.

The abstract also needs an explicit **why-these-topics** passage: one short
paragraph per imported area saying what structural absence in the target field
motivated examining it. Without it, a cross-domain survey reads as
enthusiasm-driven. With it, each area is there because it addresses a named
gap — which is also a useful discipline on the author, since an area that
cannot be justified this way probably does not belong in the document.

---

## 3. A design that cannot fail is not a design

End with a falsification table — one row per load-bearing claim, each with a
test and an explicit failure condition.

**Ablation is usually the decisive experiment.** Remove the proposed component
and check whether degradation is *characteristic* of the thing you claimed it
does. Unchanged performance means the component is decoration. Structured,
predictable degradation is real evidence.

Order the build sequence so the decisive experiment runs **early and small**. If
the central thesis is wrong, find out on a toy system rather than after months
of scale-up.

### Write an explicit unresolved section

State what is not known, in plain language: which results are toy-scale only,
which assumptions are hand-chosen, what is undecidable by any proposed
experiment. A research document that hides its gaps is marketing. This user in
particular rewards honest gaps over confident filler, and reads for them.

---

## 4. Delegating the literature review

Parallel subagents work well here — the reviews are independent and each floods
context with material you want filtered, not stored.

**Put the skepticism in the contract, not in the prose.** Use `output_schema`
to force a verdict per mechanism rather than hoping for one:

```json
{"cell_type": "...", "computational_function": "...", "timescale": "...",
 "closest_ml_analog": "...", "genuinely_novel": true,
 "demonstrated_or_speculative": "...", "urls": ["..."]}
```

A boolean `genuinely_novel` field cannot be evaded by an enthusiastic summary.
Ask explicitly for the closest existing primitive and for an honest assessment
of redundancy; instruct the agent to verify every URL and mark unverifiable
claims `[UNVERIFIED]`.

### Recovering a timed-out subagent

Subagents doing deep literature review routinely hit the 600s cap — often
*after* completing the analysis, while writing the final summary. **The work is
not lost.** The live transcript holds everything:

```bash
LOG=~/.hermes/cache/delegation/live/<delegation_id>/task-<N>.log

grep -oE 'https?://[a-zA-Z0-9./_-]+' "$LOG" | sort -u   # verified sources
tail -40 "$LOG" | cut -c1-220                           # where it stopped
grep '^[0-9:]* *assistant' "$LOG" | sed 's/^[0-9:]* *assistant| *//'
```

Check the tail first: an agent that was mid-write has usable findings, while one
stuck on a hung call at call 3 does not. Completed siblings write full output to
`~/.hermes/cache/delegation/subagent-summary-<N>-<timestamp>.txt` — read that
file rather than the truncated batch summary, which is trimmed to protect
context. Parse the JSON out of it with `raw[raw.find('{'):raw.rfind('}')+1]`.

**Tell the user when a section came from a recovered partial** rather than a
clean result. Provenance of your own process is part of the deliverable.

### Prefer re-dispatch over salvage when the detail matters

Transcript lines are truncated (~600 chars each), so recovery gives you the
agent's *conclusions* but usually not its *reasoning*. That is enough to know a
finding's direction, not enough to write mechanistic detail. Filling the gap
from your own memory and presenting it as reviewed research is the failure mode
to avoid.

Re-dispatch instead, and make the second attempt narrower:

- **Pass forward what is already verified.** List the citations the first run
  confirmed and say explicitly not to re-verify them. Most of the dead run was
  spent re-checking URLs.
- **Ask for detail, not coverage.** "Mechanistic detail and opinionated
  maturity assessment, not another link list. Equations where they clarify."
- **Force a verdict per item** — e.g. `BUILD TODAY / RESEARCH PROBLEM /
  DEAD END`. Ordinal verdicts resist hedging the way a boolean does.
- **Give an explicit time budget**: "aim to finish in under 8 minutes; if
  running long, return what you have rather than timing out."

A scoped re-run of five specific questions completed in ~150s where the broad
version died at 600s. Narrow scope plus a stated budget is usually the whole
fix, and the second pass is where the load-bearing corrections come from —
expect it to overturn something you already wrote.

---

## 5. Verify every citation before publishing

### 5a. A live URL is not a verified claim

Link-checking proves a page exists. It says nothing about whether the number you
attributed to it is in it. **Famous quantitative claims are frequently textbook
accretions** — repeated so often they acquire a citation they never had.

Measured instances from one review, all of which had passed link-checking:

| Claim as written | What the primary source says |
|---|---|
| Mental rotation RT linear, `r ≈ 0.99` | **No correlation coefficient appears anywhere in the paper.** The real result is a significant linear component, p<.001, with no higher-order terms |
| Depth slope "indistinguishable" from picture-plane | Overstated. Authors call it "of doubtful significance" because it was absent or reversed in 4 of 8 subjects — a failure to find a difference, not demonstrated equality |
| "Glia are 50–90% of brain cells" | ~1:1. The 10:1 ratio is explicitly debunked in the review literature as an unsourced consensus error |
| One astrocyte contacts 10⁴–10⁵ synapses | Right for rodent; **understates human ~20×** |
| Aphantasics perform task X "normally" | Slower but *more accurate*, via a different strategy — substitution with a speed cost, not equivalence |

Run a dedicated verification pass as its own subagent task, with the schema
forcing a ruling per claim:

```json
{"claim": "...", "verdict": "CONFIRMED | CORRECTED | UNVERIFIABLE",
 "accurate_value": "...", "url": "..."}
```

Instruct it explicitly: *do not accept a number because it is widely repeated —
find the actual source*, and where a paywall blocks full text, say so rather
than substituting the common value. `UNVERIFIABLE` must be an available verdict
or you will get invented precision.

Three consequences worth planning for:

- **Budget a correction pass.** Expect this to overturn something load-bearing.
  In the worked example it reversed an argument: aphantasia had been used to
  claim depictive imagery is functionally inert; the evidence actually shows
  strategy substitution, so the claim had to narrow.
- **Publish corrected values authoritatively — not as a changelog.** Record what
  was wrong in your *working notes* so a future session does not re-import the
  bad number. In the *document*, state the established value with its primary
  source and let it stand. A `Claim | Status | Accurate value` table is
  working-notes register; it foregrounds the error over the fact and reads as
  self-absorption in a paper.

  ```
  working notes    | Claim              | Status    | Accurate value |
                   | Glia 50% of cells  | CORRECTED | ~1:1           |

  published        | Quantity                   | Value | Source |
                   | Human glia-to-neuron ratio | ≈ 1:1 | Azevedo 2009 |
  ```

  Where a common figure is wrong in a way that *matters to the argument*, one
  sentence of prose does the work — "the abundance argument is unsupported and
  is not used here; the case rests on timescale separation instead" — without a
  table cataloguing the author's revisions.
- **Corrections sometimes strengthen the thesis.** The corrected human astrocyte
  figure was ~20× larger than the one it replaced. Check before assuming a
  correction costs you the argument.

When no primary source settles a figure, **print no number**. State the
qualitative claim and record the gap in the unresolved section.

### 5b. Mechanical link checking

Fabricated or dead references destroy a research document's credibility faster
than a weak argument. Extract and check them mechanically:

```bash
grep -oE '\]\((https?://[^)]+)\)' doc.md | sed 's/^](//;s/)$//' | sort -u > urls.txt
while read u; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 25 \
    -A 'Mozilla/5.0 Chrome/120' "$u")  $u"
done < urls.txt
```

Follow redirects (`-L`) and send a browser UA — publishers reject default curl.
Treat 2xx and 3xx as fine; PubMed returns 203 routinely. Anything else gets
fixed or dropped before shipping.

**A 403/406 from a publisher is a bot wall, not a dead citation.** eLife,
ScienceDirect and similar reject scripted requests regardless of UA. Do not drop
the reference — swap in a mirror of the same paper that permits automated
access, which for biomedical work is almost always PubMed Central:

```
https://elifesciences.org/articles/04811      → 406 (bot wall)
https://pmc.ncbi.nlm.nih.gov/articles/PMC...  → 200 (same paper)
```

Prefer PMC or the arXiv abstract page over a publisher landing page when both
exist; they are stable, scriptable, and re-verify cleanly in every later pass.

---

## 6. Structuring the document

Lead with the **mechanism-level argument**, not the appeal-to-nature one. The
durable form is usually a specific structural gap:

> Biology runs four coupled timescales. Current systems run one and a half —
> fast volatile state and slow frozen state, with nothing between. Every
> capability we want lives in that gap.

That is falsifiable, specific, and survives scrutiny. "Nature does it and we
don't" does not.

A shape that works:

```
   Abstract          findings first, ~250 words, with the rejections
   Hypothesis        ONE falsifiable sentence, plus the null it must beat
0  Why necessary     the mechanism-level gap, with numbers
1  Why different     explicit contrast table vs existing approaches
2  Background        plain-language primers, one per unfamiliar concept
3  Mechanism review  each with its novelty verdict
4  Integration       how the parts form ONE loop, not a feature list
5  Evaluation        falsification table, decisive experiment first
6  Sequence          cheapest and most decisive first, WITH scale estimates
7  Methodology       named benchmarks, baselines, metrics, statistics —
                     AND the full design of the decisive experiment
8  Prior art         the closest existing work, named
9  Conclusion        what survived, what did not, what it would cost to refute
10 Unresolved        stated plainly
```

A document that ends on prior art and open problems trails off. **Close with a
conclusion that states what survived scrutiny, what did not, and what the
decisive test costs** — the asymmetry between "two weeks on one GPU" and the
size of the claim is the most persuasive thing available, and it belongs last.

**Abstract and hypothesis belong before the theory.** The theory is then judged
by whether it survives the stated test, rather than the test reading as a
postscript to a conclusion already argued for. Write the hypothesis as one
sentence with an explicit `H0` — a null that attributes any gain to added
parameters, added recurrence, or hyperparameter choice.

**But the method detail belongs in ONE place, and that place is the Methodology
section.** Putting a full Method block in the front matter *and* a Methodology
section later produces two accounts of the same experiment that drift apart —
the state-variable equation in one, the benchmark and baselines in the other.
The front matter carries the hypothesis and, at most, a one-line statement of
what the decisive test is; the experimental design, conditions, controls,
predicted signature, falsification criterion and cost all live together under
Methodology, beside the environment and baselines they depend on.

This correction came from the user directly: *the Method section in the
abstract should be combined and moved down to the method section later in the
paper.* When merging, keep the front-matter version's content — it is usually
the better-written one — and splice it into the Methodology subsection for that
experiment rather than summarising it away.

**Every unfamiliar concept gets a short plain-language primer**, boxed, before
the section that uses it. A reader who does not know what an eligibility trace
is should still be able to follow the argument; a reader who does can skip. Four
lines each is enough.

### Every equation gets a plain-language reading

Concept primers do not cover equations. A design document that states a
formalism and moves on has excluded every reader who is not already fluent in
that notation — which, for a cross-domain document, is most of its intended
audience. The user's instruction is the standard: *when equations are used,
they should be thoroughly explained.*

Three components, in this order:

1. **The idea in words, before any notation.** What the mechanism does,
   described so it could be understood with the equation deleted. For
   hierarchical predictive coding: *"Each level tries to predict what the level
   below is about to report. It sends that prediction down. The level below
   sends back only the difference — the part that was not predicted. If a
   prediction is perfect, nothing is sent back at all."*
2. **A symbol table** where more than two symbols appear. One row per symbol,
   plain-language meaning, and mark which one the proposal actually depends on:

   | Symbol | Meaning |
   |---|---|
   | `r^l` | The **representation** at level `l` — what that level currently believes |
   | `e^(l-1)` | The **error** — the gap between prediction and observation |
   | `Σ⁻¹` | **Precision** — how much to trust this channel. The key term for this proposal |

3. **A term-by-term walkthrough after the block.** Name what each term *does*,
   not what it is called. A multi-term update equation is usually a set of
   competing pressures, and saying so is the explanation:

   > `ṙ^l` is the rate of change of the belief. The three terms are three
   > pressures acting on it: pull from below (the prediction was wrong), pull
   > from above (the level above also had expectations), and pull toward the
   > prior. The belief stops moving when the three balance.

Analogies carry more than restated notation. A state variable with a decay term
and a drive term *is* a thermostat; say that. `λ ≈ 0.98` means *98% carries
over*, so an arm good a moment ago is probably still good and one good a
thousand trials ago tells you little. An objective written as `argmin` over
buffers reads, in words, as *keep the examples that will turn out to be most
useful later* — and stating it plainly is often what makes its difficulty
obvious.

For statistical models, **name the term the hypothesis is actually about**. In
a mixed model with an interaction, `β₃` is the claim and the rest is
bookkeeping; a reader who knows that can follow the argument without parsing
the formula.

Audit mechanically before shipping — extract every fenced block and check that
explanation follows it:

```bash
awk '/^```$/{n++} n%2==1' doc.md    # list fenced blocks; read what follows each
```

This costs length, and the cost is correct: a request for both brevity *and*
legibility is usually a request for legibility (see the length-audit section
above). Explanation is not redundancy.

### Give the experiments a plain-language section of their own

Concept primers are not sufficient. A reader can understand every defined term
and still not follow **what the experiment actually does** — because the
Methodology section is written in the register of a pre-registration, ordered
by protocol rather than by comprehension, and typically sits 60% of the way
into the document behind all the theory.

The symptom is a reader saying they do not understand the experiments while
the Methodology section is, technically, complete and correct.

Add a short section immediately after the hypothesis — before any theory —
that states in ordinary language what is being built and what each experiment
does. It is not a summary of Methodology; it is the version a competent reader
outside the subfield can follow:

```
The core idea        what the addition IS, in concrete terms
                     ("three numbers that change slowly; their only job is
                      to turn three dials the agent normally has fixed")
The decisive one     the task, WHY that task, the conditions as a plain
                     table, and what a negative result looks like
The others, briefly  one table row each: question | method | negative result
```

Three things make this section work rather than pad:

- **Name the conditions by the question each answers**, not by their formal
  property knockout. "Reset — *does carrying it over matter?*" is legible;
  "condition 2, ¬(i) ∧ (ii) ∧ (iii)" is not.
- **Call out the one or two conditions that carry the argument.** Say plainly
  that if the reset arm matches the full model the central claim is dead, and
  that the shuffled arm exists because it catches the most common way to fool
  oneself.
- **State the negative result for every experiment.** A reader who knows what
  failure looks like understands the design; one who only knows the procedure
  does not.

The formal Methodology section then keeps the full protocol and drops its
duplicated prose, pointing back: *"Seven arms, described in plain terms in
§The experiments in brief. Formally, the design is factorial over…"*

### Audit length by measuring, not by impression

When a document is too long, find the bloat by counting rather than by
re-reading. Section word counts as a share of total expose in seconds what a
read-through argues about for an hour:

```python
heads = [(m.start(), m.group(1)) for m in re.finditer(r'^# (.*)$', c, re.M)]
for i, (pos, name) in enumerate(heads):
    end = heads[i+1][0] if i+1 < len(heads) else len(c)
    w = len(c[pos:end].split())
    print(f"{w:>5}  {100*w/len(c.split()):>4.1f}%  {name}")
```

Then run the sharper diagnostic — **does each background section reference any
hypothesis or experiment?**

```python
body = c[sec_start:sec_end]
set(re.findall(r'\bH[1-4]\b', body)), set(re.findall(r'Experiment (\d)', body))
```

In the worked example every background section returned empty on both. A third
of the document was a literature review sitting *beside* the proposal rather
than supporting it — which is the real finding, and no amount of re-reading
surfaces it as crisply.

What to do with that result depends on what the document is for, and that is a
decision to put to the user rather than make silently. A research proposal
needs only the background that justifies its experiments; a position paper
needs the survey. A document doing both is the usual cause of unexplained
length. Say which one it currently is and ask.

**If the answer is "both", make the dual role explicit rather than leaving it
implicit.** Serving two purposes is a legitimate choice — the assessment
sections are often the most useful content for a reader deciding whether an
area is worth effort, and rejected mechanisms have no experiment attached but
still save someone else the work. What is not legitimate is leaving a reviewer
to discover the structure by hitting a section that litigates a mechanism the
proposal never uses.

One paragraph in the abstract fixes it — name both roles, map them to section
ranges, say the assessment deliberately exceeds what the proposal uses, and
give a skip pointer:

> Sections 4–7 are an *assessment*: which mechanisms survive comparison against
> the primitives they resemble, and which do not. Sections 8–10 are a
> *proposal*: five experiments testing the ones that survive. The assessment
> covers more ground than the proposal uses, deliberately — several mechanisms
> are examined and set aside, and the reasoning is reported rather than
> omitted. A reader interested only in the experimental programme can read the
> summary below, then skip to §8.

Verify the skip pointer resolves to the section that actually starts the
proposal; section numbers move during revision.

Cut in this order, cheapest first:

```
duplicated content   abstract restating the findings sections verbatim
orphaned sections    nothing cites them (§6 dependency trace above)
literature audits    compress to the conclusion they support
overlapping tables   a sequence table and an overview table of the same runs
```

Replacing ~900 words of redundancy with ~730 words of explanation left the
worked example the same length and substantially more legible. **Legibility and
brevity are not the same axis**, and a request for both is usually a request
for the first.

### Design the controls, not just the experiment

An ablation alone does not isolate the mechanism. Specify the controls that
separate your claim from the boring explanations:

| Condition | Controls for |
|---|---|
| Full model | the claim |
| Ablated — variable clamped to its mean | removes state, keeps parameters |
| **Shuffled — variable replaced by another episode's trace** | "any time-varying signal helps" |
| Parameter-matched baseline | capacity |

**The shuffled condition is the one most easily skipped and most necessary.** A
system that improves under a *random* slow signal has demonstrated that
recurrence helps, not that your mechanism helps.

State the predicted *signature* too, not just the direction. Structured
degradation — specific capabilities failing in a predictable pattern — is
evidence. A uniform drop supports the null.

**Put a scale estimate on every step of the sequence.** "Smallest build" is not
a number. Compute and duration change whether a proposal is worth starting at
all, and an ordering without them is an assertion:

| # | Step | Scale | Why here |
|---|---|---|---|
| 1 | Astrocyte-factorised DAM layer | 1 GPU, days | Strongest result; a capacity benchmark, not a trained system |
| 2 | Homeostatic affect layer + ablation | 1 GPU, 1–2 weeks | The decisive experiment |
| 5 | Continual learning: CLS + consolidation | 2–8 GPUs, months | Known-hard; attempt last |

When the load-bearing claims turn out to be single-GPU experiments answerable
in days, **say so explicitly** — it reframes the proposal from speculative to
cheaply testable, which is the strongest thing a design document can do.

**Find the loop.** A proposal listing four requested features is weaker than one
showing they are the same mechanism seen from different angles. In the worked
example, prediction error turned out to be simultaneously the learning signal,
the attention signal, the intrinsic reward, and — integrated over time — the
valence term. One quantity, four roles. Look for that unification; it is usually
there, and it is what makes a design document an argument rather than a list.

### Keep each mechanism's verdict consistent across the whole document

A mechanism gets discussed in at least two places — the review section that
assesses it, and the prior-art section that positions it. These are written at
different times and drift into contradicting each other.

The worked example had a section headed *"Astrocytes — mostly redundant, one
deep result"*, opening with a table of redundant functions. Forty pages later
the positioning section described published work as **validating** the same
mechanism. A reader encountering both concludes the document changed its mind.

Both statements were true; the ordering made them look inconsistent. Specific
astrocytic functions *are* redundant with normalisation and squeeze-excitation.
The organising motif — wide spatial pooling combined with slow temporal
integration — has no counterpart. Three structural fixes:

- **Verdict table at the head of the parent section**, before any subsection.
  State adopted / rejected / secondary for each mechanism with a one-line
  basis, so the detail below reads as support rather than reversal.
- **For an adopted mechanism, lead with the positive case.** Order the
  subsections *motif → evidence it works → which specific functions are not
  useful*. A section that opens with a redundancy table has announced a
  rejection in its first screenful regardless of what follows.
- **Title subsections for the verdict, not the ambivalence.** "Astrocytes" with
  an explicit verdict line beats "Astrocytes — mostly redundant, one deep
  result", which reads as a hedge and buries the conclusion.

### Cite the strongest supporting evidence where the claim is made

Related failure, and easy to miss: the single best piece of empirical support
for the proposal was cited **only** in the prior-art section, because that is
where the novelty audit surfaced it. The section actually making the case for
the mechanism argued from a capacity theorem alone and never mentioned that
someone had built the thing and reported it working.

Prior-art sections accumulate the best evidence as a side effect of competitive
positioning. After the positioning section is written, walk back through the
mechanism sections and ask, for each: *is the strongest support for this claim
cited here, or only downstream?* Cross-reference it into the argument and leave
the detailed treatment where it lives.

```bash
# every work named in positioning should appear in the section that needs it
grep -oE '\[([A-Z][^]]*[0-9]{4})\]' doc.md | sort | uniq -c | sort -rn
```

### Render structural diagrams as tables, not ASCII art

Multi-column ASCII laid out inside a code fence cannot wrap. It survives a
terminal and a desktop browser, then collapses into unreadable staggered
fragments on a phone — which is where the user will actually read it.

```
BAD — fixed-width columns in a fence, cannot reflow
TIMESCALE          BIOLOGY                      CURRENT ANNs
~1 ms              action potentials            forward pass
```

Convert anything with aligned columns to a real markdown table. **Keep code
fences only for content where per-line layout is semantic** — equations, code,
directory trees. The test: if it has columns, it is a table; if it has syntax,
it is a fence.

### When the thesis narrows, cut the sections written under the old framing

A design document's thesis usually narrows during revision — the novelty audit
shrinks the claim, a correction pass reverses an argument, a section gets
merged. **Sections written under the earlier, broader framing do not update
themselves.** They stay in the document arguing for a proposal that is no longer
being made, and they read as padding to anyone who notices.

In the worked example, one imported area entered as a co-equal pillar when the
document was a broad cross-domain survey. After the thesis narrowed to a single
mechanism, that area's real role had shrunk to *supplying one input signal* —
but the section still opened with "X as a substrate for cognition" and spent
most of its length on material nothing else referenced.

Before cutting on instinct, **trace the dependencies mechanically**:

```bash
grep -n '§6' doc.md                      # what the rest of the paper cites
grep -niE 'precision|saccade|dorsal' doc.md   # per-concept, outside the section
```

The result is usually stark — one subsection is load-bearing and the rest is
orphaned:

```
CUT   two-streams        nothing referenced it
CUT   active vision      no downstream use
CUT   spatial simulation a separate argument about a different field
KEPT  predictive coding  defines the term the HYPOTHESIS depends on
```

Keep only what something else needs, rename the section for the role it now
plays rather than the one it was written for, and make it earn its place by
answering a question the architecture raises. Then sweep for the debris the cut
leaves behind — orphaned cross-references (`§6.4` pointing at a deleted
subsection), the abstract paragraph still describing it as a pillar, an
experiment in the sequence table with no section behind it, and counts that
have changed ("five roles" → "four roles").

**The title and subtitle are part of the document and are the most commonly
missed.** A subtitle listing three themes when the paper now covers two is a
visible contradiction on page one; the user caught exactly this. After any
structural cut, re-read the title block against the section list and grep for
the removed framing:

```bash
grep -rin 'vision-centred\|vision-centric\|as a substrate' doc.md
```

The general rule: a section belongs in the document if removing it would break
something else. If nothing depends on it, it is a different paper.

### Cut status columns from data tables

A table that presents facts should present facts. Columns like `Status`,
`Verdict: CORRECTED`, or `Previously` turn a reference table into a record of
the author's revision history. Replace with `Quantity | Value | Source`. The
exception is a *deliberate* verdict table — novelty rulings, build/reject
decisions — where the judgement is the content.

---

## 6a. Methodology: name real benchmarks or say none exist

A proposal that specifies experiments without naming the benchmark, the
baseline and the metric is not yet falsifiable — it is a plan to make a plan.
Dispatch a dedicated subagent for this, with the instruction **do not invent
benchmarks** and a schema forcing four fields per experiment:

```json
{"name": "...", "benchmarks": "...", "baselines": "...",
 "metric": "...", "urls": ["..."]}
```

What this produces that self-assessment does not:

- **The baseline that actually threatens the claim.** For a proposal about
  adaptive internal state, the mandatory comparison is a recurrent meta-learning
  agent — the "ordinary recurrence already does this" rebuttal. Beating a
  feedforward baseline proves nothing. Ask explicitly: *what is the standard
  rebuttal architecture, and what must be included so a reviewer cannot raise
  it?*
- **The published number to clear.** "Competitive with state of the art" is not
  a bar. A specific figure with a citation is.
- **The discriminating condition.** Often the easy version of a benchmark
  separates nothing and a harder variant does — correlated rather than
  independent patterns, smallest rather than largest buffer. Ask which
  condition distinguishes real advantage from restatement.
- **An honest "no accepted benchmark exists."** Some subfields are genuinely
  fragmented. Saying so, and naming what the reference implementation was
  evaluated on instead, is stronger than implying a standard that is not there.
  Include the degenerate baseline that exposed the reference method's weakness
  (e.g. copy-last-frame for video prediction).

### Specify statistical practice explicitly

Venue expectations have moved and a design document should state its bar:

```
supervised    ≥5 seeds (10 preferred), mean ± SD, seed count in every caption,
              and say explicitly whether the interval is SD or SEM
RL            interval estimates via stratified bootstrap over the
              INTERQUARTILE MEAN, plus performance profiles — not
              point-estimate means over 3-5 seeds
```

---

## 6b. Positioning against the closest existing work

The novelty audit (§1) will sometimes return work that satisfies **every**
condition the proposal claims is unmet. Before treating it as a competitor,
establish what it actually is.

### First check whether it is a competitor at all

A subagent asked "does anything close this gap?" answers in the frame it was
given. It will return the nearest match labelled as a threat, because that is
what it was asked for — **it does not evaluate whether that framing is the
useful one.** Fetch the actual paper before writing a word of positioning:

```bash
curl -sL -A 'Mozilla/5.0 Chrome/120' "$URL" -o /tmp/p.html
# title + abstract tell you the field; keyword counts tell you the setting
grep -oiE 'benchmark|BPTT|dataset|episode|deployment' /tmp/p.html | sort | uniq -c
```

In the worked example the audit flagged a *Frontiers in Neuroscience* paper as
"the strongest live threat." The abstract showed it was a machine-learning
paper — proposing an online learning framework, benchmarking against
backpropagation-through-time, reporting on N-Caltech101 and Split CIFAR-100.
The venue had been mistaken for the field.

That distinction inverted the section. The work did not threaten the thesis; it
**validated the mechanism the thesis proposed**, on recognised benchmarks.

### Convergent evidence beats a distinction table

When the closest work shares your mechanism and reports it working, that is the
strongest result available to the document — not a liability to be fenced off.
Say so explicitly and restructure around three points:

1. **The mechanism is validated rather than speculative.** The standard weakness
   of a cross-domain proposal is that supporting results are toy-scale or
   theoretical. A published result using the same mechanism removes that
   weakness entirely. Lead with it.
2. **Independent corroboration is worth more than either result alone.** If the
   existing work reached a compatible conclusion from a different starting
   point, name the convergence — it is evidence neither paper provides by
   itself.
3. **It narrows what remains to be shown.** Convert the gap analysis from
   "distinctions that defend us" to "axes the validated mechanism has not yet
   been extended along":

| Property | Demonstrated by prior work | Remaining open |
|---|---|---|
| Slow variable with own dynamics | Yes — activity-integrating gate | Homeostatic setpoint with explicit decay |
| Multiplicative gating | Yes — of plasticity | Of forward computation too |
| Persistence | Within training stream | Across episodes at deployment |
| Setting | Spiking networks | Dense, backprop-trained |

The programme then reads as *extending a validated mechanism along three axes*
rather than proposing an untested idea — a strictly stronger position, and an
honest one.

Propagate the reframing to the abstract and conclusion in the same pass; both
will still carry the adversarial language. Grep for `competitor`, `threat`,
`undermin` afterwards to catch survivors.

### Validated prior art changes what the hypothesis may ask

This is the part most easily left undone, and it is not cosmetic. If existing
work demonstrates the mechanism, then **"does this work?" is no longer the
document's question** — and a hypothesis still phrased that way is factually
wrong, not merely unambitious.

The worked example shipped an abstract reading *"This document asks whether
adding an explicit medium-timescale state variable produces measurable
capability gains, and specifies how to find out"* — while its own conclusion,
written later, already said *"what remains to be shown is not whether a slow
gate can improve learning; that is established."* The document contradicted
itself across sixty pages because the prior-art finding arrived late and the
front matter never caught up. The user caught it: *we do know the slow state
variable is effective, we just want to test how far it goes.*

The repair has a standard shape. Qualify what the prior work demonstrated,
along every axis it did **not** cover, and promote each uncovered axis to its
own hypothesis:

```
demonstrated   a slow gate improves learning ... gating PLASTICITY,
                                                 WITHIN a training stream,
                                                 in a SPIKING network
                                                 ↓ each qualifier is an axis
H1 persistence  does carrying it across episode boundaries add anything?
H2 dynamics     does accumulation beat recomputation?
H3 gating scope does gating forward computation add to gating plasticity?
H4 transfer     does it survive outside the demonstrated setting?
```

Four consequences worth taking deliberately:

- **Split the single hypothesis.** A conjunctive H1 hides which extension
  failed. Separate hypotheses fail independently and map one-to-one onto the
  knockout conditions already required by §6c.
- **Name the load-bearing one.** Usually it is the property the novelty audit
  identified as the actual increment. Say in the text that the others are
  secondary.
- **Flag any hypothesis that is a precondition.** If the mechanism does not
  transfer out of the demonstrated setting, the remaining hypotheses are
  untestable in the target domain. That is a sequencing risk, and the old
  single-hypothesis framing hid it entirely.
- **Separate the failure modes in the conclusion.** "If persistence shows no
  advantage, *the contribution claimed here* does not exist — without
  invalidating the demonstrated result the programme builds on." A proposal
  that can fail without taking its foundations down is a stronger one.

Then make the evaluation table carry the hypothesis labels (`H1 — …`), so a
reader can see which experiment kills which claim rather than inferring it.

The broader rule: **a late-arriving prior-art finding invalidates the front
matter, and the front matter is written first and reread least.** Whenever the
positioning section changes what is known, re-read the abstract and hypothesis
against it in the same pass.

**The general lesson:** an audit dispatched to find threats returns threats.
Verify the primary source yourself before adopting its framing — the user asked
"shouldn't we just incorporate this as a source and not a competitor?" and was
right, because the subagent had never opened the paper.

### When it genuinely is a competitor

If the work truly occupies the same ground and does not support the thesis,
handle it in the document rather than softening it.

Give the closest work its own subsection, state what it achieves, and lay out
the remaining distinctions in a table:

| Dimension | Competitor | This proposal |
|---|---|---|
| Setting | Spiking neuromorphic training rule | General deployed architecture |
| What is gated | Plasticity only | Forward computation and plasticity |
| Persistence | Within training stream | Across episodes, wall-clock constants |

Then say how narrow the gap is, out loud:

> These are real distinctions but they are narrow. If the competing method
> generalises beyond its current setting, the contribution here reduces
> substantially.

Add an **ownership table** listing each component idea and who established it,
with an explicit line that novelty is claimed for none of them individually.
Two effects: a reviewer cannot land the "this is just X" objection because the
document already conceded it, and the residual claim — the conjunction — is
sized correctly.

Qualify the scope statement to match. "No architecture has X" becomes "no
*deployed, general-purpose* architecture has X, explicitly excluding the
<specific line> where it has been demonstrated." Precision here is what
separates a defensible claim from one that collapses on the first citation a
reviewer produces.

---

## 6c. Peer-review the document adversarially before shipping

A design document that has only been *written* has not been tested. Run a
structured review whose explicit goal is to break it — not to confirm it. The
most valuable findings come from checking whether the proposed experiment
actually tests the stated hypothesis, which is a different question from
whether the experiment is well designed.

Review in this order; the first check is the one that finds disqualifying
errors.

### Does the benchmark satisfy the hypothesis's preconditions?

**This is the highest-yield check in the entire review and the easiest to fail
silently.** A benchmark is usually selected because its *description* matches
the thesis vocabulary. Descriptions match at the level of keywords; structure
can be exactly inverted.

Worked example. The hypothesis required a state variable that **persists across
episode boundaries**. The methodology named DeepMind Alchemy, justified as an
environment whose latent structure "resamples between episodes" — which sounds
like non-stationarity and is. But *resampled per episode* means carried state
is stale and actively misleading, and the optimal policy is to **reset** belief
at episode start. The flagship experiment would have tested the opposite of the
claim, and a null result would have been uninterpretable: mechanism failure, or
an environment structurally hostile to the mechanism?

The check that catches this, for any proposed benchmark:

```
hypothesis requires   X persists / accumulates / transfers across boundary B
benchmark provides    is the thing X depends on preserved across B,
                      or is it resampled, reset, or randomised there?
```

Write the hypothesis's precondition and the benchmark's structural property as
two sentences next to each other. If they are in tension, the experiment is
invalid regardless of how carefully the controls are designed.

Two related traps in the same family:

- **A benchmark where strong baselines fail badly is a poor demonstration
  venue.** Improvement near the floor is hard to attribute to a specific
  architectural change rather than to noise. Check what published baselines
  actually score before adopting an environment.
- **Prefer an environment with a closed-form optimal solution.** If the
  Bayes-optimal version of the proposed variable is analytically available —
  a Kalman posterior over drifting values, a Bayesian volatility estimate — the
  hypothesis can be tested by *direct correlation against a known target*
  rather than only inferred from downstream reward. This converts a vague claim
  into a measurable one and supplies an extra falsification criterion
  (`r < 0.3` against the analytic posterior refutes the mechanism regardless of
  task score). Simple, interpretable environments are often stronger tests than
  complex ones for exactly this reason.

Keep the rejected benchmark in the document **as a named negative example**, and
better, as a control condition where the mechanism should provide *no* benefit.
If it does, the effect is an artefact.

### Is a conjunctive hypothesis tested as a conjunction?

If the claim is "a variable with properties (i), (ii) and (iii) will
outperform…", then testing the bundle against its absence cannot attribute the
effect to any single property. This matters most when the novelty audit (§1)
has already established that some properties are owned by prior work — the
experiment then fails to isolate the one property actually being claimed.

Add single-property knockouts:

| # | Condition | i | ii | iii | Isolates |
|---|---|---|---|---|---|
| 1 | Full model | ✓ | ✓ | ✓ | The claim |
| 2 | Property i removed, others intact | ✗ | ✓ | ✓ | **i — usually the claimed increment** |
| 3 | Property ii removed | ✓ | ✗ | ✓ | ii |
| 4 | Property iii removed | ✓ | ✓ | ✗ | iii |
| 5 | Fully ablated | ✗ | ✗ | ✗ | The state as a whole |
| 6 | Shuffled | ✗ | ✗ | ✓ | Any slow signal vs *this* signal |
| 7 | Parameter-matched baseline | — | — | — | Capacity |

Then name the decisive comparison explicitly in the text: *if condition 2
matches condition 1, the contribution claimed does not exist, regardless of how
condition 5 performs.* Four corners plus three edges estimates each main effect
without running a full 2³ at every seed budget.

### Is the predicted signature operationalised?

"Structured degradation rather than uniform decline" is unfalsifiable as
written — almost any result can be narrated as structured afterwards. Each
predicted effect needs a statistic fixed in advance, and adjacent fields usually
already have one. Computational neuroscience and computational psychiatry are
unusually rich sources, and their model-fitting methods apply to artificial
agents exactly as to animals:

| Vague prediction | Named statistic |
|---|---|
| "loses risk calibration" | Risk-sensitivity parameter ρ in a fitted mean-variance softmax |
| "fails to disengage" | Perseveration parameter κ in `p(a) ∝ exp(β·Q(a) + κ·1[a = a_{t−1}])`, plus lose-shift probability |
| "learning-rate control fails" | Effective α̂ from a sliding-window delta-rule fit, regressed on true volatility |

Then test *structured vs uniform* with a pre-registered mixed model on
z-scored, sign-aligned metrics: structured degradation is a significant
**Arm × MetricFamily interaction** by likelihood-ratio test. Critically, the
uniform alternative must be supported **positively** — by a TOST equivalence
check against a declared bound — not inferred from a non-significant p-value.

### Is the seed budget derived or asserted?

"Ten seeds is a defensible budget" is a convention, not a power analysis.
Declare a **minimum effect size of interest** before running, then justify the
budget against it by bootstrap simulation: resample a pilot score matrix with a
synthetic shift δ applied to the treatment arm, and find the smallest δ whose
95% interval excludes zero in 80% of replicates. Pre-commit to the rule that if
the pilot cannot resolve the declared effect, the budget increases or the
experiment does not run.

### Do proposed criteria contain feedback loops?

Check any self-referential rule for circularity. A criterion like *discard data
once the slow model predicts it* sounds principled until you notice the slow
model is **trained on what was retained** — so the retained set drifts toward
whatever the model finds hard, which is where label noise concentrates. That is
the exact pathology the same document criticised in other methods.

When found, do not delete the idea. Specify mitigations as part of the design
(an exempt randomly-sampled fraction; requiring stability across k passes) and
**promote the failure mode to a primary measured outcome** so the experiment
detects it rather than assuming it away.

### Reproducibility: could someone else run this?

Design documents routinely specify controls carefully and leave the mechanism
unimplementable. Every one of these must be pinned down, and their absence is
easy to miss because the prose reads as complete:

```
the input map g          exact form, inputs, how normalised
the setpoint             fixed / learned / annealed, and its bounds
the time constant τ      SWEPT and reported in full, never assumed —
                         it determines whether the claim is even about
                         the timescale you say it is
gate placement           pre/post nonlinearity, per-layer or global,
                         and the bound that keeps it sane
architecture + capacity  layer counts and widths, so "parameter-matched"
                         is implementable
```

For a timescale claim specifically, sweeping τ turns a guess into evidence:
predict an interior optimum, and state that its absence is evidence against the
thesis.

### Second pass: cite locations, and check the front matter

Review a second time recording section and line numbers. Mechanical checks that
repeatedly find real defects:

```bash
grep -n '§' doc.md | grep -vE '§[0-9]+(\.[0-9]+)?'   # refs to renamed sections
grep -niE 'four roles|five roles|three conditions'   # counts stale after edits
```

Counts and cross-references go stale whenever a section is cut or merged — the
abstract said "five distinct roles" after the cut that reduced it to four, and
a table still pointed at a `§Method` that had been merged away.

### A changed verdict invalidates every section that cited it

Counts and cross-references are the *easy* staleness class, because they are
greppable. The damaging one is a **verdict that changed in one section while
the sections depending on it kept the old ruling.** Those read as the document
contradicting itself, and no mechanical check finds them.

When a review or a correction pass flips any mechanism from rejected to adopted
(or the reverse), four downstream sites need revisiting in the same pass:

```
abstract tally          "four supported, three not" — recount, and check the
                        two-outcome framing still fits; a partial verdict
                        often needs a third category
open-problems section   an entry asserting "no evidence exists for X" directly
                        contradicts a newly-cited result for X
evaluation table        a newly-adopted mechanism with no test row is a claim
                        the document never proposes to check
section title           still naming the old verdict or the old terminology
```

All four fired in the worked example after microglia moved from a flat
rejection to "pruning not adopted, one mechanism retained." The open-problems
entry was the worst: it stated no glial mechanism had demonstrated benefit at
scale, while the mechanism section two pages earlier cited benchmarked results.

The check is to search for the mechanism's *name* rather than for the stale
phrasing, since the stale phrasing is what you are trying to find:

```bash
grep -niE 'microglia|astrocyte' doc.md | grep -viE '^\s*\|'   # prose mentions
```

Then read each hit against the current verdict table. This is a read, not a
grep — which is why it needs to be a deliberate pass rather than a reflex.

### Reconcile source-domain units with target-domain units

A cross-domain document argues in the **source** field's units and specifies
experiments in the **target** field's units. The two are usually never
connected, and the gap is invisible because each section is internally
consistent.

The worked example argued throughout that the missing timescale band is
`0.1–10 s`, because that is how the biology is measured. The methodology then
swept the time constant over `{10 … 3000}` **inference steps**. An artificial
system has no intrinsic conversion between wall-clock seconds and inference
steps, so nothing in the document licensed the correspondence its own argument
depended on.

State the claim as a **ratio within the target domain**, and say explicitly
that the absolute correspondence is not claimed:

> The useful τ should be one to three orders of magnitude longer than the
> recurrent state's effective memory and substantially shorter than a training
> run. That ratio is what the biological argument supports, and it is what the
> sweep measures. Any correspondence to literal seconds is coincidental and is
> not claimed.

This converts an unstated assumption into a testable prediction, and it is
strictly more defensible than the version that quietly equates the two units.

### Check closed loops for amplification, not only circularity

Circularity — a criterion that feeds on its own output (§6c above) — has a
sibling that is easier to miss. Where the proposed controller takes its input
from a signal the controller itself influences, a **systematic miscalibration
can be amplified rather than corrected**.

In the worked example the modulatory state was computed from prediction error,
so a persistently overconfident predictor yields a persistently wrong control
signal, and the loop reinforces it. No mechanism in the design detected that
case.

For any proposed feedback architecture, ask: *what happens if the drive signal
is systematically wrong rather than noisy?* Noise averages out; bias does not.
If the design has no detector for the biased case, that belongs in the
unresolved section — it is a real limitation and stating it is cheaper than
having a reviewer derive it.

Where the environment supplies a closed-form optimum, the detector is cheap and
should be specified rather than deferred: track the divergence between the
system's estimate and the analytic one, and report its correlation with the
controller's magnitude. A correlation that grows over training is the
amplification signature. Say explicitly that detection is only possible because
this environment has a tractable ground truth, and that the failure would be
invisible in a realistic deployment — a monitored limitation is not a solved
one.

### A closed loop needs a stability argument, stated

Amplification of bias is one failure of a feedback design; **oscillation is the
other**, and a proposal that introduces a loop without addressing it is
incomplete. Trace the cycle explicitly in the document:

```
absolute prediction error → arousal → precision on the value head
                                    → value estimate → prediction error
```

Written out, the risk is obvious: raising precision in response to surprise can
produce more surprise. Name the properties that bound it — a saturating
nonlinearity capping the drive term, a decay rate that dominates when
unsaturated, a gain coefficient keeping loop gain below unity in the linear
regime — and then **say they are design arguments, not proofs**.

Two moves make this credible rather than hand-waving. Fold stability into a
sweep you are already running: the loop is least damped at the smallest time
constant, so instability should appear at one end of the τ sweep and vanish as
τ grows, which makes the sweep a stability test at no extra cost. And commit in
advance that **divergence or oscillation is reported as a result rather than
tuned away** — a mechanism requiring careful damping to avoid oscillating is a
weaker proposal than one that does not, and concealing that is the failure mode.

### Check that architectural guarantees actually hold

Design documents assert guarantees in the form "*this cannot happen because the
architecture prevents it*". These are worth re-deriving, because the assertion
is usually written while designing the mechanism and never re-checked against
the final input list.

The worked example claimed the control variable was **not self-writable** —
criterion 4 in §2 — on the grounds that its input map receives no action and no
policy output, with a stop-gradient on the path from the policy loss. Both
true. But two of the four inputs were temporal-difference errors, which are
functions of the value head, which is part of the agent. The stop-gradient
blocks the *gradient* path; it does not block the *functional* one.

The claim had to weaken to what was actually enforced: the agent cannot
optimise the variable directly, but can influence it indirectly through its own
estimates. That is a smaller guarantee, and stating it accurately costs
nothing — particularly when, as here, the residual channel is already
measurable by an existing metric (a system exploiting it would drive the
variable away from the analytic optimum, which the tracking correlation
detects).

The general check, for every "cannot be gamed / cannot diverge / is guaranteed"
sentence in a design document:

```
claimed guarantee    what is asserted to be impossible
enforcement cited    the specific mechanism said to enforce it
inputs traced        does EVERY input to that mechanism sit outside the
                     thing being constrained?
```

Trace the actual input list rather than re-reading the justification. Gradient
barriers, stop-gradients and detachment operations are the common source of
over-claiming, because they genuinely block one channel and it is easy to
write as though they blocked all of them.

### Report the review honestly

Recommendation, blocking issues first, each with a location and a required
revision. Separate **blocking** from **moderate** from **minor**, and state
which findings would make the programme produce an uninterpretable result
versus merely a weaker one. A review that lists twenty equal-weight nitpicks
has not prioritised; the user needs to know which two items must be fixed
before anything is run.

Also state what held up. In the worked example the negative results, the
mandatory-baseline choice, and a striking concession that a favoured mechanism
"confers no capability advantage" were genuine strengths, and saying so made
the blocking findings land rather than read as hostility.

Full review structure, findings and the applied revisions:
`references/design-document-peer-review.md`.

---

## 7. Shipping it: the rendered artifact is the deliverable

A document that is correct and unreadable has not been delivered. Verify the
*rendered* output, not the source you wrote.

### Do not hard-wrap prose destined for a converter

Markdown hard-wrapped at 78 columns reads well in a terminal and can shatter on
conversion: a converter that emits one paragraph per source line turns every
wrap point into a paragraph break. On a phone this is unreadable — sentences
fragment mid-clause, every few words.

Either leave prose paragraphs as single long lines, or make the converter
reflow. Reflow is the better fix since it survives future documents — accumulate
consecutive non-blank lines into one paragraph, breaking only at blank lines and
genuine block starts:

```python
# stop at any line that begins a different block type
if (cur.startswith("#") or cur.startswith(">") or cur.startswith("```")
        or cur.startswith("|") or (cur.startswith("---") and len(set(cur)) == 1)
        or re.match(r"^[-*+]\s+", cur) or re.match(r"^\d+\.\s+", cur)):
    break
```

**Fix reflow in every block type, not just paragraphs.** The same line-by-line
assumption usually appears in the list handler, where it is easier to miss: a
loop that consumes only lines matching `^[-*+]\s+` exits at the first wrapped
continuation, closes the list, and emits the orphaned text as a *paragraph*.
The visible symptom is a continuation rendering at the wrong indent level
rather than merely breaking — the text is no longer a list item at all.

```python
def _collect_item(strip_re):          # one item + its continuation lines
    parts = [re.sub(strip_re, "", lines[i].strip())]
    j = i + 1
    while j < len(lines) and lines[j].strip() and not _BLOCK_START(lines[j].strip()):
        parts.append(lines[j].strip()); j += 1
    return " ".join(parts), j
```

After fixing paragraphs, immediately audit every other handler that steps
`i += 1` per line. Blockquotes usually already join; headings are single-line by
definition; lists almost never are. Fixing one and shipping means the user finds
the next one.

**Paragraph indentation follows the academic convention, not blanket
indentation.** First paragraph after a heading sits flush; continuation
paragraphs take a first-line indent (24pt works well). The indent marks
continuity, so applying it after a heading is redundant — the heading already
signals a new section. Implement with a `prev_was_para` flag reset by *every*
block type that interrupts a run (heading, list, table, fence, blockquote,
rule), and verify all six cases:

```
flush    first paragraph after a heading
INDENT   second consecutive paragraph
flush    paragraph right after a list
INDENT   next one after that
```

**Code blocks must keep their hard line breaks** — equations and snippets are
the one place where per-line output is correct. After any reflow change, test a
document containing every block type and count what survived:

```
paragraphs   3  (was 8 — reflow worked)
list items   2  ✓
table cells  4  ✓
code lines   2  ✓   ← must NOT reflow
blockquote   ✓
```

### A character count cannot detect a formatting failure

`verified_chars` and similar length checks reported success on the broken
version and the fixed one **identically**, because reflowing changes no
characters. Length checks catch truncation; they are blind to structure.

Verify by exporting the live artifact and reading a real paragraph:

```bash
# export the published doc as plain text, then look at actual prose
drive download DOC_ID --export-mime text/plain --output /tmp/live.txt
```

Then read the first paragraph of the abstract. One flowing block means it
worked; fragments mean it did not. This is the same lesson as §5a in a different
register — **a check that passes on both the broken and the working version is
not a check.**

### When the tool is at fault, fix the tool

If the defect is in a shared converter rather than this document, patch the
converter. Every future document inherits the fix, and previously-published
documents correct themselves on their next sync. Note in your reply which other
deliverables were affected.

**Fix the class, not the instance.** A rendering defect found in one block type
almost always exists in the sibling handlers written the same way. The user
reported paragraph fragmentation, it was fixed, the document shipped — and the
identical bug in list items came back in the next screenshot. When a fix lands,
grep the converter for the same pattern elsewhere *before* re-uploading:

```bash
grep -n 'i += 1' converter.py      # every per-line stepper is a suspect
```

This is cheaper than a second round-trip and avoids spending the user's review
attention on a defect already diagnosed.

If the converter lives in a protected or bundled skill, the code fix still
applies — but record the lesson in a skill you own, and say so.

---

Domain findings from the brain-inspired AI review — glial mechanisms, the
neuromodulator-to-variable mapping, affect criteria, vision and continual
learning, with verified citations — are in
`references/brain-inspired-ai-review.md`.

Implementable mechanistic detail for that domain — predictive coding equations,
active-vision options, the continual-learning eviction survey, and the
three-factor plasticity rule, each with a BUILD TODAY / RESEARCH PROBLEM
verdict — is in `references/brain-inspired-ai-mechanisms.md`.

Primary-source corrections to widely-repeated neuroscience and cognition figures
— mental rotation, aphantasia, glia:neuron ratio, astrocyte coverage, BTSP and
dopamine timescales — are in `references/verified-claim-corrections.md`. Check
it before quoting any of those numbers; several common versions are wrong.

The novelty landscape for persistent/adaptive state in ML — fast weights, SSMs,
test-time training, Titans, retrieval, hypernetworks, neuromodulation-inspired
work, with the qualified claim that survives them — is in
`references/medium-timescale-state-survey.md`.

Concrete benchmarks, threatening baselines, metrics and statistical practice for
specifying an ML methodology section — associative memory capacity,
non-stationary RL, predictive coding, delay learning, continual learning — are
in `references/ml-experiment-benchmarks.md`. Use it to name real benchmarks
instead of writing "evaluate on standard benchmarks." It also carries the
drifting-vs-resampled distinction that determines whether a non-stationary
environment tests a persistence claim or inverts it.

A full worked adversarial review — the blocking findings, the revisions that
resolved them, and the stale-edit defects that structural changes leave behind —
is in `references/design-document-peer-review.md`. Read it before reviewing a
design document, and before shipping one.

After all substantive revisions and immediately before delivery, run the
post-revision consistency pass in `references/post-revision-consistency-pass.md`.
It is a different check from peer review — review asks whether the argument is
sound, this asks whether the document still says one thing — and in the worked
example it found six defects in a document that had already passed review,
including an open-problems entry flatly contradicting a result cited two pages
earlier. It carries a copy-paste checklist.
