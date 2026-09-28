#!/usr/bin/env python3
"""Reusable Replicate API generation helper.

Supports image (flux-2-pro, gpt-image-2) and video (seedance-2.0) models.
Handles polling, retries, parallel batches, and saves outputs.

Usage:
    from replicate_generate import generate

    # Single image
    generate(model="black-forest-labs/flux-2-pro",
             prompt="...",
             out_path="/tmp/img.png",
             extra_input={"aspect_ratio": "1:1"})

    # Image-to-image
    generate(model="openai/gpt-image-2",
             prompt="Keep this exact composition... Only ONE change: ...",
             out_path="/tmp/edited.png",
             input_images=["/path/to/source.png"],
             extra_input={"aspect_ratio": "match_input_image"})

    # Video with first + last frame
    generate(model="bytedance/seedance-2.0",
             prompt="...",
             out_path="/tmp/video.mp4",
             extra_input={"image": "data:...", "last_frame_image": "data:...",
                          "duration": 7, "generate_audio": True})

    # Parallel batch
    from concurrent.futures import ThreadPoolExecutor, as_completed
    tasks = [(model, prompt, out_path, extra) for ...]
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(generate, *t): t for t in tasks}
        for fut in as_completed(futs):
            print(fut.result())

Env: requires REPLICATE_API_TOKEN. Run from `terminal`, not `execute_code`
(execute_code does not inherit env vars).
"""
import os, json, time, base64, urllib.request, urllib.error


def to_data_uri(path: str) -> str:
    """Encode a local file as data: URI for input_images / image / last_frame_image."""
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
            "webp": "webp", "gif": "gif", "mp4": "mp4"}.get(ext, ext)
    with open(path, "rb") as f:
        return f"data:image/{mime};base64,{base64.b64encode(f.read()).decode()}"


def generate(model: str,
             prompt: str,
             out_path: str,
             extra_input: dict = None,
             input_images: list = None,
             timeout: int = 600,
             poll_interval: float = 4.0) -> dict:
    """Submit a Replicate prediction, poll until done, download output to out_path.

    Args:
        model: 'owner/model' slug, e.g. 'black-forest-labs/flux-2-pro'.
        prompt: text prompt.
        out_path: where to save the downloaded output.
        extra_input: dict of additional input fields (aspect_ratio, duration, etc.).
        input_images: list of local image paths to encode + pass as input_images.
        timeout: max seconds to wait for completion.
        poll_interval: seconds between status polls.

    Returns:
        dict with 'status', 'out_path', 'prediction_id'.
    """
    token = os.environ["REPLICATE_API_TOKEN"]
    inp = {"prompt": prompt}
    if extra_input:
        inp.update(extra_input)
    if input_images:
        inp["input_images"] = [to_data_uri(p) for p in input_images]

    body = json.dumps({"input": inp}).encode()
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{model}/predictions",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "wait=60",  # max is 60
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500]
        raise RuntimeError(f"Replicate HTTP {e.code}: {err_body}")

    pid = resp["id"]
    status = resp.get("status")
    output = resp.get("output")

    deadline = time.time() + timeout
    while status not in ("succeeded", "failed", "canceled") and time.time() < deadline:
        time.sleep(poll_interval)
        poll = urllib.request.Request(
            f"https://api.replicate.com/v1/predictions/{pid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(poll, timeout=30) as r:
            pd = json.loads(r.read())
        status = pd.get("status")
        output = pd.get("output")

    if status != "succeeded":
        raise RuntimeError(f"Prediction {pid} failed with status={status}")

    url = output if isinstance(output, str) else output[0]
    data = urllib.request.urlopen(url, timeout=120).read()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)

    return {"status": status, "out_path": out_path, "prediction_id": pid,
            "bytes": len(data)}


def get_schema(model: str) -> dict:
    """Fetch a model's input schema. Useful to check accepted fields/enums
    before submitting (avoids 422 errors)."""
    token = os.environ["REPLICATE_API_TOKEN"]
    req = urllib.request.Request(
        f"https://api.replicate.com/v1/models/{model}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    return (d.get("latest_version", {})
             .get("openapi_schema", {})
             .get("components", {})
             .get("schemas", {})
             .get("Input", {})
             .get("properties", {}))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == "schema":
        print(json.dumps(get_schema(sys.argv[2]), indent=2))
