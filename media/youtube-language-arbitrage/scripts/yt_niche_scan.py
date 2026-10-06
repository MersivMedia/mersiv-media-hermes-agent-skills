#!/usr/bin/env python3
"""Cross-language YouTube niche scan: how crowded is a topic in each language?

For each (lang, query) it fetches YouTube's channel search, parses channel handle + subscriber count,
and reports how many "serious" channels exist (>= --serious subscribers, default 10K).

Backends:
  - YouTube Data API v3 if YOUTUBE_API_KEY is set (env or ~/.hermes/.env): search.list (100 units/query)
    + channels.list (1 unit) -> exact subscriber counts. Free quota 10,000 units/day = ~95 queries.
  - Otherwise keyless: YouTube results page rendered by r.jina.ai (rate-limited, ~20 req/min; counts are
    YouTube's rounded display values like 4.25K).

Usage:
  yt_niche_scan.py --q en:"retirement tips" --q pt:"dicas de aposentadoria" --q es:"consejos jubilacion"
  yt_niche_scan.py --file queries.txt [--serious 10000] [--out ~/.hermes/data/yt-arbitrage/<niche>]
  queries.txt lines: <lang>:<query>   e.g.  de:Rente Tipps
Exit: 0 ok, 2 bad args, 4 every fetch failed.
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

GL = {'en': 'US', 'pt': 'BR', 'es': 'MX', 'de': 'DE', 'fr': 'FR', 'ja': 'JP', 'it': 'IT', 'ko': 'KR', 'hi': 'IN',
      'id': 'ID', 'tr': 'TR', 'ar': 'SA', 'ru': 'RU', 'pl': 'PL', 'nl': 'NL', 'vi': 'VN', 'th': 'TH'}
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36'


def api_key():
    k = os.environ.get('YOUTUBE_API_KEY')
    if k: return k
    p = os.path.expanduser('~/.hermes/.env')
    if os.path.exists(p):
        m = re.search(r'^YOUTUBE_API_KEY=(.+)$', open(p).read(), re.M)
        if m: return m.group(1).strip().strip('"')
    return None


def num(s):
    s = s.replace(',', '').strip()
    mult = {'K': 1e3, 'M': 1e6, 'B': 1e9}.get(s[-1:].upper(), 1)
    try: return int(float(s.rstrip('KMBkmb')) * mult)
    except ValueError: return None


def get(url, headers=None, timeout=90):
    req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout).read()


def scan_jina(lang, q):
    yt = 'https://www.youtube.com/results?' + urllib.parse.urlencode(
        {'search_query': q, 'sp': 'EgIQAg==', 'hl': lang, 'gl': GL.get(lang, 'US')})
    for attempt in range(3):
        try:
            md = get('https://r.jina.ai/' + yt, {'X-Return-Format': 'markdown'}).decode('utf8', 'replace')
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2: time.sleep(20 * (attempt + 1)); continue
            raise
    out, seen = [], set()
    # "[Name Name @handle•4.25K subscribers description](https://www.youtube.com/@handle)"
    for m in re.finditer(r'\[([^\[\]]*?)@([^\s•\]]+)•\s*([\d.,]+\s*[KMBkmb]?)\s+(?:subscribers|inscritos|suscriptores|Abonnenten|abonnés|iscritti)[^\]]*\]\((https://www\.youtube\.com/[^)\s]+)\)', md):
        handle = urllib.parse.unquote(m.group(2))
        if handle in seen: continue
        seen.add(handle)
        name = m.group(1).strip()
        half = len(name) // 2                      # name is printed twice ("Foo Bar Foo Bar")
        if half and name[:half].strip() == name[half:].strip(): name = name[:half].strip()
        out.append({'name': name, 'handle': '@' + handle, 'subs': num(m.group(3)), 'url': m.group(4)})
    return out


def scan_api(lang, q, key):
    s = json.loads(get('https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode(
        {'part': 'snippet', 'q': q, 'type': 'channel', 'maxResults': 25, 'relevanceLanguage': lang,
         'regionCode': GL.get(lang, 'US'), 'key': key})))
    ids = [i['snippet']['channelId'] for i in s.get('items', [])]
    if not ids: return []
    c = json.loads(get('https://www.googleapis.com/youtube/v3/channels?' + urllib.parse.urlencode(
        {'part': 'snippet,statistics', 'id': ','.join(ids), 'key': key})))
    out = []
    for i in c.get('items', []):
        st = i.get('statistics', {})
        out.append({'name': i['snippet']['title'], 'handle': i['snippet'].get('customUrl', ''),
                    'subs': None if st.get('hiddenSubscriberCount') else int(st.get('subscriberCount', 0)),
                    'videos': int(st.get('videoCount', 0)), 'url': f"https://www.youtube.com/channel/{i['id']}"})
    return sorted(out, key=lambda x: -(x['subs'] or 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--q', action='append', default=[], help='lang:query (repeatable)')
    ap.add_argument('--file')
    ap.add_argument('--serious', type=int, default=10000)
    ap.add_argument('--out')
    a = ap.parse_args()
    pairs = list(a.q)
    if a.file: pairs += [l.strip() for l in open(a.file) if l.strip() and not l.startswith('#')]
    pairs = [p.split(':', 1) for p in pairs if ':' in p]
    if not pairs: ap.print_help(); sys.exit(2)
    key = api_key()
    backend = 'youtube-data-api' if key else 'jina-keyless'
    results, fails = [], 0
    for i, (lang, q) in enumerate(pairs):
        lang, q = lang.strip().lower(), q.strip().strip('"')
        try:
            ch = scan_api(lang, q, key) if key else scan_jina(lang, q)
        except Exception as e:
            print(f'[{lang}] "{q}": FETCH FAILED {e}', file=sys.stderr); fails += 1; ch = None
        if ch is not None:
            subs = [c['subs'] for c in ch if c['subs'] is not None]
            serious = [c for c in ch if (c['subs'] or 0) >= a.serious]
            results.append({'lang': lang, 'query': q, 'channels_parsed': len(ch), 'serious': len(serious),
                            'top_subs': max(subs) if subs else 0, 'median_subs': sorted(subs)[len(subs) // 2] if subs else 0,
                            'channels': ch})
        if not key and i < len(pairs) - 1: time.sleep(3.5)
    if fails == len(pairs): sys.exit(4)
    print(f'backend: {backend} | serious = >= {a.serious:,} subscribers | read {time.strftime("%Y-%m-%d")}')
    print(f'{"lang":4} {"query":34} {"parsed":>6} {"serious":>7} {"top":>10} {"median":>8}')
    for r in results:
        print(f'{r["lang"]:4} {r["query"][:34]:34} {r["channels_parsed"]:>6} {r["serious"]:>7} {r["top_subs"]:>10,} {r["median_subs"]:>8,}')
    for r in results:
        top = sorted(r['channels'], key=lambda c: -(c['subs'] or 0))[:5]
        print(f'\n[{r["lang"]}] {r["query"]}: ' + '; '.join(f'{c["name"][:30]} {c["handle"]} {c["subs"] or "?":,}' if isinstance(c["subs"], int) else f'{c["name"][:30]} ?' for c in top))
    if a.out:
        os.makedirs(os.path.expanduser(a.out), exist_ok=True)
        p = os.path.join(os.path.expanduser(a.out), f'scan-{time.strftime("%Y%m%d-%H%M%S")}.json')
        json.dump({'backend': backend, 'serious_threshold': a.serious, 'results': results}, open(p, 'w'), indent=1, ensure_ascii=False)
        print(f'\nwrote {p}')


if __name__ == '__main__':
    main()
