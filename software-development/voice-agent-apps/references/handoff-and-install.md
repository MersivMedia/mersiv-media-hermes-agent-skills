# Hand-off: home-screen install + updates (iPhone, Oct 2026)

Personal apps ship as a Vercel web app the recipient saves to the home screen (PWA), not an App Store app. Users expect a "download"; say up front there isn't one.

## Install steps by browser (give the one for THEIR browser)

Always from the private link that includes `?key=…`. Saving the bare domain opens the locked page.

- **Safari, iOS 26:** tap **•••** (bottom right) → **Share** → scroll → **Add to Home Screen** → leave **Open as Web App** on → **Add**.
- **Safari, older iOS:** Share (square + up arrow, bottom toolbar; top right on iPad) → Add to Home Screen → Add.
- **Chrome iOS:** share icon at the right end of the address bar → Add to Home Screen (may be under "More") → Add. Very old Chrome builds lack it; fall back to Safari.
- **Firefox iOS:** menu **☰** (bottom right) → **Share** → Add to Home Screen → Add. Missing → update Firefox, else do this one step in Safari (the icon stays signed in on its own; they keep Firefox for everything else).

Then: the first voice-mode tap triggers the mic permission prompt. Tap **Allow**. If denied, re-enable in iPhone Settings (location varies by iOS version; don't promise an exact path).

## Why the key stays in the URL

The first build stripped `?key=` after setting the cookie (redirect to `/`). The home-screen icon then saved `/` and opened to "Open it from your personal link": iOS home-screen web apps don't reliably share the browser's cookies. Fix: serve the app on `/?key=…` without redirecting (see `templates/proxy-two-role-auth.ts`). Anyone who added the icon before the fix must delete and re-add it.

## Updates after hand-off (what to tell the owner)

- No install/update step on the recipient side: each launch loads the live deployment; progress and history live server-side (plus localStorage threads).
- Exceptions: an app left open in the background shows the old build until reload (solved by `templates/use-auto-update.ts`); agent prompt/voice changes go straight to ElevenLabs and apply next conversation; the icon image and name are captured at add time (re-add to change); rotating the learner key locks the icon out until re-added from the new link.
- Offer auto-update proactively. The user said yes immediately.

## Before the hand-off

- `scripts/reset-check.mjs` performs a REAL reset. If it runs after the owner has started testing, it archives their test data. Tell them it happened, and that it's still viewable in the dashboard's period dropdown.
- Automated checks (E2E, update-check) write into the current period. Run them before the owner's final "Reset for <name>", or say which sessions are yours.
