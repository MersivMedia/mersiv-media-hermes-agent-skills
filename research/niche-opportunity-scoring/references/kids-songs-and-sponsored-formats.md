# Kids' songs and "every scene is an ad slot" formats (researched 2026-10-05)

Source post: @ArchiveExplorer, 2026-10-04, https://x.com/archiveexplorer/status/2106853265694503064 (links its own
article, x.com/ArchiveExplorer/status/2099882744541045045). Read both with `social-post-extraction`.

## What the post claims
- 35 s counting song with a consistent AI mascot (a dinosaur) in one playroom.
  - Song: Lyria 3 Pro from the author's own lyrics (vocals + ukulele); Whisper caught a skipped line, 3 tries.
  - Character stills: Nano Banana Pro; lip-sync/dance: Seedance 2.5; edit: HyperFrames (karaoke word
    highlight, counting board).
  - Cost: ~520 Higgsfield + 34 Picsart credits.
- Monetization pitch: "every scene is an ad slot" (toothbrush → toothpaste brands, bath → bath toys, bedtime →
  night lights).
- 8.3M views: unclear whether that is his video or the toddler cartoon he remade. In the linked article the
  big numbers belonged to the originals. The article promotes Picsart.

## Policy reality (verify again before advising; things move fast here)
- YouTube kids-content quality principles name "heavily commercial or promotional" made-for-kids videos as low
  quality → limited/no ads, possible removal from the Partner Program. Paid placement aimed at toddlers also
  draws FTC/COPPA scrutiny. **Recommend dropping the in-video ad-slot model entirely.**
- April 2026: 200+ child-safety groups (Fairplay-led) asked YouTube to ban AI content from YouTube Kids; May
  2026: YouTube committed to clearer AI labels. The July 2025 "inauthentic content" rename targets templated
  mass production. Expect more pressure, not less.
- Made-for-kids: no personalized ads, comments or notifications → lower RPM, offset by huge replay volume.
- Mislabeling is expensive: Disney paid $10M in 2025 for kids' videos labeled as general audience.

## Legitimate version
- Build a CHARACTER (CoComelon / Baby Shark model) with good educational songs (counting, colors, first words),
  one language per channel, and disclose AI.
- Revenue: YouTube ads + music distribution (Spotify/Apple via a distributor); merch/licensing only if the
  character catches on. No paid products inside the videos.
- Production chain maps to the user's skills: Replicate (Seedance; check which music models are live first),
  HyperFrames `embedded-captions` for singalong highlighting, Whisper lyric check, songwriting skills.
- Before producing: run the kids-songs dives (`dive_<lang>_kids_songs.cfg` in
  `~/.hermes/data/yt-arbitrage/niches/`, made by `make_kids_cfgs.py`) for owner concentration. Nursery rhymes
  are among the most incumbent-locked categories on YouTube, so expect few breakouts.

## General lesson
Treat sponsorship or ad-slot claims in a viral "how I make $X" post with the same skepticism as its earnings
claims. Check the platform's rules for that audience before presenting the monetization as an opportunity.
