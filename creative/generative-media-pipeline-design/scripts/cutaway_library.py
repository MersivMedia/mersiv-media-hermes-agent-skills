"""Cutaway fallback library — generate character-free bridge clips, pick at runtime.

WHY THIS EXISTS
    A live generative-video system has a hard constraint: the next clip must
    exist before the current one ends. Generation is fast but not guaranteed —
    a provider 500, a safety rejection or a queue backup will eventually land
    inside a vote window. The answer is not a bigger buffer. It is having
    something honest to cut to.

WHY CHARACTER-FREE IS THE WHOLE TRICK
    Every drift failure this class of pipeline produces is a CHARACTER failure:
    faces aging, wardrobe changing, blocking re-staging. A clip with no
    character in it cannot break identity continuity, which makes it the only
    shot type safe to substitute arbitrarily and reuse across runs. Generate it
    from the location plates and it cannot break the world either.

    Film grammar absorbs this completely. Cutting to the lamp while someone
    decides is normal editing, not an apology.

USAGE
    Adapt SUBJECTS to your locations, wire `generate_clip` to your provider,
    then generate once per location offline:

        python cutaway_library.py story.json --beat b1_arrival --dry-run
        python cutaway_library.py story.json --beat b1_arrival

    At runtime, pass a CutawayLibrary into your renderer and catch generation
    failures with it (see `render_with_fallback` below).

PROVIDER NOTES
    - Clip duration often has a FLOOR (5s on MiniMax H3 Max; `duration: 4` is
      rejected at result-fetch time, not at submit).
    - 5s is also about the shortest clip that reads as a deliberate cut rather
      than a glitch.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

# Concrete and mechanical. A cutaway must be unambiguous about WHERE it is and
# must contain no people. Five subjects covers a location comfortably.
SUBJECTS = [
    ("mechanism", "the location's defining mechanism or machine seen close, "
                  "metal and glass, moving slowly"),
    ("water",     "water breaking against wet rock or running over a hard "
                  "surface, spray caught in the available light"),
    ("glass",     "rain running down a salt-crusted window pane, the light "
                  "beyond diffused into soft bloom"),
    ("detail",    "a weathered practical detail — worn handrail, peeling "
                  "paint, a bolted hatch — held in shallow focus"),
    ("wide",      "an empty wide of the location with no person present, "
                  "atmosphere drifting through the frame"),
]

DURATION = 5
NEG = ("Absolutely NO people, NO figures, NO silhouettes, NO hands, no human "
       "presence of any kind anywhere in frame.")


def cutaway_prompt(location_desc: str, subject: str, style: str) -> str:
    """Location grounding + style bible + a hard negative on human presence."""
    return f"{subject}. Location: {location_desc}. {style} {NEG}"


def generate_clip(prompt: str, plate: Path, duration: int, dest: Path) -> None:
    """Wire this to your provider. Image-to-video from a location plate.

    No characters means no identity locks are needed, so the cheap/fast
    endpoint is appropriate here.
    """
    raise NotImplementedError(
        "wire to your provider, e.g.:\n"
        "  res = fal.run('minimax/h3-max/image-to-video', {\n"
        "      'prompt': prompt,\n"
        "      'image_url': fal.upload(plate),\n"
        "      'duration': duration,\n"
        "      'resolution': '768P',\n"
        "      'prompt_expansion_mode': 'disabled'})\n"
        "  fal.fetch(res['video']['url'], dest)")


def build(story_path: Path, beat_id: str, dry: bool = False) -> list[Path]:
    """Generate the cutaway set for one location.

    ONE API CALL PER SUBJECT. Batched 'N distinct items' requests return N
    independent rolls of the same prompt, not a coherent set — the single most
    repeated failure in this class of pipeline.
    """
    story = json.loads(story_path.read_text())
    beats = [b for ch in story.get("chapters", []) for b in ch.get("beats", [])]
    beat = next((b for b in beats if b["id"] == beat_id), None)
    if beat is None:
        raise SystemExit(f"no beat {beat_id!r}; have {[b['id'] for b in beats]}")

    style = story.get("style_bible", "")
    location = beat.get("location") or beat.get("premise", beat_id)

    out = Path("assets/cutaways") / beat_id
    out.mkdir(parents=True, exist_ok=True)

    plates = sorted(Path("assets/plates", beat_id).glob("plate_*.png"))[:3]
    if not plates and not dry:
        raise SystemExit(f"no location plates for {beat_id}; generate them first")

    made = []
    for name, subject in SUBJECTS:
        dest = out / f"{name}.mp4"
        prompt = cutaway_prompt(location, subject, style)
        if dry:
            print(f"  [{name}] {DURATION}s  refs={len(plates)}")
            print(f"      {prompt[:150]}...")
            continue
        if dest.exists():
            print(f"  [{name}] exists, skipping")
            made.append(dest)
            continue
        print(f"  [{name}] generating {DURATION}s...")
        generate_clip(prompt, plates[0], DURATION, dest)
        made.append(dest)
    return made


class CutawayLibrary:
    """Runtime picker. Never returns the same clip twice within one screening."""

    def __init__(self, root: Path = Path("assets/cutaways")):
        self.root = Path(root)
        self.used: set[Path] = set()

    def available(self, beat_id: str) -> list[Path]:
        return sorted((self.root / beat_id).glob("*.mp4"))

    def take(self, beat_id: str, rng: random.Random | None = None) -> Path | None:
        """Unused cutaway for this location, else any location, else None.

        Falling back across locations is deliberate: a slightly wrong-place
        cutaway is far less damaging than a stall. Returning None means the
        library is exhausted — the caller MUST treat that as a real error, not
        stall silently. It is the signal to generate more cutaways.
        """
        rng = rng or random
        pool = [p for p in self.available(beat_id) if p not in self.used]
        if not pool:
            pool = [p for p in self.root.rglob("*.mp4") if p not in self.used]
        if not pool:
            return None
        pick = rng.choice(pool)
        self.used.add(pick)
        return pick

    def reset(self) -> None:
        """Call between screenings so clips become available again."""
        self.used.clear()


def render_with_fallback(render_fn, beat_id: str, dest: Path,
                         library: CutawayLibrary | None):
    """Shape of the integration. Note `result` is initialised BEFORE the try.

    A real bug caught by testing this path: code after the try block still
    referenced the success-path result variable, so the cutaway substitution
    worked and the function raised UnboundLocalError anyway.
    """
    import shutil
    result: dict = {}
    try:
        result = render_fn()
    except Exception as exc:
        if not library:
            raise
        alt = library.take(beat_id)
        if alt is None:
            raise RuntimeError(
                f"render failed ({exc}) and the cutaway library is exhausted "
                "— generate more cutaways for this location") from exc
        print(f"  DEADLINE MISS ({type(exc).__name__}) -> cutaway {alt.name}")
        shutil.copyfile(alt, dest)
        result = {"fallback": alt.name}
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("story", type=Path)
    ap.add_argument("--beat", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    print(f"cutaways for {a.beat}{'  [DRY RUN]' if a.dry_run else ''}")
    made = build(a.story, a.beat, a.dry_run)
    if not a.dry_run:
        print(f"-> {len(made)} cutaways in assets/cutaways/{a.beat}/")


if __name__ == "__main__":
    main()
