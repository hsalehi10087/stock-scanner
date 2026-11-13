"""بررسی دسترسی به API عمومی پلی‌مارکت و شمارش بازارهای باز سهام/شاخص (فقط خواندن)."""
import json
import os
import re

import requests

G = 'https://gamma-api.polymarket.com'
OUT = 'data/strategy_lab/poly_probe'
KW = re.compile(r'\b(S&P|SPX|Nasdaq|NDX|Dow Jones|stock|shares|close (above|below|at)|Up or Down|'
                r'TSLA|Tesla|NVDA|Nvidia|AAPL|Apple|MSFT|Microsoft|AMZN|Amazon|GOOGL|Google|META|Netflix|NFLX|'
                r'COIN|Coinbase|PLTR|Palantir|MSTR|AMD|HOOD|Robinhood|IPO|market cap)\b', re.I)


def get(path, **p):
    r = requests.get(G + path, params=p, timeout=30)
    return r.status_code, (r.json() if r.ok else r.text[:200])


res = {'tags': {}}
st, tags = get('/tags', limit=1000)
res['tags_status'] = st
if st == 200:
    res['tag_list'] = [t.get('slug') for t in tags if any(k in (t.get('slug') or '') for k in
                                                          ('stock', 'equit', 'finance', 'earn', 'nasdaq', 'sp-500', 'tesla', 'nvidia', 'ipo'))]
for slug in ['stocks', 'equities', 'finance', 'earnings', 'business', 'economy', 'tech', 'ipos', 'indicies', 'sp-500']:
    st, ev = get('/events', closed='false', tag_slug=slug, limit=200)
    if st == 200:
        res['tags'][slug] = {'events': len(ev), 'sample': [e.get('title') for e in ev[:15]]}
    else:
        res['tags'][slug] = {'status': st}
# همه‌ی بازارهای باز (صفحه‌به‌صفحه) و جستجوی کلیدواژه
mk, off = [], 0
while off < 6000:
    st, page = get('/markets', closed='false', active='true', limit=500, offset=off)
    if st != 200 or not page:
        break
    mk += page
    off += 500
res['open_markets_total'] = len(mk)
hits = [m for m in mk if KW.search(m.get('question') or '')]
def vol(m):
    try:
        return float(m.get('volumeNum') or m.get('volume') or 0)
    except Exception:
        return 0.0
res['stock_like'] = len(hits)
res['stock_like_vol10k'] = sum(vol(m) >= 10000 for m in hits)
hits.sort(key=lambda m: -vol(m))
res['top'] = [{'q': m.get('question'), 'vol': round(vol(m)), 'end': m.get('endDate'), 'outcomes': m.get('outcomes'),
               'prices': m.get('outcomePrices'), 'slug': m.get('slug'), 'tags': [t.get('slug') for t in (m.get('tags') or [])][:5]}
              for m in hits[:60]]
os.makedirs(OUT, exist_ok=True)
json.dump(res, open(os.path.join(OUT, 'result.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'top'}, ensure_ascii=False, indent=1)[:4000])
