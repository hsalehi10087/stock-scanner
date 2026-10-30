"""خبرخوان بازار — جمع‌آوری خبرهای طلا، نقره، بیت‌کوین، مس، نفت و نرخ بهره (هر چند ساعت).

منابع: Finnhub (general، forex، crypto) + RSS سایت‌های خبری تخصصی. فقط جمع‌آوری؛ «درک خبر» و استخراج
نظر تحلیلگران را کار زمان‌بندی‌شده‌ی Claude انجام می‌دهد و در data/analyst_views/latest.json می‌نویسد.
خروجی: data/news/YYYY-MM-DD.jsonl (۱۰ روز آخر نگه داشته می‌شود) و data/news/diagnostics.txt

هر خبر: id, assets, primary, collected, source, publisher, title, summary, url, gnews_url, source_url, body, published
 (برای خبرهای Google News: url و source_url = نشانی اصلی خبر، gnews_url = لینک واسط Google)
 - تکراری‌ها (همان نشانی یا همان تیتر از چند رسانه) حذف می‌شوند.
 - منابع فهرست market_intel/news_blocklist.txt کنار گذاشته می‌شوند.
 - primary = دارایی‌هایی که در خود تیتر آمده‌اند (برای شمارش)، assets = همه‌ی دارایی‌های مرتبط.
 - لینک‌های news.google.com به نشانی اصلی تبدیل می‌شوند و چند پاراگراف اول متن خبر در body ذخیره می‌شود
   تا کار روزانه بدون باز کردن لینک‌ها متن را داشته باشد.
"""
import concurrent.futures as cf
import datetime as dt
import glob
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'news')
BLOCKLIST = os.path.join(ROOT, 'market_intel', 'news_blocklist.txt')
KEY = os.getenv('FINNHUB_API_KEY', '')
SAVE = os.getenv('NEWS_SAVE', '1') != '0'
UA = {'User-Agent': 'Mozilla/5.0 (compatible; market-intel-news/1.0)'}
BROWSER = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/124.0 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.9'}
ENRICH_MAX = int(os.getenv('NEWS_ENRICH_MAX', '120'))      # حداکثر خبر برای گرفتن متن در هر اجرا
ENRICH_SECONDS = int(os.getenv('NEWS_ENRICH_SECONDS', '360'))
BODY_CHARS = 2000
ASSETS = {
    'gold': r'\b(gold|bullion|xau)\b',
    'silver': r'\b(silver|xag)\b',
    'bitcoin': r'\b(bitcoin|btc|crypto(?:currency|currencies)?)\b',
    'copper': r'\b(copper)\b',
    'oil': r'\b(oil|crude|brent|wti|opec\+?)\b',
    'ai': r'\b(artificial intelligence|a\.?i\.? (?:chips?|stocks?|models?|infrastructure|startups?|agents?|demand|spending|capex)|genai|generative ai|llms?|data ?cent(?:er|re)s?|gpus?|nvidia|openai|anthropic|hyperscalers?)\b',
    'rates': r'\b(fed|fomc|powell|warsh|rate cut|rate hike|interest rates?|treasury yields?|bond yields?|inflation|cpi|pce|ecb|boj)\b',
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


# ---------- تیتر، ناشر، تکراری‌ها، فهرست سیاه ----------

def split_publisher(title):
    """تیترهای Google News به شکل «تیتر - ناشر» هستند."""
    m = re.match(r'^(.*\S)\s+-\s+([^-]{2,60})$', title or '')
    return (m.group(1), m.group(2).strip()) if m else (title or '', '')


def title_key(title):
    t, _ = split_publisher(title)
    t = re.sub(r'[^a-z0-9$%. ]+', ' ', t.lower())
    return re.sub(r'\s+', ' ', t).strip()[:90]


def load_blocklist(path=BLOCKLIST):
    pubs, patterns = {}, []
    try:
        lines = open(path, encoding='utf-8').read().splitlines()
    except OSError:
        return pubs, patterns
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        if ln.startswith('re:'):
            patterns.append(re.compile(ln[3:].strip(), re.I))
            continue
        name, _, scope = ln.partition(':')
        pubs[name.strip().lower()] = {a.strip() for a in scope.split(',') if a.strip()} or None
    return pubs, patterns


def apply_blocklist(item, assets, block):
    """دارایی‌های باقی‌مانده را برمی‌گرداند؛ فهرست خالی یعنی خبر کنار گذاشته شود."""
    pubs, patterns = block
    if any(p.search(item['title']) for p in patterns):
        return []
    for name in (item.get('publisher', ''), item.get('source', '')):
        scope = pubs.get((name or '').lower(), 0)
        if scope is None:
            return []
        if scope:
            assets = [a for a in assets if a not in scope]
    return assets


# ---------- منابع ----------

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
                out.append({'source': n.get('source') or 'finnhub', 'publisher': n.get('source') or '',
                            'title': n.get('headline', ''),
                            'summary': clean(n.get('summary', ''))[:1500], 'url': n.get('url', ''),
                            'published': dt.datetime.fromtimestamp(n.get('datetime', 0), dt.timezone.utc).isoformat()})
        except Exception as e:
            DIAG.append(f'ERR finnhub/{cat} {e!r}'[:160])
    return out


def rss():
    out = []
    atom = '{http://www.w3.org/2005/Atom}'
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
        items = list(root.iter('item')) or list(root.iter(atom + 'entry'))
        for it in items:
            g = lambda tag: (it.findtext(tag) or it.findtext(atom + tag) or '')
            link = g('link')
            if not link and it.find(atom + 'link') is not None:
                link = it.find(atom + 'link').get('href', '')
            title = clean(g('title'))
            publisher = clean(g('source')) or (split_publisher(title)[1] if name.startswith('googlenews') else name)
            summary = clean(g('description') or g('summary'))
            if name.startswith('googlenews'):
                summary = ''          # در Google News توضیح فقط همان تیتر و نام ناشر است
            out.append({'source': name, 'publisher': publisher, 'title': title, 'summary': summary[:1500],
                        'url': link, 'published': g('pubDate') or g('updated') or g('published')})
    return out


# ---------- تبدیل لینک Google News و گرفتن متن ----------

def gnews_decode(url, session):
    """نشانی اصلی یک لینک news.google.com/rss/articles/... را برمی‌گرداند (یا None)."""
    m = re.search(r'news\.google\.com/(?:rss/)?articles/([^?/]+)', url or '')
    if not m:
        return None
    art = m.group(1)
    sig = ts = None
    for base in ('https://news.google.com/articles/', 'https://news.google.com/rss/articles/'):
        try:
            r = session.get(base + art, headers=BROWSER, timeout=15)
        except requests.RequestException:
            continue
        if r.ok:
            s = re.search(r'data-n-a-sg="([^"]+)"', r.text)
            t = re.search(r'data-n-a-ts="([^"]+)"', r.text)
            if s and t:
                sig, ts = s.group(1), t.group(1)
                break
    if not sig:
        return None
    inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
             f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{art}",{ts},"{sig}"]')
    body = 'f.req=' + urllib.parse.quote(json.dumps([[['Fbv4je', inner]]]))
    try:
        r = session.post('https://news.google.com/_/DotsSplashUi/data/batchexecute', data=body, timeout=15,
                         headers={**BROWSER, 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})
        if not r.ok:
            return None
        payload = json.loads(r.text.split('\n\n', 1)[1])[:-2]
        decoded = json.loads(payload[0][2])[1]
        return decoded if str(decoded).startswith('http') else None
    except Exception:
        return None


BOILER = re.compile(r'cookie|subscribe|sign up|newsletter|all rights reserved|javascript|advertisement|'
                    r'privacy policy|terms of (use|service)|log ?in to|read more:|click here', re.I)


def extract_body(page):
    """چند پاراگراف اول متن خبر از HTML (بدون کتابخانه‌ی جانبی)."""
    h = re.sub(r'(?is)<(script|style|noscript|header|footer|nav|aside|form|figure)\b[^>]*>.*?</\1>', ' ', page or '')
    m = re.search(r'(?is)<article\b[^>]*>(.*?)</article>', h)
    src = m.group(1) if m and len(m.group(1)) > 500 else h
    paras = [clean(p) for p in re.findall(r'(?is)<p\b[^>]*>(.*?)</p>', src)]
    paras = [p for p in paras if len(p) > 60 and not BOILER.search(p)]
    txt = ''
    for p in paras:
        if len(txt) + len(p) > BODY_CHARS:
            txt += ' ' + p[:max(0, BODY_CHARS - len(txt))]
            break
        txt += ' ' + p
    txt = txt.strip()
    if len(txt) < 200:
        og = re.search(r'(?is)<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]*'
                       r'content=["\']([^"\']+)', page or '')
        if og and len(clean(og.group(1))) > len(txt):
            txt = clean(og.group(1))
    return txt


def enrich(item):
    """لینک Google News را باز می‌کند و متن خبر را می‌گیرد. خطاها بی‌صدا رد می‌شوند."""
    s = requests.Session()
    url = item['url']
    if 'news.google.com' in url:
        real = gnews_decode(url, s)
        if not real:
            return 'gnews_fail'
        item['gnews_url'], item['url'], item['source_url'] = url, real, real
    try:
        r = s.get(item['url'], headers=BROWSER, timeout=15)
    except requests.RequestException:
        return 'fetch_err'
    if not r.ok or 'html' not in r.headers.get('Content-Type', 'html'):
        return f'http_{r.status_code}'
    body = extract_body(r.text)
    if len(body) < 120:
        return 'no_body'
    item['body'] = body
    return 'ok'


def enrich_all(items):
    # همه‌ی خبرها (کالاها و AI)؛ اگر بیش از سقف بود، خبرهای Google News که بدون باز کردن لینک قابل‌استفاده نیستند اول
    todo = sorted(items, key=lambda n: 'news.google.com' not in n['url'])[:ENRICH_MAX]
    stats, deadline = {}, time.time() + ENRICH_SECONDS
    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(enrich, n): n for n in todo}
        try:
            for f in cf.as_completed(futs, timeout=max(1, deadline - time.time())):
                try:
                    k = f.result()
                except Exception:
                    k = 'error'
                stats[k] = stats.get(k, 0) + 1
        except cf.TimeoutError:
            stats['timeout'] = sum(not f.done() for f in futs)
            for f in futs:
                f.cancel()
    DIAG.append(f'enrich tried={len(todo)} {stats}')


# ---------- اجرا ----------

def load_seen():
    ids, keys = set(), set()
    for f in glob.glob(os.path.join(OUT, '20*.jsonl')):
        for ln in open(f, encoding='utf-8'):
            try:
                n = json.loads(ln)
            except Exception:
                continue
            ids.add(n.get('id'))
            keys.add(title_key(n.get('title', '')))
    keys.discard('')
    return ids, keys


def main():
    os.makedirs(OUT, exist_ok=True)
    seen, seen_titles = load_seen()
    block = load_blocklist()
    now = dt.datetime.now(dt.timezone.utc)
    new, skipped = [], {'dup_url': 0, 'dup_title': 0, 'blocked': 0}
    for n in finnhub() + rss():
        if not n['url']:
            continue
        assets = tags(n['title'] + ' ' + n['summary'])
        if not assets:
            continue
        nid = hashlib.sha1(n['url'].encode()).hexdigest()[:12]
        if nid in seen:
            skipped['dup_url'] += 1
            continue
        tk = title_key(n['title'])
        if tk and tk in seen_titles:
            skipped['dup_title'] += 1
            continue
        assets = apply_blocklist(n, assets, block)
        if not assets:
            skipped['blocked'] += 1
            continue
        seen.add(nid)
        seen_titles.add(tk)
        primary = [a for a in tags(split_publisher(n['title'])[0]) if a in assets] or assets
        new.append({'id': nid, 'assets': assets, 'primary': primary,
                    'collected': now.isoformat(timespec='seconds'), **n})
    enrich_all(new)
    if SAVE:
        with open(os.path.join(OUT, f'{now.date()}.jsonl'), 'a', encoding='utf-8') as f:
            for n in new:
                f.write(json.dumps(n, ensure_ascii=False) + '\n')
        for f in glob.glob(os.path.join(OUT, '20*.jsonl')):           # فقط ۱۰ روز آخر
            if os.path.basename(f)[:10] < str(now.date() - dt.timedelta(days=10)):
                os.remove(f)
    per = {a: sum(a in n['assets'] for n in new) for a in ASSETS}
    bodies = sum(bool(n.get('body')) for n in new)
    DIAG.insert(0, f'{now:%Y-%m-%d %H:%M} new={len(new)} with_body={bodies} skipped={skipped} per_asset={per}')
    if SAVE:
        open(os.path.join(OUT, 'diagnostics.txt'), 'w').write('\n'.join(DIAG))
    else:
        for n in new[:15]:
            print('-', n['publisher'], '|', n['title'][:90], '|', n['url'][:80], '| body', len(n.get('body', '')))
    print('\n'.join(DIAG))


if __name__ == '__main__':
    main()
