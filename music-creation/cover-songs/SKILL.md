---
name: cover-songs
description: Create Suno-ready cover song remakes in any genre. Use when the user wants to remake, cover, or transform a song into a different genre. Produces exact original lyrics with genre-adapted performance, delivery, and style metadata for Suno AI music generation. Triggers on "cover song", "remake", "genre conversion", "Suno remake", or "transform this song into [genre]".
---

# Cover Songs (Suno Remake Expert)

Transform any song into a new genre while preserving ALL original lyrics exactly.

## Quick Start

1. User provides: **artist**, **title**, **target genre(s)** (optional: subgenres)
2. Fetch exact original lyrics (web search if needed)
3. Research target genre deeply
4. Output exactly TWO code blocks: `lyrics` + `style`

## Core Rules

### Lyric Preservation (NON-NEGOTIABLE)

- **NEVER** modify, paraphrase, reword, or reorder lyrics
- **NEVER** change pronouns, tense, grammar, or meaning
- **MAY** add: section headers, sparse ad-libs (10-15% max), call-and-response using ONLY existing lyrics

### Genre Fusion

- Target genre = 80-90% of performance style
- Original genre = 10-20% subtle influence
- Only performance/arrangement changes — never lyrics

## Output Format

See [references/suno-remake-guide.md](references/suno-remake-guide.md) for complete formatting rules.

**Block 1 — Lyrics:**
```lyrics
[SECTION NAME | delivery | energy | fx]
Original lyrics here (untouched)
(optional ad-lib)
```

**Block 2 — Style (Suno metadata only):**
```style
genre: target genre
mood: 2-3 word emotional tone
tempo: BPM or relative
instruments: 3-6 core instruments
percussion: rhythm pattern
bass: tone + movement
vocals: delivery style + harmony
mix: fx + space + texture
energy: section-by-section curve
source_influence: subtle original genre touch
```

## Section Headers

Format: `[SECTION NAME | VOCAL DELIVERY | ENERGY LEVEL | OPTIONAL FX]`

Valid sections: Intro, Verse, Rap Verse, Pre-Chorus, Chorus, Hook, Bridge, Breakdown, Build, Drop, Interlude, Instrumental, Instrumental Break, Solo, Outro, Ensemble, Tutti, Call & Response, Improvisation, Choir Break

## Ad-Lib Rules

- 10-15% max of lines
- End of line only, in parentheses
- Genre-appropriate (research the genre)
- Never two ad-libbed lines in a row
- Never on iconic emotional lines

## Quality Checklist

Before output, verify:
1. NO empty section headers
2. Lyrics COMPLETELY original/untouched
3. Genre adaptation is strong and obvious
4. Style block is PURE technical metadata (no narrative)
5. Exactly TWO code blocks produced
