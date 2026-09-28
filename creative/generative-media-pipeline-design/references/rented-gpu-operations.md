# Renting GPU hardware for a media pipeline

When a hosted API cannot reach the required fidelity (see
`audio-remix-and-stems.md` §2 for how that gets discovered), the fallback is
renting a GPU by the hour. This file covers the operational traps — measured on
RunPod, but most generalise to any provider that rents containers.

Load this **before** creating any pod, not after the first one misbehaves.

---

## 1. Decide whether to rent at all

Rent only when both are true:

- no hosted API serves the model, **or** the hosted route has a proven quality
  ceiling below what the work needs
- the local box genuinely cannot run it

Local synthesis is free and instant; a hosted API call is cents; a pod is
dollars per hour plus setup time plus ongoing storage. Work up that ladder, not
down it. A restyle that can be prototyped locally in numpy should be, before
any hardware is booked.

### 1.0 First confirm the model HAS weights — many flagships never will

Before any VRAM arithmetic, answer a prior question: **can this model be
self-hosted at all?** A large share of the best-performing video models are
API-only. They have no Hugging Face checkpoint, no weights download, no local
inference path — and no GPU you rent will ever run them.

Measured: a request to "install the latest Seedance and set up ComfyUI
workflows" on a freshly rented L40S. Every Seedance version (1.0 Pro/Lite,
2.0, 2.5) is hosted-only. The ComfyUI "Seedance workflows" that show up in
search are real, but they are **API nodes that call a remote endpoint and bill
per generation** — they load nothing onto the card. The pod was already
running and billing before this was checked.

The tell is in the vendor's own materials: a page offering "Try Now" and "Get
API" with no weights link is an API-only model, however open the ecosystem
around it looks. Third-party ComfyUI node packs (MuAPI-style bridges) make it
*appear* self-hostable because they install into ComfyUI like any other node.
They are network clients.

Cheap disambiguation before committing hardware:

```bash
# Does a real weights repo exist? (files + sizes, not just a landing page)
curl -s -H "Authorization: Bearer $HF_TOKEN" \
  "https://huggingface.co/api/models/<org>/<repo>" | jq '.gated, (.siblings|length)'

# Is it served as a hosted API instead?
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $REPLICATE_API_TOKEN" \
  "https://api.replicate.com/v1/models/<owner>/<name>"
```

Both answers are useful and they are not exclusive. The routing rule:

| Weights exist? | Hosted API? | Rent a GPU? |
|---|---|---|
| no | yes | **No** — call the API from the local box; a pod adds cost and zero capability |
| yes | yes | Only if the hosted route has a measured ceiling (fidelity, rate limit, cost at volume) |
| yes | no | Yes — this is the real case for renting |

State the verdict *before* creating the pod. Discovering it afterwards means
the meter has been running on a machine that was never going to help, and the
honest report is an admission rather than a status update.

Corollary: "the latest <model>" in a user request is a capability ask, not a
deployment instruction. When the named model turns out to be API-only, say so
plainly and offer the equivalent open-weights model for the GPU track — the
two can run in parallel, one per surface.

**Verify VRAM against the actual model size, not the model's reputation.** An
int8 3B audio model needs ~6 GB; a 24 GB card is already generous and a 48 GB
card is waste. Sum the real weight files before picking a tier:

```bash
curl -sIL "https://huggingface.co/<repo>/resolve/main/<file>" \
  | grep -i '^content-length'
```

One measured example came to 5.93 GB across four files, against an initial
assumption that an A100-class card was the floor. The assumption came from a
third-party wrapper's README; the actual packaged build was far lighter.

---

## 2. SSH keys must be injected AT CREATION

The single biggest time-waster. Registering a public key on the account
afterwards does **not** grant access to an already-running container, and a
stop/start cycle does **not** re-inject it. The key material is baked in when
the container is first built and never revisited.

```bash
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -C "agent" -f ~/.ssh/id_ed25519 -q
```

Pass it in the create body:

```python
"env": {"PUBLIC_KEY": open(os.path.expanduser("~/.ssh/id_ed25519.pub")).read()}
```

Assert the create response shows the key landed before waiting on the pod. If
SSH returns `Permission denied (publickey)` on a pod you just made, the key was
missing at creation — **terminate and recreate** rather than trying to repair
it in place. With persistent storage attached this costs two minutes and
nothing else.

Connect on the *mapped* port, not 22:

```bash
ssh -o StrictHostKeyChecking=no -p "$(jq -r '.portMappings["22"]' pod.json)" root@"$IP"
```

---

## 3. Quoted price is not billed price

A GPU listed at one rate can bill at another because listings aggregate across
tiers. Measured: a card quoted `$0.34/hr` created at **`$0.74/hr`** because an
unconstrained create landed on the secure tier rather than the community tier.

Read the real rate off the create response (`costPerHr`, and whatever flag
names the tier) and **say it out loud** rather than repeating the quote.

**Do not silently re-optimise this.** The correction received on this point:

> *"Why community cloud? I don't think the difference in price is so bad, I'll
> pay, just set it up properly so I can access it from my phone or computer."*

Reliability and access beat a rounding error. Quote both tiers, default to the
reliable one, and let the user choose. Raise cost as a *decision* only when it
is material — long jobs, large GPUs, many hours — not when the delta is cents.
The same judgement applies to storage: a few dollars a month to avoid
re-downloading gigabytes every session is obviously worth it, and is not worth
a paragraph of deliberation.

---

## 4. Only the mounted volume survives

The container filesystem is destroyed on termination. Everything that took time
to build must live on the network volume, conventionally `/workspace`:

- clone repos to `/workspace/<project>`
- create the venv **inside** `/workspace` — a `pip install` into system Python
  is gone next session
- point every model cache at it: `export HF_HOME=/workspace/hf`

Forgetting `HF_HOME` is the subtle one: the install persists, the multi-GB
weights do not, and the next session silently re-downloads them. That defeats
the entire reason for paying for the volume.

Volumes are **datacenter-locked** — a pod can only mount one in its own region.

A volume also bills **continuously**, whether or not a pod exists. It is the
cost that outlives the session, so it is the one to mention at teardown.

### 4.1 Global stock is not per-datacenter stock — run the probe

This is the one irreversible decision in the whole workflow, and an earlier
version of this file covered it in a single sentence that was read, agreed
with, and then *still* got the recommendation wrong. The prose was not enough;
use `scripts/dc_stock.py`.

The measured trap: the global GPU list reported **A40 48 GB at `High` stock**,
the only card above `Low` anywhere. A per-datacenter sweep of all thirteen
volume-capable regions found A40 in **none** of them. Creating the recommended
volume would have locked 100 GB into a region where no pod can ever attach it —
billing ~$7/month forever for storage that cannot be used.

Worse, the specific region recommended from the global reading (`US-CA-2`) had
**zero GPUs of any size in stock**, not merely a missing A40.

```bash
set -a; . ~/.hermes/.env; set +a
python3 scripts/dc_stock.py --min-vram 48
```

Read the output as a filter, not a ranking: any datacenter printed under
`NO STOCK` is disqualified from holding a volume regardless of how attractive
its latency or price looks. Expect most regions to be empty and nearly every
surviving row to read `Low` — that is the normal state, and it means a create
call can fail and need a retry or a fallback card. `Low` is workable; absent is
not.

Sequence that avoids the stranding: **probe per-DC → pick a DC with stock at
your VRAM tier → create the volume there → create the pod.** Never the reverse,
and never from the global list.

### 4.2 Latency matters when the deliverable is a screen recording

Region choice is usually a rounding error, because a batch job does not care
whether it started 150 ms later. It stops being a rounding error when the user
is going to **drive the UI on camera** — portfolio reels, demos, tutorials,
anything where the recording itself is the artifact.

Every node drag and menu click pays the round trip. From the US west coast,
a European region costs ~160–190 ms per interaction and reads on video as
hesitation on the operator's part, not as network lag. A US region lands nearer
~45 ms, which does not.

So when the purpose is a recording, rank candidate datacenters by **stock
first, then proximity to the user, then price** — and say the latency number
out loud during the decision, because it is the one factor the user cannot see
in a price table. An SSH tunnel (§5) removes the proxy hop and helps, but it
cannot shorten the physical distance.

This also reframes reusing an existing volume: a volume already sitting in a
far region is free, but if the session's output is footage, the saved
storage fee buys visibly worse material.

### 4.3 urllib is 403'd by the RunPod GraphQL endpoint

`api.runpod.io` user-agent-filters Python's default client, so
`urllib.request.urlopen` returns **HTTP 403 Forbidden** on a perfectly valid
authenticated query. The key is not wrong and the query is not malformed.

Use `curl` (via `subprocess`, as `dc_stock.py` does) or any client that sends a
conventional user agent. Do not "simplify" a working curl-based probe back to
urllib. The same filtering behaviour affects other media-pipeline providers —
see `video-generation-providers.md`.

---

## 4.4 Size the download against the volume BEFORE fetching

A modern open video model ships every variant in one repo, and the total
routinely exceeds the volume you provisioned. Measured on `Lightricks/LTX-2.5`
(22B, open weights, gated): **201 GB of files against a 100 GB volume.** Naive
"clone the repo" or `snapshot_download` fills the disk and fails partway.

Enumerate with sizes first — the HF tree API gives LFS sizes without
downloading anything:

```bash
curl -s -H "Authorization: Bearer $HF_TOKEN" \
  "https://huggingface.co/api/models/<org>/<repo>/tree/main?recursive=true" \
| python3 -c "
import json,sys
rows=[((f.get('lfs') or {}).get('size') or f.get('size') or 0, f['path'])
      for f in json.load(sys.stdin) if f.get('type')=='file']
for s,p in sorted(rows, reverse=True):
    if s > 1e6: print(f'{s/1e9:8.2f} GB  {p}')
print(f'TOTAL {sum(s for s,_ in rows)/1e9:.2f} GB')"
```

Then pick **one** of each role rather than mirroring the repo. The recurring
axes:

| Axis | Options | Pick |
|---|---|---|
| precision | bf16 / int8 / nvfp4 | int8 unless quality is the deliverable — roughly halves size |
| variant | `dev` vs `distilled` | **distilled** for demos: far fewer steps per clip |
| encoder | full vs quantized text encoder | match the transformer's precision |
| extras | VAEs, upscalers, LoRAs, duration heads | small, take them all |

Taking one transformer instead of both, at int8 instead of bf16, took that
201 GB repo to a ~50 GB working set with half the volume still free.

**`distilled` is the right default whenever the output is a screen
recording.** A dev-variant clip that needs many more sampling steps turns a
demo into minutes of progress bar. This is the same §4.2 reasoning — when the
artifact is footage of the tool being used, wall-clock per action is a quality
attribute, not an efficiency detail.

### Gated repos need a token, and `gated: auto` is not a wait

Most frontier open-weights repos are gated. Check access *before* building any
fetch plan — the failure mode is a 401 halfway through a long download:

```bash
curl -s -H "Authorization: Bearer $HF_TOKEN" \
  "https://huggingface.co/api/models/<org>/<repo>" | jq '.gated'
```

`gated: "auto"` means access is granted automatically on token presentation —
no human approval delay, despite "gated" sounding like a queue. `gated: manual`
does mean waiting on the publisher, and that is a genuine blocker to surface to
the user immediately rather than discovering at fetch time.

Never pass the token on a command line that gets logged or echoed. Write it to
`.env` (chmod 600) locally and to a `umask 077` file on the pod, then read it
in the fetch script:

```bash
export HF_TOKEN="$(cat /workspace/.hf_token)"
export HF_HUB_ENABLE_HF_TRANSFER=1     # materially faster on multi-GB files
```

Fetch file-by-file with `hf_hub_download`, skipping anything already present,
so an interrupted pull resumes instead of restarting. ComfyUI expects weights
sorted into `models/{diffusion_models,text_encoders,vae,loras,model_patches,
latent_upscale_models}` — the HF repo's own directory names usually match, but
confirm rather than assume.

---

## 5. Reaching the service

Providers proxy exposed HTTP ports on a predictable hostname:

```
https://<pod-id>-<port>.proxy.runpod.net
```

Declare ports at create time — they cannot be added later. Two requirements:

- bind the app to `0.0.0.0`, never `127.0.0.1`, or the proxy sees nothing
  (Gradio needs `--listen`)
- prefer the proxy to a custom port plus firewall rules; it is HTTPS on a
  standard port, which is what survives mobile networks and phone browsers

This directly answers "so I can access it from my phone or computer" — a URL is
the deliverable, not an SSH command.

### The proxy is unreliable for websocket apps

The page loads, renders, and then shows a reconnect loop. Reported verbatim:

> *"Connection to server lost. Reconnecting…"* — appearing seconds after the UI
> painted, on a server confirmed `LISTEN` on `0.0.0.0:7860`.

The HTTP handshake succeeds and the websocket upgrade does not, so every
server-side check passes: the port is bound, the process is alive, `curl`
returns the page. Nothing local is wrong, and debugging the app is wasted time.

**Use the framework's own tunnel instead.** Gradio's `--share` prints a
`https://<hash>.gradio.live` URL that connects straight to the pod, bypassing
the proxy, and works on mobile:

```bash
python -u app.py --listen --server-port 7860 --share
grep -oE "https://[a-z0-9]+\.gradio\.live" /root/app.log | tail -1
```

Hand that over as the primary link and keep the proxy URL as a fallback. Share
links expire (one week for Gradio), so say so. For non-Gradio services the
equivalent is any reverse tunnel — the principle is that a provider HTTP proxy
is fine for request/response and should not be trusted for a live socket.

---

## 6. Install in the background, report real progress

A framework install is 10–25 minutes of torch plus requirements. Run it as a
background process with completion notification rather than a foreground call
that will hit a timeout.

SSH output buffers, so a local log may look empty while the remote is working.
**Poll the pod directly** for ground truth rather than trusting an empty log:

```bash
ssh ... 'echo "venv: $(du -sh /workspace/*/venv | cut -f1)";
         echo "pkgs: $(ls /workspace/*/venv/lib/python*/site-packages | wc -l)";
         echo "pip:  $(pgrep -c -f "pip install")"'
```

Growing package count and a live pip process distinguish "slow" from "hung" —
without that, an idle-looking log invites a destructive restart of work that
was fine.

---

## 6.5 Running a long-lived service on the pod

Four independent failure modes converge here, and they all present as the same
symptom: an empty log and a service that never comes up.

**`nohup … &` over SSH dies with the session.** Use tmux, so the service
survives disconnects and its live screen can be read back:

```bash
apt-get install -y -qq tmux
tmux new-session -d -s app \
  "cd /workspace/proj && ./venv/bin/python -u app.py --listen 2>&1 | tee /root/app.log"
tmux capture-pane -t app -p | tail -20     # ground truth, even if the log lags
```

**Do not write logs to the network volume.** `/workspace` is a distributed
mount (MooseFS here). Append-heavy writes to it are unreliable — a log observed
at 3207 bytes vanished entirely between two reads. Logs belong on `/root` or
`/tmp`; the volume is for weights and installs.

**`python -u` is mandatory.** Without it stdout buffers and the log stays at
zero bytes while the process works normally, which is indistinguishable from a
hang and invites exactly the wrong intervention.

**Budget ~3 minutes of silence on first launch.** Large ML apps load CUDA
kernels, inject quantization kernels, and fetch tunnel binaries before printing
a single line. An empty log at 60 seconds is not yet evidence of failure.

### `pkill -f <script>` kills your own shell

A self-inflicted trap worth naming, because it produces bizarre evidence. The
pattern matches the command line of the SSH session running it, so the shell
kills itself mid-command. The visible result is several diagnostics returning
completely empty output — which reads as "the remote is broken" rather than
"I shot the messenger".

Use a bracket to exclude the matcher from its own match:

```bash
pgrep -af "[a]pp.py"      # lists the service, not this shell
pkill    -f "[a]pp.py"
```

Same reason a file written by the killed shell never appeared: the redirect
died with it.

---

## 6.6 When the app runs but generation crashes

Three traps that all present as "my config fix did nothing".

### The error label names the wrong subsystem

Apps with one shared generation entry point label every failure with whichever
subsystem is most common. A music model reported a **video generation error**
because both routes funnel through the same `generate_media()` call.

Never debug from the UI's label. Pull the real traceback off the server and
read the bottom frame:

```
RuntimeError: No compatible Triton convrot configuration for shape=(1,2048,2048)
  shared/kernels/quanto_int8_triton.py:733
```

That names a quantization kernel. Nothing to do with video.

### Fused int8 kernels are shape- and GPU-specific

Quantized builds ship hand-tuned Triton configs for a fixed set of matmul
shapes. Hit an untuned shape on an untested card and the kernel **raises rather
than falling back**. This is not a bad install; the weights are fine.

The fix is to stop using the fused int8 path — both the kernel flag *and* the
weight variant, since int8 weights re-enter the kernel regardless of the flag:

```python
d["enable_int8_kernels"] = 0
d["transformer_quantization"] = "bf16"
d["text_encoder_quantization"] = "bf16"
```

Back the config up first. Cost is memory: bf16 roughly doubles resident weights
(~6 GB → ~11 GB here), which is precisely why the VRAM headroom from §1 is
worth keeping rather than sizing to the exact int8 figure.

### A persisted queue replays the crash on every boot

Apps that autosave failed work (`error_queue.zip`, job DBs) reload it at
startup, so the same task crashes again immediately and a correct config change
looks ineffective. Quarantine rather than delete — the payload is evidence:

```bash
mkdir -p /root/quarantine && mv -f error_queue.zip /root/quarantine/
```

### Before concluding a fix failed

A failed restart leaves the previous log in place, and reading it produces a
confident wrong conclusion — observed here across three cycles, compounding
with the `pkill` self-kill above. Prove the output is fresh:

```bash
wc -c /root/app.log; stat -c '%y' /root/app.log   # newer than the restart?
rm -f /root/app.log                                # or just clear it first
tmux ls                                            # session gone == died
```

Also re-read the config **off disk** and print the changed key. A change that
never persisted and a change that did not help look identical from the log.

---

## 6.7 Driving a Gradio app programmatically

Tempting once the UI is up, and usually not worth it. Gradio auto-exposes every
handler, but an app that never declared `api_name=` gives you nothing usable:

- endpoint names are autogenerated (`lambda_4`, `_on_upload_2`)
- `/info` may 404 entirely, so there is no name→type schema
- the real generate endpoint took **113 positional inputs**

Positional arguments with no schema means one wrong index silently renders with
the wrong settings and bills GPU time to discover it. `/config` does list every
component's current default, so reconstructing the full payload and overriding
a few fields is *possible* — but state the confidence honestly before spending
on it.

The cheap sequencing: let the user drive one render in the UI, then automate
from the settings that run wrote out. Replaying a known-good payload beats
reverse-engineering an unnamed one.

---

## 7. Teardown discipline

- **stop** halts GPU billing, keeps container disk at a lower rate
- **terminate** destroys everything not on the volume
- an **idle running pod bills the full rate** — there is no auto-shutdown

With a volume attached, terminate freely. When a decision is pending and the
user has not answered, **stop the pod rather than let it idle** — it is
reversible, forecloses nothing, and is the honest default while waiting.

Report actual spend at teardown, not the estimate. Measured here: an estimate
of ~$0.25 against an actual $0.03, because provisioning and restart time was
not fully billed. Quoting the estimate as if it were the charge is a small
dishonesty that compounds.

---

## 8. Checklist

- [ ] Model confirmed to HAVE public weights before any pod is created (§1.0)
      — API-only flagships cannot be self-hosted at any VRAM tier, and a
      ComfyUI node pack for one is a network client, not a local install
- [ ] Hosted API ruled out for a *measured* reason, not assumed
- [ ] Real weight sizes summed; VRAM tier matched to them
- [ ] Repo total sized against the volume BEFORE fetching (§4.4); one variant
      per role chosen rather than mirroring the repo
- [ ] Gated-repo access checked up front — `auto` grants immediately, `manual`
      is a blocker to raise now, not at fetch time
- [ ] Balance checked — a zero balance fails pod creation unhelpfully
- [ ] `scripts/dc_stock.py` RUN before creating any volume — global stock lists
      cards that exist in zero volume-capable regions (§4.1). A prose reminder
      is not enough; run the probe and paste the output.
- [ ] Datacenter chosen by stock first, then user proximity if the session's
      deliverable is a screen recording (§4.2), then price
- [ ] SSH public key present in the create body; presence asserted in response
- [ ] Billed `costPerHr` read from the response and stated, not the list price
- [ ] Repo, venv and model cache all under the mounted volume
- [ ] Ports declared at creation; service bound to `0.0.0.0`
- [ ] Long-lived services under tmux, logging to local disk with `python -u`
- [ ] Websocket UIs handed over on a framework tunnel, not the provider proxy
- [ ] Proxy URL handed over, verified reachable
- [ ] Generation crash diagnosed from the **traceback**, not the UI's error
      label — shared entry points misname the failing subsystem
- [ ] Fused int8 kernel ruled in or out on an unfamiliar GPU; bf16 fallback
      sets the weight variant too, not only the kernel flag
- [ ] Persisted failure queue quarantined before retesting a config change
- [ ] Log freshness proved (byte count + mtime) before concluding a fix failed
- [ ] Pod stopped or terminated when the session ends; actual spend reported
