# Share assets: favicon, home-screen icon, link preview

A shared game link needs a tab icon, an iOS home-screen icon, and an og:image plus
caption, so iMessage/WhatsApp/X show a card and not a bare URL. From the Heart Maze
build. Generator template: `templates/make_share_assets.py`.

## Plan first (user asked explicitly)
Before generating anything, send the plan and wait for "go ahead":
- which character is the icon and why (e.g. the pink squirrel, to match the palette),
  offering one alternative (e.g. the orange one, which stands out more in a row of tabs)
- the preview layout in words: title, tagline, maze strip, hero chased by enemies
- the exact caption title + description text
- what is deliberately left out: **no prize/reward character** (the bear) in the
  preview or caption, same spoiler rule as the start screen
- how it's made: rendered from the game's real sprites in headless Chromium. It's
  free, with no AI image generation, so it matches the game pixel for pixel.
If you add something the plan didn't mention (a footer line, a moved element), call it out as a deviation in the final reply.

## Files + tags
| File | Size | Notes |
|---|---|---|
| `favicon-32.png` | 32×32 | rounded dark tile, sprite at integer scale |
| `icon-192.png` | 192×192 | rounded |
| `apple-touch-icon.png` | 180×180 | **square, not rounded**: iOS applies its own mask |
| `og-image.jpg` | 1200×630 | JPEG q0.92 ≈ 88 KB (the PNG was ≈ 600 KB, and some apps drop big previews) |

`<head>`: `meta description`, `link rel=icon` ×2 with sizes, `apple-touch-icon`,
`apple-mobile-web-app-title`, `og:type/site_name/url/title/description/image`
(**absolute** https URL), `og:image:width/height/alt`, `twitter:card=summary_large_image`
+ `twitter:title/description/image`. Root-level asset files deploy fine with the
existing `.vercelignore` (which only excludes `.test/`).

## Rendering pitfalls
- Slice the sprite consts out of `game.js` between two stable comment markers and
  inject them into the generator page, so there's one source of truth for the art.
  Define any constants the slice references (e.g. `COLS`, `ROWS`).
- `await document.fonts.load(...)` for every web font **before** `fillText`, or the
  preview ships with a fallback font.
- The pixel-sprite helper sets `fillStyle` per pixel and leaves it on the last
  sprite colour. **Reset `fillStyle` before any text drawn after a sprite.** This
  bug turned "1 SPECIAL PRIZE" pink.
- To centre a mixed text+sprite line, measure each text run and compute the group
  width. Centring only the sprite looks off-centre.
- Icon sprite scale = `floor(size/16)` for a 14px sprite, centred, no smoothing.
- Look at the output with vision (full image plus a zoomed crop of each text line) before deploying.

## Verify on the live site
```bash
for f in /favicon-32.png /icon-192.png /apple-touch-icon.png /og-image.jpg; do
  curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}B $f\n" "$BASE$f"; done
curl -s -A "facebookexternalhit/1.1" "$BASE/" | grep -oE '<meta (property|name)="(og|twitter):(title|description|image)" content="[^"]*"'
```
Tell the user what wasn't checked: the card inside iMessage itself. **iMessage caches
a link's preview on first send.** Old threads keep the old card, so test by sending
the link to yourself first.
