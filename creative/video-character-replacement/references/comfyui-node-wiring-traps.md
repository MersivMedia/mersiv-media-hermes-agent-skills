# ComfyUI Node Wiring Traps

Every entry here is a real execution failure observed while building a
character-replacement graph. The common cause: ComfyUI's `MODEL` and
`CONDITIONING` types are **generic**. A graph passes queue-time validation
with incompatible tensors wired together and only explodes mid-execution —
sometimes minutes in, after models have loaded.

**Working rule:** the schema tells you the *type*, not the *contract*. Before
wiring a new node into an expensive graph, run it in a tiny throwaway graph
first. A 10-second failure beats a 250-second one.

---

## 1. Wrong model into a pose extractor

```
ValueError: The provided model does not have a heatmap_head.
```

`SDPoseKeypointExtractor.model` needs the **pose** checkpoint
(`sdpose_wholebody_fp16`), which carries the heatmap head. The detector
shipped alongside it (`rt_detr_v4-x-hgnet`) is a *bounding-box* model and
belongs on a `bboxes` input, not here.

Both files ship in the same HF repo, which is exactly why it's easy to grab
the wrong one.

Load the pose checkpoint with `CheckpointLoaderSimple` — it returns
`(MODEL, CLIP, VAE)`, so take `model` from output 0 and `vae` from output 2.
No separate `VAELoader` needed.

---

## 2. Model file in a folder ComfyUI does not scan for it

A SAM3 checkpoint dropped into `models/detection/` was listed by
`GET /models/detection` but appeared in **no loader's dropdown**, so nothing
could consume it.

It actually loads via `UNETLoader`, which means it must live in
`models/diffusion_models/` — same as `rt_detr`.

Diagnostic: `GET /object_info`, then scan every loader's combo options for
your filename. If no loader lists it, the folder is wrong regardless of what
`GET /models/<folder>` says.

```python
for node, info in object_info.items():
    for field, spec in (info.get("input", {}).get("required") or {}).items():
        if isinstance(spec, list) and spec and isinstance(spec[0], list):
            if any("yourfile" in str(o).lower() for o in spec[0]):
                print(node, field)
```

---

## 3. Cross-family conditioning (dimension mismatch)

```
RuntimeError: mat1 and mat2 shapes cannot be multiplied (512x4096 and 1024x256)
```

Wan's `umt5` text encoder emits **4096-dim** embeddings. SAM3's text path
expects **1024**. They are unrelated encoders; the `CONDITIONING` type is
identical so the graph validates fine.

Check `CLIPLoader`'s `type` list before assuming a text encoder is reusable
across families. If there is no entry for the target model family, that node
uses its own internal encoder and its `conditioning` socket is not for your
`CLIPTextEncode` output.

---

## 4. Schema-optional, runtime-required

```
ValueError: Either initial_mask or conditioning must be provided
```

`SAM3_VideoTrack` marks **both** `initial_mask` and `conditioning` optional
in the schema, then refuses to run with neither. Removing the bad
conditioning from trap 3 traded one error for another.

Resolution: seed with `SAM3_Detect`, which accepts either

- `positive_coords` — JSON point prompts, `[{"x": 413, "y": 213}]`, pixel
  coords; or
- `bboxes` — from `RTDETR_detect`, fully automatic on new footage.

Its `MASK` output then satisfies `initial_mask`.

Optional-in-schema means "the node accepts the key being absent," not "the
node works without it."

---

## 5. Output collection: video lands under `images`

`SaveVideo` results appear in the history JSON under the node's **`images`**
list with `"animated": true` — **not** under `videos`.

Collection code checking only `videos`/`gifs` reports a perfectly successful
run as a failure. Always scan all three:

```python
for node_out in (entry.get("outputs") or {}).values():
    for key in ("videos", "gifs", "images"):
        for item in (node_out.get(key) or []):
            ...
```

---

## 6. Reading a stale log as a fresh failure

After a failed relaunch, `tail`-ing the server log shows the **previous**
traceback and is indistinguishable from a new one. Two separate false
diagnoses came from this.

Before every launch: truncate the log (`: > comfy.log`), then confirm the
process is actually alive with `pgrep -af "main.py --listen"`. An empty
`pgrep` plus an old traceback means the launch never started — the traceback
is history, not evidence.

---

## Diagnostic habits that paid off

- Pull `GET /object_info` fresh after any model download or restart; combo
  lists are cached from boot and will not show new files.
- Verify a model registered by calling `GET /models/<folder>` **and** by
  finding it in a loader's options. The first alone is not sufficient.
- ComfyUI validates node types, links, and input ranges at queue time. A
  successful submit (200 + `prompt_id`) proves the graph is structurally
  sound — it proves nothing about tensor compatibility.
- Errors that name the missing component and link the correct repo are worth
  reading in full before theorising.
