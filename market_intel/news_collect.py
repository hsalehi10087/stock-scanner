"""خبرخوان بازار — جمع‌آوری خبرهای طلا، نقره، بیت‌کوین، مس، نفت و نرخ بهره (هر چند ساعت).

منابع: Finnhub (general، forex، crypto) + RSS سایت‌های خبری تخصصی. فقط جمع‌آوری؛ «درک خبر» و استخراج
نظر تحلیلگران را کار زمان‌بندی‌شده‌ی Claude انجام می‌دهد و در data/analyst_views/latest.json می‌نویسد.
خروجی: data/news/YYYY-MM-DD.jsonl (بدون تکرار؛ ۱۰ روز آخر نگه داشته می‌شود) و data/news/diagnostics.txt
"""
import datetime as dt
import glob
import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'news')
KEY = os.getenv('FINNHUB_API_KEY', '')
UA = {'User-Agent': 'Mozilla/5.0 (compatible; market-intel-news/1.0)'}
ASSETS = {
    'gold': r'\b(gold|bullion|xau)\b',
    'silver': r'\b(silver|xag)\b',
    'bitcoin': r'\b(bitcoin|btc|crypto(?:currency|currencies)?)\b',
    'copper': r'\b(copper)\b',
    'oil': r'\b(oil|crude|brent|wti|opec\+?)\b',
    'ai': r'\b(artificial intelligence|a\.?i\.? (?:chips?|stocks?|models?|infrastructure|startups?|agents?|demand|spending|capex)|genai|generative ai|llms?|data ?cent(?:er|re)s?|gpus?|nvidia|openai|anthropic|hyperscalers?)\b',
    'rates': r'\b(fed|fomc|powell|rate cut|rate hike|interest rates?|treasury yields?|bond yields?|inflation|cpi|ecb|boj)\b',
}
FEEDS = {
    'forexlive': 'https://www.forexlive.com/feed/news',
    'oilprice': 'https://oilprice.com/rss/main',
    'coindesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'cointelegraph': 'https://cointelegraph.com/rss',
    'mining.com': 'https://www.mining.com/feed/',
    'investing-commodities': 'https://www.investing.com/rss/news_11.rss',
    'investing-economy': 'https://www.investing.com/rss/news_14.rss',
    'cnbc-markets': 'https://www.cnbc.com/id/20910258/device/rss/rss.html',
    'marketwatch': 'https://feeds.content.dowjones.io/public/rss/mw_topstories',
    'fed-press': 'https://www.federalreserve.gov/feeds/press_all.xml',
}
GQ = {'gold': 'gold price analysts forecast', 'silver': 'silver price analysts forecast',
      'bitcoin': 'bitcoin price analysts forecast', 'copper': 'copper price analysts outlook',
      'oil': 'oil price analysts forecast brent', 'rates': 'Fed interest rate outlook economists',
      'ai': 'AI stock analyst upgrade price target', 'ai-small': 'AI small cap stock revenue growth',
      'ai-infra': 'AI data center stock earnings guidance', 'ai-chips': 'AI chip stock outlook analysts'}
for _a, _q in GQ.items():
    FEEDS[f'googlenews-{_a}'] = ('https://news.google.com/rss/search?q=' + _q.replace(' ', '+') +
                                 '+when:2d&hl=en-US&gl=US&ceid=US:en')
DIAG = []


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def tags(text):
    t = text.lower()
    return [a for a, rx in ASSETS.items() if re.search(rx, t)]


def finnhub():
    out = []
    if not KEY:
        DIAG.append('finnhub: no key')
        return out
    for cat in ('general', 'forex', 'crypto'):
        try:
            r = requests.get('https://finnhub.io/api/v1/news', params={'category': cat, 'token': KEY}, timeout=30)
            DIAG.append(f'{r.status_code} finnhub/{cat} n={len(r.json()) if r.ok else 0}')
            for n in r.json() if r.ok else []:
                out.append({'source': n.get('source') or 'finnhub', 'title': n.get('headline', ''),
                            'summary': clean(n.get('summary', ''))[:1500], 'url': n.get('url', ''),
                            'published': dt.datetime.fromtimestamp(n.get('datetime', 0), dt.timezone.utc).isoformat()})
        except Exception as e:
            DIAG.append(f'ERR finnhub/{cat} {e!r}'[:160])
    return out


def rss():
    out = []
    for name, url in FEEDS.items():
        try:
            r = requests.get(url, headers=UA, timeout=25)
            DIAG.append(f'{r.status_code} {name} len={len(r.content)}')
            if not r.ok:
                continue
            root = ET.fromstring(r.content)
        except Exception as e:
            DIAG.append(f'ERR {name} {e!r}'[:160])
            continue
        items = list(root.iter('item')) or list(root.iter('{http://www.w3.org/2005/Atom}entry'))
        for it in items:
            g = lambda tag: (it.findtext(tag) or it.findtext('{http://www.w3.org/2005/Atom}' + tag) or '')
            link = g('link') or ((it.find('{http://www.w3.org/2005/Atom}link') or {}).get('href') if it.find('{http://www.w3.org/2005/Atom}link') is not None else '')
            out.append({'source': name, 'title': clean(g('title')), 'summary': clean(g('description') or g('summary'))[:1500],
                        'url': link, 'published': g('pubDate') or g('updated') or g('published')})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    seen = set()
    for f in glob.glob(os.path.join(OUT, '20*.jsonl')):
        for ln in open(f, encoding='utf-8'):
            try:
                seen.add(json.loads(ln)['id'])
            except Exception:
                pass
    now = dt.datetime.now(dt.timezone.utc)
    new = []
    for n in finnhub() + rss():
        t = tags(n['title'] + ' ' + n['summary'])
        if not t or not n['url']:
            continue
        nid = hashlib.sha1(n['url'].encode()).hexdigest()[:12]
        if nid in seen:
            continue
        seen.add(nid)
        new.append({'id': nid, 'assets': t, 'collected': now.isoformat(timespec='seconds'), **n})
    with open(os.path.join(OUT, f'{now.date()}.jsonl'), 'a', encoding='utf-8') as f:
        for n in new:
            f.write(json.dumps(n, ensure_ascii=False) + '\n')
    for f in glob.glob(os.path.join(OUT, '20*.jsonl')):           # فقط ۱۰ روز آخر
        if os.path.basename(f)[:10] < str(now.date() - dt.timedelta(days=10)):
            os.remove(f)
    per = {a: sum(a in n['assets'] for n in new) for a in ASSETS}
    DIAG.insert(0, f'{now:%Y-%m-%d %H:%M} new={len(new)} per_asset={per}')
    open(os.path.join(OUT, 'diagnostics.txt'), 'w').write('\n'.join(DIAG))
    print(DIAG[0])


if __name__ == '__main__':
    main()
