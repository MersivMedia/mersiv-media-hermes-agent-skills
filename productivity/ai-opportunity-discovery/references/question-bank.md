# Discovery Question Bank

Source pool for Phase 0.5. Never hand the client all of these — select 12-18 that the
desk research could NOT answer, ordered so the meeting flows. Each question below is
tagged with what its answer unlocks downstream.

## Rules for selecting

1. **Delete anything you already researched.** Asking "so what does your company do?"
   burns the credibility you earned by preparing. Instead: "I saw you launched X in
   March — did that change the volume your ops team handles?"
2. **Every question must feed a cell in the opportunity register.** If an answer wouldn't
   change a recommendation or an ROI input, cut it.
3. **Lead with their problems, not your solutions.** No AI vocabulary until they raise it.
4. **Always get numbers.** "It takes a while" is unusable; "about 40 a week, 20 minutes
   each" is an ROI model.
5. **Cap at ~18.** More than that and you're interrogating, not consulting.

---

## A. Operations and workflow (→ pain points, volumes)

- Walk me through what happens from the moment a {{core transaction}} comes in to when
  it's done. Who touches it?
- Which step in that chain backs up the most?
- What does your team spend time on that you'd be embarrassed to show a customer?
- If you could delete one recurring task from your team's week, what would it be?
- What breaks when volume doubles?
- Which work happens in a spreadsheet or an inbox because no system supports it?
- What do people do the same way every single time, with no judgment involved?
- Where does the same information get typed in more than once?

## B. Volume and cost (→ ROI arithmetic — non-negotiable)

- How many {{units}} per week/month?
- How long does one take, start to finish? Best case and bad case?
- How many people touch it, and at what level (coordinator, manager, specialist)?
- Roughly what's a fully loaded cost for those roles?
- How often does one get done wrong, and what does a redo cost?
- Is the volume seasonal? What does peak look like?
- What's the cost of it being late — SLA penalty, lost deal, churn?

## C. Systems and data (→ feasibility, integration, data readiness)

- What systems hold the data for this work? Which is the system of record?
- Does anything talk to anything else today, or is it copy-paste?
- Who administers {{CRM/ERP}}? Do we have API access, or is it locked down?
- How far back does the history go, and is it clean enough that you'd trust it?
- Is anything still on paper, in scanned PDFs, or in email attachments?
- Are there documents your team searches through constantly? Where do they live?

## D. People and adoption (→ org-readiness score, rollout plan)

- Who on the team would be first to try something new? Who'd be last?
- Has anything been rolled out here that didn't stick? What happened?
- Who has to approve a purchase like this? Who can kill it?
- Is the goal here to grow without hiring, or to free existing people up for other work?
- Would this change anyone's job description? How would that be received?

## E. Constraints (→ architectural gates — ask before Phase 3, never after)

- Any regulatory requirements on this data? HIPAA, PII, financial, contractual?
- Are there restrictions on data leaving your environment or going to a third party?
- Do you have security review requirements for new vendors, and how long does that take?
- Anything in a customer contract that limits how you process their data?
- What's the budget range and the fiscal timing you're working against?

## F. Prior AI exposure (→ expectation calibration)

- Has anyone here tried AI tools already? What happened?
- What have you seen elsewhere that made you think "we should have that"?
- What would make you consider this a failure six months in?
- What are you worried about?

## G. Success definition (→ acceptance metrics in the technical PRD)

- If this works perfectly, what number on a dashboard moves?
- What's that number today?
- Who else has to believe it worked?
- What would you want to see in the first 30 days to keep going?

---

## Closing questions (always ask)

- What haven't I asked about that I should have?
- Who else should I be talking to?
- What's the one thing that would make this a no?

## After the meeting

Log answers straight into `inputs/notes.md` under the question they answer. Mark anything
you asked and did NOT get a clear answer to as `[UNANSWERED]` — those become the open
questions in both PRDs rather than quietly turning into assumptions.
