#!/usr/bin/env bash
# Live test of x_read.py against the two articles read this session + a plain embedded tweet + error paths.
set -u
S=~/.hermes/skills/research/social-post-extraction/scripts/x_read.py
O=${1:-$HOME/.hermes/data/x-reader/test}
mkdir -p "$O"
echo "== 1. Movez article (code blocks, media, embedded tweets, dividers)"
python3 "$S" "https://x.com/0xmovez/status/2104216919033192746?s=46" --out "$O"; echo "exit=$?"
echo "== 2. Raphael article (GitHub link inline)"
python3 "$S" "https://x.com/raphaelaubryy/status/2104502744010629269?s=46" --out "$O"; echo "exit=$?"
echo "== 3. plain tweet by bare id (one of Movez's embeds)"
python3 "$S" 2103315922098470926 | head -12; echo "exit=${PIPESTATUS[0]}"
echo "== 4. bad input"
python3 "$S" "https://example.com/nothing"; echo "exit=$? (expect 2)"
echo "== 5. nonexistent id"
python3 "$S" "https://x.com/jack/status/1"; echo "exit=$? (expect 3)"
echo "== 6. embeds resolved (Raphael article has none; use a 3-embed slice check on Movez: count resolved quotes)"
python3 "$S" 2104216919033192746 --embeds --out "$O/emb" | head -2; echo "exit=$?"
printf 'resolved embeds: %s of 21\n' "$(grep -c '^> \*\*@' "$O/emb/2104216919033192746.md")"
echo "== checks on article 1"
M=$O/2104216919033192746.md
printf 'code fences: %s\n' "$(grep -c '^```' "$M")"
printf 'images: %s\n' "$(grep -c '^!\[' "$M")"
printf 'embedded posts: %s\n' "$(grep -c 'embedded post' "$M")"
printf 'dividers: %s\n' "$(grep -c '^---$' "$M")"
printf 'chars: %s\n' "$(wc -c < "$M")"
echo "== checks on article 2"
grep -n "github.com" "$O/2104502744010629269.md" | head -5
