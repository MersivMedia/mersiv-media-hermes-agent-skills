# assets.py — free, commercially usable assets, fetched into the project. Look at everything on a contact sheet
# before using it. Licences: Mixkit free licence (music/SFX/video, no attribution); svgl / simple-icons logos
# remain their owners' trademarks (use for "works with" truthfully, never to imply partnership); picsum serves
# Unsplash-licensed photos; 3dicons.co CC0.
#
#   python assets.py sfx click                list Mixkit SFX ids + titles for a tag (whoosh, pop, swoosh, notification, ...)
#   python assets.py sfx-get 1125 2568        download SFX previews -> sfx/<id>.mp3
#   python assets.py music hip-hop            list Mixkit music ids + titles for a genre page
#   python assets.py music-get 207            download a track -> audio/mixkit-<id>.mp3 (then: python drop.py audio/mixkit-207.mp3)
#   python assets.py logo shopify openai      colour SVG logos -> assets/logos/<name>.svg (svgl.app, fallback simple-icons)
#   python assets.py photo 184 2600 1600      picsum (Unsplash licence) photo id at size -> assets/photos/
#
# Mixkit's own search ignores ?q=: crawl the tag/genre pages instead (what this does).
# Adapted from howseen-ai/claude-motion-design mixkit_sfx_search.py + svgl_logos.py (MIT).
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def get(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def save(url, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(get(url))
    print(f"{path}  ({path.stat().st_size // 1024} KB)")


def cards(html, id_re):
    marks = [(m.start(), m.group(1)) for m in re.finditer(id_re, html)]
    titles = [(m.start(), m.group(1).strip()) for m in re.finditer(r'item-grid-card__title">\s*(?:<[^>]+>\s*)*([^<]+?)\s*<', html)]
    seen, out = set(), []
    for i, (p, sid) in enumerate(marks):
        if sid in seen:
            continue
        seen.add(sid)
        prv = marks[i - 1][0] if i else 0
        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(html)
        near = [t for pos, t in titles if prv < pos < nxt]
        out.append((sid, near[0] if near else "?"))
    return out


cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "sfx":
    for tag in args:
        html = get(f"https://mixkit.co/free-sound-effects/{tag}/").decode("utf8", "ignore")
        print(f"== {tag}")
        for sid, title in cards(html, r'data-audio-player-item-id-value="(\d+)"')[:30]:
            print(f"  {sid:>5}  {title}")
elif cmd == "sfx-get":
    for sid in args:
        save(f"https://assets.mixkit.co/active_storage/sfx/{sid}/{sid}-preview.mp3", f"sfx/{sid}.mp3")
elif cmd == "music":
    for genre in args:
        html = get(f"https://mixkit.co/free-stock-music/{genre}/").decode("utf8", "ignore")
        print(f"== {genre}")
        for sid, title in cards(html, r'music/(\d+)/\1\.mp3')[:30]:
            print(f"  {sid:>5}  {title}")
elif cmd == "music-get":
    for sid in args:
        save(f"https://assets.mixkit.co/music/{sid}/{sid}.mp3", f"audio/mixkit-{sid}.mp3")
elif cmd == "logo":
    for name in args:
        try:
            res = json.loads(get("https://api.svgl.app?search=" + urllib.parse.quote(name)))
            pick = next((r for r in res if r["title"].lower().replace(".", "").startswith(name.lower().replace(".", ""))),
                        res[0] if res else None)
            if not pick:
                raise LookupError("no svgl match")
            route = pick["route"] if isinstance(pick["route"], str) else pick["route"].get("light")
            save(route, f"assets/logos/{name}.svg")
        except Exception as e:
            print(f"{name}: svgl failed ({e}), trying simple-icons (monochrome)")
            save(f"https://cdn.jsdelivr.net/npm/simple-icons@13/icons/{name}.svg", f"assets/logos/{name}.svg")
elif cmd == "photo":
    pid, w, h = args[0], args[1] if len(args) > 1 else "2400", args[2] if len(args) > 2 else "1600"
    info = json.loads(get(f"https://picsum.photos/id/{pid}/info"))
    save(f"https://picsum.photos/id/{pid}/{w}/{h}", f"assets/photos/picsum-{pid}.jpg")
    print(f"author: {info.get('author')}  source: {info.get('url')}")
else:
    sys.exit(__doc__ if False else "unknown command; see header")
