#!/usr/bin/env python3
"""Rebuild the MiniMax H3 ref2va workflow for the pipeline (v2).

Changes vs. the supplied graph:
  1. UNET: third-party Eros finetune -> official minimax_h3_ref2va_int8_convrot
  2. LoRA: fl2v turbo (wrong task family) -> ref2v_turbo_4step
  3. Text encoder: nvfp4_awq -> int8_convrot (H100 is Hopper; NVFP4 needs Blackwell)
  4. Hardcoded prompt box -> H3 Prompt Director node
  5. Duration primitive drives the Director so prompt timestamps match frames
  6. ONE character reference, ONE checkbox ("Replace background?"):
       off -> SAM3 cuts the character out onto flat grey, so the reference's
              environment cannot leak into the output
       on  -> the reference is used as-is and its environment replaces the
              source's
     A single ComfySwitchNode feeds BOTH the Director and H3, so the prompt
     always describes the exact image H3 is conditioned on.
  7. Reference mapping:
       ref_image_0 = <Picture 1> = first frame of source video
       ref_image_1 = <Picture 2> = character (cutout or full, per checkbox)
       ref_video_0 = <Video 1>   = source video
     The second LoadImage (old background loader) is removed.
"""
import json
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
wf = json.load(open(SRC))
nodes = {n["id"]: n for n in wf["nodes"]}
links = wf["links"]
state = {"node": wf["last_node_id"] + 1, "link": wf["last_link_id"] + 1}

GREY = 0x808080   # neutral mid-grey backdrop for the cutout
SAM3_MODEL = "sam3.1_multiplex_fp16.safetensors"


def nid():
    state["node"] += 1
    return state["node"] - 1


def link(src, src_slot, dst, dst_slot, typ):
    lid = state["link"]; state["link"] += 1
    links.append([lid, src, src_slot, dst, dst_slot, typ])
    o = nodes[src]["outputs"][src_slot]
    o["links"] = (o.get("links") or []) + [lid]
    nodes[dst]["inputs"][dst_slot]["link"] = lid
    return lid


def unlink(lid):
    for i, l in enumerate(links):
        if l[0] == lid:
            _, s, ss, d, ds, _ = l
            links.pop(i)
            o = nodes[s]["outputs"][ss]
            if o.get("links") and lid in o["links"]:
                o["links"].remove(lid)
            if nodes[d]["inputs"][ds].get("link") == lid:
                nodes[d]["inputs"][ds]["link"] = None
            return


def slot(node_id, name):
    for i, inp in enumerate(nodes[node_id]["inputs"]):
        if inp["name"] == name:
            return i
    raise KeyError(f"{node_id}.{name}")


def add(typ, title, pos, inputs, outputs, widgets, size=(320, 110), mode=0):
    i = nid()
    n = {"id": i, "type": typ, "title": title, "pos": list(pos), "size": list(size),
         "flags": {}, "order": 0, "mode": mode, "properties": {"Node name for S&R": typ},
         "inputs": [dict(x) for x in inputs],
         "outputs": [{"name": nm, "type": t, "links": []} for nm, t in outputs],
         "widgets_values": widgets}
    wf["nodes"].append(n); nodes[i] = n
    return i


H3, VID, CHAR, BG_OLD, OLD_PROMPT = 136, 148, 137, 139, 149

# ---- 1-3. official weights --------------------------------------------------
nodes[127]["widgets_values"] = ["minimax_h3_ref2va_int8_convrot.safetensors", "default"]
nodes[145]["widgets_values"] = ["minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", 1]
nodes[128]["widgets_values"] = ["qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "minimax", "default"]
nodes[92]["widgets_values"][0] = "refswap/h3_refswap"

nodes[VID]["widgets_values"]["video"] = "source.mp4"
nodes[VID]["widgets_values"]["custom_width"] = 0
nodes[VID]["title"] = "Source Video (<Video 1>)"
nodes[CHAR]["title"] = "Character Reference"
nodes[CHAR]["widgets_values"] = ["character.png", "image"]

# ---- strip every existing link into H3's image refs and prompt ----------------
for name in ("ref_images.ref_image_0", "ref_images.ref_image_1", "ref_images.ref_image_2", "prompt"):
    lid = nodes[H3]["inputs"][slot(H3, name)].get("link")
    if lid is not None:
        unlink(lid)

# ---- remove the old background loader entirely ------------------------------
for o in nodes[BG_OLD]["outputs"]:
    for lid in list(o.get("links") or []):
        unlink(lid)
wf["nodes"] = [n for n in wf["nodes"] if n["id"] != BG_OLD]
del nodes[BG_OLD]

# ---- old hardcoded prompt: bypassed, kept for reference ---------------------
nodes[OLD_PROMPT]["mode"] = 4
nodes[OLD_PROMPT]["title"] = "(unused) original hardcoded prompt"
nodes[OLD_PROMPT]["widgets_values"] = ["Superseded by H3 Prompt Director."]

cx, cy = nodes[CHAR]["pos"]

# ---- <Picture 1>: first frame of the source ---------------------------------
ff = add("ImageFromBatch", "First Frame (<Picture 1>)",
         (nodes[VID]["pos"][0] + 420, nodes[VID]["pos"][1] + 260),
         [{"name": "image", "type": "IMAGE", "link": None}],
         [("IMAGE", "IMAGE")], [0, 1])
link(VID, 0, ff, 0, "IMAGE")

# ---- the checkbox -----------------------------------------------------------
cb = add("PrimitiveBoolean", "Replace background?  (on = use character's background)",
         (cx, cy - 170), [], [("BOOLEAN", "BOOLEAN")], [False], size=(420, 60))

# ---- SAM3 cutout branch -----------------------------------------------------
# SAM3 must load as a CHECKPOINT: that returns its own 1024-dim CLIP text
# encoder alongside the model. Encoding "person" with H3's Qwen3-VL gives
# 5120-dim embeddings -> "mat1 and mat2 shapes cannot be multiplied
# (1x5120 and 1024x256)". The file is symlinked into models/checkpoints/.
sam_loader = add("CheckpointLoaderSimple", "SAM3 model (+ its own CLIP)", (cx + 380, cy - 40), [],
                 [("MODEL", "MODEL"), ("CLIP", "CLIP"), ("VAE", "VAE")], [SAM3_MODEL])
sam_cond = add("CLIPTextEncode", "SAM3 target: person", (cx + 380, cy + 110),
               [{"name": "clip", "type": "CLIP", "link": None}],
               [("CONDITIONING", "CONDITIONING")], ["person"])
sam = add("SAM3_Detect", "SAM3 detect character", (cx + 740, cy),
          [{"name": "model", "type": "MODEL", "link": None},
           {"name": "image", "type": "IMAGE", "link": None},
           {"name": "conditioning", "type": "CONDITIONING", "link": None, "shape": 7},
           {"name": "bboxes", "type": "BOUNDING_BOX", "link": None, "shape": 7}],
          [("masks", "MASK"), ("bboxes", "BOUNDING_BOX")],
          [0.4, 2, False, "", ""])
grow = add("GrowMask", "Feather edge", (cx + 1080, cy),
           [{"name": "mask", "type": "MASK", "link": None}], [("MASK", "MASK")], [4, True])
size = add("GetImageSize", "Reference size", (cx + 380, cy + 260),
           [{"name": "image", "type": "IMAGE", "link": None}],
           [("width", "INT"), ("height", "INT"), ("batch_size", "INT")], [])
grey = add("EmptyImage", "Neutral grey backdrop", (cx + 740, cy + 260),
           [{"name": "width", "type": "INT", "link": None, "widget": {"name": "width"}},
            {"name": "height", "type": "INT", "link": None, "widget": {"name": "height"}}],
           [("IMAGE", "IMAGE")], [512, 512, 1, GREY])
comp = add("ImageCompositeMasked", "Character on grey", (cx + 1080, cy + 200),
           [{"name": "destination", "type": "IMAGE", "link": None},
            {"name": "source", "type": "IMAGE", "link": None},
            {"name": "mask", "type": "MASK", "link": None, "shape": 7}],
           [("IMAGE", "IMAGE")], [0, 0, False])
sw = add("ComfySwitchNode", "Character image H3 will see", (cx + 1420, cy + 60),
         [{"name": "on_false", "type": "IMAGE", "link": None},
          {"name": "on_true", "type": "IMAGE", "link": None},
          {"name": "switch", "type": "BOOLEAN", "link": None}],
         [("output", "IMAGE")], [False])

link(sam_loader, 0, sam, 0, "MODEL")
link(CHAR, 0, sam, 1, "IMAGE")
link(sam_loader, 1, sam_cond, 0, "CLIP")     # SAM3's OWN text encoder, never H3's
link(sam_cond, 0, sam, 2, "CONDITIONING")
link(sam, 0, grow, 0, "MASK")
link(CHAR, 0, size, 0, "IMAGE")
link(size, 0, grey, 0, "INT")
link(size, 1, grey, 1, "INT")
link(grey, 0, comp, 0, "IMAGE")
link(CHAR, 0, comp, 1, "IMAGE")
link(grow, 0, comp, 2, "MASK")
link(comp, 0, sw, 0, "IMAGE")                # off -> cutout on grey
link(CHAR, 0, sw, 1, "IMAGE")                # on  -> full reference with environment
link(cb, 0, sw, 2, "BOOLEAN")

# ---- Prompt Director --------------------------------------------------------
op = nodes[OLD_PROMPT]["pos"]
pd = add("H3PromptDirector", "H3 Prompt Director", op,
         [{"name": "source_video", "type": "IMAGE", "link": None},
          {"name": "character_image", "type": "IMAGE", "link": None},
          {"name": "replace_background", "type": "BOOLEAN", "link": None,
           "widget": {"name": "replace_background"}},
          {"name": "duration_seconds", "type": "FLOAT", "link": None,
           "widget": {"name": "duration_seconds"}}],
         [("prompt", "STRING"), ("preview", "STRING")],
         ["Replace the performer with the character in the reference image.",
          False, 5.0, 6, "claude-sonnet-4-5", ""], size=(520, 420))
link(VID, 0, pd, 0, "IMAGE")
link(sw, 0, pd, 1, "IMAGE")                  # SAME image H3 gets
link(cb, 0, pd, 2, "BOOLEAN")                # SAME checkbox drives the prompt
link(132, 0, pd, 3, "FLOAT")

pv = add("PreviewAny", "Generated Prompt (read-only)", (op[0] + 560, op[1]),
         [{"name": "source", "type": "*", "link": None}], [], [], size=(520, 420))
link(pd, 1, pv, 0, "STRING")

# ---- wire H3 ----------------------------------------------------------------
link(ff, 0, H3, slot(H3, "ref_images.ref_image_0"), "IMAGE")
link(sw, 0, H3, slot(H3, "ref_images.ref_image_1"), "IMAGE")
link(pd, 0, H3, slot(H3, "prompt"), "STRING")

# ---- audio mode: source / generated / off ----------------------------------
# H3 makes audio jointly with video; this only picks what lands in the file.
# Lazy inputs: in `source`/`off` mode VAEDecodeAudio (121) never executes.
CREATE, DEC_AUDIO = 130, 121
old_audio = nodes[CREATE]["inputs"][slot(CREATE, "audio")].get("link")
if old_audio is not None:
    unlink(old_audio)
ar = add("H3AudioRoute", "Audio: source / generated / off",
         (nodes[CREATE]["pos"][0] - 380, nodes[CREATE]["pos"][1] + 40),
         [{"name": "generated_audio", "type": "AUDIO", "link": None, "shape": 7},
          {"name": "source_audio", "type": "AUDIO", "link": None, "shape": 7}],
         [("audio", "AUDIO")], ["source"], size=(340, 90))
link(DEC_AUDIO, 0, ar, 0, "AUDIO")
link(VID, 2, ar, 1, "AUDIO")                # VHS_LoadVideo output 2 = source audio
link(ar, 0, CREATE, slot(CREATE, "audio"), "AUDIO")

# ---- resolution: 768p default (H3's local max, 1344x768 at 16:9) -------------
# ResolutionSelector: 0.98 MP @16:9, multiple 32 -> 1344x768; 0.4 -> 864x480.
# Batch runs override H3's width/height directly from the SOURCE aspect.
nodes[115]["widgets_values"] = ["16:9 (Widescreen)", 0.98, 32]
nodes[115]["title"] = "Resolution (0.98 MP = 768p, 0.4 MP = 480p)"

# ---- instructions -----------------------------------------------------------
add("MarkdownNote", "HOW TO RUN", (nodes[VID]["pos"][0], nodes[VID]["pos"][1] - 520), [], [], [
    "## Ref Character Replacement (MiniMax H3)\n\n"
    "1. **Source Video** - the clip to edit (2-15 s).\n"
    "2. **Character Reference** - one image of the new character.\n"
    "3. **Replace background?**\n"
    "   - **off** - character is cut out with SAM3 and put on grey, so the "
    "reference's environment cannot leak in. The video keeps its own background.\n"
    "   - **on** - the reference's environment replaces the video's background.\n"
    "4. **H3 Prompt Director** - type a plain instruction.\n"
    "5. **Float (Duration)** - seconds to render, <= source length and <= 15.\n"
    "6. **Audio** - `source` keeps the original soundtrack (default), "
    "`generated` uses H3's audio, `off` is silent.\n"
    "7. **Enable Lightning LoRA** - on = 4-step turbo (~4x faster).\n"
    "8. Queue. Read the generated prompt in the preview node; check "
    "*Character image H3 will see* to confirm the cutout.\n\n"
    "Hand-write a prompt via the Director's `manual_override`.\n\n"
    "**Rules:** no sexual/nude content; real identifiable people only with consent. "
    "Enforced inside the node."], size=(560, 420))

wf["last_node_id"] = state["node"] - 1
wf["last_link_id"] = state["link"] - 1
# widgets_values_named is a stale export-time copy of widget values that nothing
# reads (ComfyUI uses widgets_values). The supplied workflow's copy still held the
# third-party NSFW finetune filename and the original explicit example prompt
# after both were replaced, and a public release shipped them. Drop it every build.
for n in wf["nodes"]:
    n.pop("widgets_values_named", None)
_blob = json.dumps(wf)
for banned in ("Eros", "towel"):
    assert banned not in _blob, f"banned string {banned!r} still in workflow"
json.dump(wf, open(OUT, "w"), indent=1)
print(f"wrote {OUT}: {len(wf['nodes'])} nodes, {len(links)} links")
print(f"ids: checkbox={cb} switch={sw} director={pd} sam={sam} composite={comp} first_frame={ff}")
