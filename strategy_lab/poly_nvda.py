"""همه‌ی بازارهای پلی‌مارکت مرتبط با NVDA، با احتمال و حجم، برای بررسی شرط حجم."""
import json
import requests

G = 'https://gamma-api.polymarket.com'
out, seen = [], set()
for tag in ['stocks', 'equities']:
    off = 0
    while off < 1000:
        r = requests.get(G + '/events', params={'closed': 'false', 'tag_slug': tag, 'limit': 100, 'offset': off}, timeout=40)
        ev = r.json() if r.ok else []
        if not ev:
            break
        for e in ev:
            for m in e.get('markets') or []:
                q = m.get('question') or ''
                if ('NVDA' in q or 'NVIDIA' in q) and q not in seen:
                    seen.add(q)
                    out.append({'q': q, 'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
                               'vol': m.get('volumeNum') or m.get('volume'), 'event_vol': e.get('volume'),
                               'end': m.get('endDate'), 'slug': e.get('slug')})
        off += 100
out.sort(key=lambda x: -(float(x['vol'] or 0)))
print(json.dumps(out, indent=1, ensure_ascii=False))
import os
os.makedirs('data/strategy_lab/poly_nvda', exist_ok=True)
json.dump(out, open('data/strategy_lab/poly_nvda/result.json', 'w'), ensure_ascii=False, indent=1)
