"""شکارچی روش — جمع‌آوری ادعاهای سود از فروم‌ها و سایت‌ها (بدون کلید API).

منابع: Reddit (JSON/RSS)، Hacker News (Algolia)، StackExchange Quant، Medium (RSS برچسب‌ها)، dev.to.
هر پست با واژه‌های «روش + ادعای عددی سود» امتیاز می‌گیرد؛ پست‌های بالای آستانه در inbox.jsonl ذخیره می‌شوند.
خروجی: data/strategy_hunter/inbox.jsonl (بدون تکرار، بر اساس url) و diagnostics.txt
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'strategy_hunter')
INBOX = os.path.join(OUT, 'inbox.jsonl')
UA = {'User-Agent': 'strategy-hunter/1.0 (research; contact mahdi.salehi.sichani@gmail.com)'}
SUBS = ['algotrading', 'Daytrading', 'Forex', 'options', 'thetagang', 'swingtrading', 'CryptoMarkets', 'Trading']
MEDIUM_TAGS = ['trading-strategy', 'algorithmic-trading', 'forex-trading', 'crypto-trading', 'options-trading',
               'day-trading', 'backtesting']
MARKET = re.compile(r'\b(trad\w*|stocks?|forex|fx|crypto|bitcoin|btc|eth|options?|futures|spy|qqq|s&p|nasdaq|'
                    r'portfolio|backtest\w*|scalp\w*|swing|day ?trad\w*|pips?|candles?)\b', re.I)
STRAT = re.compile(r'\b(strateg\w*|setup|system|indicator|rsi|macd|ema|sma|moving average|breakout|bollinger|'
                   r'scalp\w*|grid|martingale|dca|wheel|iron condor|credit spread|covered call|mean reversion|'
                   r'momentum|backtest\w*|ichimoku|fibonacci|vwap|supertrend|orb|opening range)\b', re.I)
CLAIM = re.compile(r'(\d{2,5}(?:\.\d+)?\s?%|\bwin ?rate\b|\bprofit factor\b|\bsharpe\b|\bcagr\b|'
                   r'\bx\d{1,3}\b|\b\d+x\b|\bdoubled?\b|\bper (?:day|week|month)\b|\$\d{3,}[kK]?)', re.I)
DIAG = []


def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=25, **kw)
        DIAG.append(f'{r.status_code} {url[:90]} len={len(r.content)}')
        return r if r.status_code == 200 else None
    except Exception as e:
        DIAG.append(f'ERR {url[:90]} {e!r}'[:200])
        return None


def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))
    return re.sub(r'\s+', ' ', s).strip()


def score(title, text):
    t = f'{title} {text}'
    if not MARKET.search(t):
        return 0
    s = len(set(m.lower() for m in STRAT.findall(t)))
    c = len(CLAIM.findall(t))
    return (min(s, 4) + min(c, 4)) if s and c else 0


def reddit():
    """JSON از سرورهای GitHub مسدود است (403)؛ RSS با فاصله‌ی زمانی کار می‌کند ولی سقف درخواست دارد (429)."""
    out = []
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    for sub in SUBS:
        r = None
        for wait in (0, 20):
            time.sleep(wait or 7)
            r = get(f'https://www.reddit.com/r/{sub}/top/.rss', params={'t': 'day', 'limit': 25})
            if r:
                break
        if not r:
            continue
        try:
            for e in ET.fromstring(r.content).findall('a:entry', ns):
                out.append(('reddit/' + sub, e.findtext('a:title', '', ns), clean(e.findtext('a:content', '', ns)),
                            e.find('a:link', ns).get('href'), 0))
        except ET.ParseError:
            pass
    return out


def rss_sites():
    """وبلاگ‌ها و فروم‌های معامله‌گری با RSS عمومی."""
    feeds = {'quantifiedstrategies': 'https://www.quantifiedstrategies.com/feed/',
             'quantpedia': 'https://quantpedia.com/feed/',
             'babypips-forum': 'https://forums.babypips.com/latest.rss',
             'elitetrader': 'https://www.elitetrader.com/et/forums/-/index.rss',
             'tradingview-ideas': 'https://www.tradingview.com/feed/?sort=recent',
             'robotwealth': 'https://robotwealth.com/feed/',
             'forexfactory': 'https://www.forexfactory.com/rss.php'}
    out = []
    for name, url in feeds.items():
        r = get(url)
        if not r:
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        for it in root.iter('item'):
            body = it.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or it.findtext('description') or ''
            out.append((name, it.findtext('title', ''), clean(body)[:4000], it.findtext('link', ''), 0))
    return out


def hackernews():
    out = []
    since = int(time.time()) - 3 * 86400
    for q in ('trading strategy', 'backtest', 'algorithmic trading'):
        r = get('https://hn.algolia.com/api/v1/search_by_date',
                params={'query': q, 'tags': '(story,comment)', 'numericFilters': f'created_at_i>{since}', 'hitsPerPage': 50})
        if r:
            for h in r.json().get('hits', []):
                url = h.get('url') or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                out.append(('hackernews', h.get('title') or h.get('story_title') or '',
                            clean(h.get('comment_text') or h.get('story_text') or ''), url, h.get('points') or 0))
    return out


def stackexchange():
    out = []
    r = get('https://api.stackexchange.com/2.3/search/excerpts',
            params={'site': 'quant', 'q': 'strategy return', 'sort': 'creation', 'order': 'desc', 'pagesize': 50})
    if r:
        for it in r.json().get('items', []):
            out.append(('stackexchange/quant', clean(it.get('title', '')), clean(it.get('excerpt', '')),
                        f"https://quant.stackexchange.com/q/{it.get('question_id')}", it.get('score', 0)))
    return out


def medium():
    out = []
    for tag in MEDIUM_TAGS:
        r = get(f'https://medium.com/feed/tag/{tag}')
        if not r:
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        for it in root.iter('item'):
            body = it.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or it.findtext('description') or ''
            out.append(('medium/' + tag, it.findtext('title', ''), clean(body)[:4000], it.findtext('link', ''), 0))
    return out


def devto():
    out = []
    for tag in ('trading', 'algotrading', 'forex', 'crypto'):
        r = get('https://dev.to/api/articles', params={'tag': tag, 'per_page': 30, 'top': 3})
        if r:
            for a in r.json():
                out.append(('dev.to/' + tag, a.get('title', ''), a.get('description', ''), a.get('url', ''),
                            a.get('public_reactions_count', 0)))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    seen = set()
    if os.path.exists(INBOX):
        for ln in open(INBOX, encoding='utf-8'):
            try:
                seen.add(json.loads(ln)['url'])
            except Exception:
                pass
    found = []
    counts = {}
    for fn in (reddit, rss_sites, hackernews, stackexchange, medium, devto):
        try:
            items = fn()
        except Exception as e:
            DIAG.append(f'{fn.__name__} failed {e!r}'[:200])
            items = []
        counts[fn.__name__] = len(items)
        for src, title, text, url, pop in items:
            sc = score(title, text)
            if sc >= 3 and url and url not in seen:
                seen.add(url)
                found.append({'id': hashlib.sha1(url.encode()).hexdigest()[:10], 'source': src, 'title': clean(title)[:300],
                              'text': clean(text)[:3000], 'url': url, 'popularity': pop, 'score': sc,
                              'found_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'status': 'new'})
    with open(INBOX, 'a', encoding='utf-8') as f:
        for x in found:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    DIAG.insert(0, f'{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} raw={counts} new_claims={len(found)}')
    open(os.path.join(OUT, 'harvest_diagnostics.txt'), 'w').write('\n'.join(DIAG))
    print(DIAG[0])


if __name__ == '__main__':
    main()
