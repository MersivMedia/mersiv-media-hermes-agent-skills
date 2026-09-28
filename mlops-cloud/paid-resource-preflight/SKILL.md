---
name: paid-resource-preflight
description: Check account state before provisioning paid cloud.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cloud, cost-control, provisioning, preflight, gpu, verification]
    related_skills: [runpod-pods, modal-serverless-gpu, lambda-labs-gpu-cloud]
    created_by: agent
---

# Paid Resource Pre-flight

A user saying "launch a GPU", "spin up an instance", or "deploy this" is
stating a goal, not authorizing the first API call that matches those words.
This skill covers the read-only verification pass that runs BEFORE any billable
resource is created, on any provider (RunPod, Modal, Lambda, fal, Vercel).

It does not cover how to use any one provider — see the provider skill for
that. It covers what to establish first, and when to stop and ask.

## When to Use

Any request that would create, resume, or scale a billable resource. Triggers:
"launch", "spin up", "rent a GPU", "deploy", "start the instance", "test X on
the cloud box". Also when resuming work on infrastructure from a past session,
where your notes may be stale.

## Prerequisites

Provider credentials already in `hermes-agent/.env` (chmod 600). Read-only API
access is enough for every step here — nothing in this skill spends money.

## Procedure

### 1. Enumerate what already exists

Query running instances/pods/deployments and persistent storage BEFORE
creating anything. The single most common waste: provisioning a second
resource next to one the user forgot was running.

Report, explicitly:
- what is already running, its hourly rate, and its uptime
- current utilization (0% on a running GPU = pure waste)
- cumulative spend so far on the idle resource

Never launch alongside an idle resource without naming it first.

### 2. Disambiguate "our volume" / "the server" / "that instance"

Possessive references are ambiguous on accounts that accumulate resources.
Enumerate and match by name, size, and region — never by memory or assumption.
Your own notes from a previous session are a hypothesis to verify, not a fact:
a note saying a volume holds install A does not mean the account has only one
volume, or that the user means that one.

State which concrete resource ID you matched and why.

### 3. Check stock/quota in the constrained region, not globally

Persistent storage is usually region-locked, permanently. That means the
region is the fixed constraint and the compute must fit it — not the reverse.

Query availability **scoped to the resource's own region**. A global catalog
listing a GPU type says nothing about whether that region stocks it. Read the
per-region price/availability field; a null means no stock.

Check **balance against runway**, not just "above zero". Divide the balance by
(GPU rate + all storage burn) and state the hours it buys. One account had
$2.36: enough for about an hour on the only suitable GPU, and — counting the
account's continuous volume billing — only a few days before volumes risked
deletion at a zero balance. A setup that runs past the runway dies mid-download.
Ask for a top-up with a concrete amount before creating anything.

### 4. When the request is not satisfiable, stop and lay out the options

If the requested hardware is unavailable where the data lives, do not silently
substitute, and do not launch the wrong thing in the right region or the right
thing in the wrong region. Both are waste.

Present the real fork with live prices:
- what IS stocked in the data's region, with rates
- what it would take to move the data (scope it as its own job — moving 100GB+
  across regions is never a side effect of "launch a GPU")
- the already-running resource, if it can do the job

Then let the user choose. This is the point of the whole pass.

### 5. Verify the target artifact before renting time to test it

Before paying to "test model X", confirm on disk that X exists, and that it
does the task named. Inspect weights, custom nodes, and workflow/blueprint
filenames. Model and feature names drift between what a user remembers and
what was installed; two adjacent capabilities may both be present with only
one wired up. Confirm the interpretation before spending.

## Pitfalls

- **Treating the verb as the authorization.** "Launch a GPU" is a goal. If the
  account state contradicts it, surface the contradiction — the user usually
  did not know.
- **A stale note used as ground truth.** Re-query; accounts change between
  sessions, including by the user's own hand.
- **Global availability read as regional availability.** The failure mode is a
  pod that will not start, or one that starts with none of the data attached.
- **Silently downgrading hardware.** If they asked for a specific GPU and it
  is unavailable, that is information they need, not a detail to smooth over.
- **A fallback loop that creates the first thing that succeeds.** Looping over
  GPU types and breaking on the first successful create is an automated
  silent substitution. One session quoted an RTX PRO 6000 at $2.09/hr, got
  "no instances available" on all three variants, and the loop created an H100
  at **$3.49/hr** — 67% over the agreed quote, with no check-in. Before any
  fallback create: stop, report the failure and the next option's live rate,
  and get a yes. Only automate fallback within a price ceiling the user named.
- **Stock status is not reservable capacity.** GraphQL showed the RTX PRO 6000
  as `Low` stock in the volume's region, and the create call still returned
  `There are no instances currently available`. "Low" means "maybe" — tell the
  user the quoted card may not materialise before they plan around it.
- **Resizing persistent storage is also a spend decision.** Growing a volume
  adds recurring monthly cost and can never be shrunk back. Quota headroom is a
  preflight check (compare `du` to size before a big download); if it needs
  growing, ask with the new monthly figure rather than PATCHing mid-setup.
- **A user top-up is not blanket authority.** "I topped up, go ahead" authorises
  the plan as quoted — hardware, rate, storage. Any deviation discovered after
  (different GPU, bigger volume, different quantisation because of the GPU
  swap) goes back to the user before it is executed.
- **Quoting a price without reading back the actual rate.** Report the rate
  the API returns on the created resource, and flag when an existing resource
  is billing above the current going rate.
- **Ignoring an idle running resource** because the new request felt like a
  fresh start. Check utilization; 0% for hours is the signal.
- **Oversized inline shell payloads get hard-blocked.** Long one-liner `curl`
  + GraphQL invocations trip the command parser blocklist. Write the probe to
  a real script file and run that instead — it is also reusable.

## Reference

`references/runpod-preflight-queries.md` — the exact read-only GraphQL queries
for the RunPod inventory / region-stock pass, with a worked example.

`references/runpod-volume-inspection-and-bringup.md` — inspecting an existing
volume (S3 prefix walks, first-boot SSH checks, testing venvs), quota checks
before large downloads, the huggingface_hub<2.0 pin, quantisation-follows-GPU,
and handling API keys on a rented pod.

## Verification

Before any create call, you should be able to state in one line each:
the target resource ID, its region, the chosen instance type, the confirmed
hourly rate, and why no already-running resource serves the purpose. If any
of those is a guess, you have not finished the pre-flight.

On teardown, report actual spend against the estimate.
