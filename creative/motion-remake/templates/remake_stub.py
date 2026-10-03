# remake_stub.py — one placeholder file per shot group (project.json "groups": {"G1": [f0, f1], ...}).
# Never overwrites an existing shots/<G>.js. Run after SPEC.md, before dispatching build agents.
import json
from pathlib import Path

H = Path.cwd()
P = json.loads((H / "project.json").read_text())
(H / "shots").mkdir(exist_ok=True)
for g, (a, b) in P["groups"].items():
    p = H / f"shots/{g}.js"
    if p.exists():
        print("keep", p)
        continue
    p.write_text(f"""(function () {{
  const C = CORE;
  // {g}: frames {a}-{b}. Replace this placeholder with real shots: one SHOT per shot id, contiguous, helpers prefixed {g}_.
  SHOT({{ id: '{g}_placeholder', f0: {a}, f1: {b}, render: (lf, F) =>
    `<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font:48px sans-serif;color:#94a3b8">{g} · F${{F}}</div>` }});
}})();
""")
    print("stub", p)
