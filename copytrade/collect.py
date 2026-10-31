"""کپی ترید — جمع‌آوری معاملات «بزرگ‌ترین تریدرها» از ۴ منبع عمومی و انتخاب رهبرها.

منبع‌ها (همه عمومی، با تأخیر قانونی):
  1) 13F از Dataroma (عکس‌های روزانه‌ی data/superinvestors): خرید = سهم تازه یا افزایش ≥۲۵٪ تعداد؛ فروش = حذف یا کاهش ≥۵۰٪
  2) ARK (کتی وود): فایل‌های روزانه‌ی دارایی صندوق‌ها؛ خرید = سهم تازه یا افزایش ≥۱۰٪؛ فروش = حذف یا کاهش ≥۳۰٪
  3) نمایندگان کنگره (Finnhub congressional-trading روی سهم‌های بزرگ آمریکا)
  4) خرید گروهی مدیران شرکت‌ها (openinsider: latest cluster buys، ارزش ≥ ۲۵۰ هزار دلار)

خروجی:
  data/copytrade/events.jsonl   هر رویداد یک بار: {id, seen, leader, source, ticker, side, trade_date, ref_price}
  data/copytrade/leaders.json   رهبرها + معیار انتخاب (۳ سال بهتر از S&P 500)
  data/copytrade/ark/<date>.json عکس دارایی ARK

اجرا: python3 copytrade/collect.py [--select]   (--select: انتخاب دوباره‌ی رهبرها؛ هر شنبه یا اگر فایل نبود)
"""
import datetime as dt
import glob
import io
import json
import os
import re
import sys
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'copytrade')
SUPER = os.path.join(ROOT, 'data', 'superinvestors')
EVENTS = os.path.join(OUT, 'events.jsonl')
LEADERS = os.path.join(OUT, 'leaders.json')
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}
TODAY = str(dt.date.today())
ARK_FUNDS = {'ARKK': 'ARK_INNOVATION_ETF_ARKK_HOLDINGS', 'ARKW': 'ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS',
             'ARKQ': 'ARK_AUTONOMOUS_TECH._&_ROBOTICS_ETF_ARKQ_HOLDINGS', 'ARKG': 'ARK_GENOMIC_REVOLUTION_ETF_ARKG_HOLDINGS',
             'ARKF': 'ARK_BLOCKCHAIN_&_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS', 'ARKX': 'ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS'}
TICKER = re.compile(r'^[A-Z]{1,5}(\.[A-Z])?$')
LOG = []


def log(*a):
    s = ' '.join(str(x) for x in a)
    LOG.append(s)
    print(s)


def ev(leader, source, ticker, side, trade_date, ref_price=None, extra=None):
    t = str(ticker).upper().replace('.', '-').strip()
    if not TICKER.match(t.replace('-', '.')):
        return None
    e = {'id': f'{source}|{leader}|{t}|{side}|{trade_date}', 'seen': TODAY, 'leader': leader, 'source': source,
         'ticker': t, 'side': side, 'trade_date': trade_date,
         'ref_price': round(float(ref_price), 4) if ref_price else None}
    if extra:
        e.update(extra)
    return e


# ---------------------------------------------------------------- 1) 13F (Dataroma)
def from_13f():
    files = sorted(glob.glob(os.path.join(SUPER, '20*.json')))
    if len(files) < 2:
        log('13F: not enough snapshots')
        return []
    cur = json.load(open(files[-1], encoding='utf-8'))
    # برای هر مدیر، آخرین عکس قبلی که با امروز فرق دارد
    out = []
    for m in cur['managers']:
        now = {h['ticker']: h for h in m.get('holdings', []) if h.get('ticker')}
        prev, changed = None, cur['date']
        for f in reversed(files[:-1]):
            old = json.load(open(f, encoding='utf-8'))
            om = next((x for x in old['managers'] if x['code'] == m['code']), None)
            if om is None:
                break
            oh = {h['ticker']: h for h in om.get('holdings', []) if h.get('ticker')}
            if {k: v.get('shares') for k, v in oh.items()} != {k: v.get('shares') for k, v in now.items()}:
                prev = oh
                break
            changed = old['date']            # این عکس هنوز مثل امروز است: تغییر بعد از عکس قبلی رخ داده
        if prev is None:
            continue
        qd = changed                       # روزی که تغییر در Dataroma دیده شد
        leader = f"13F:{m['name']}"
        for t, h in now.items():
            p = prev.get(t)
            px = h['value_usd'] / h['shares'] if h.get('shares') else None
            if p is None or (p.get('shares') and h['shares'] >= 1.25 * p['shares']):
                if h.get('pct', 0) >= 1.0:          # فقط موقعیت‌های معنادار (≥۱٪ پورتفوی)
                    out.append(ev(leader, '13F', t, 'buy', qd, px, {'pct': h.get('pct')}))
        for t, p in prev.items():
            h = now.get(t)
            if h is None or (p.get('shares') and h['shares'] <= 0.5 * p['shares']):
                out.append(ev(leader, '13F', t, 'sell', qd, None))
    log(f'13F: {len(out)} events')
    return [e for e in out if e]


# ---------------------------------------------------------------- 2) ARK
def ark_snapshot():
    snap = {}
    for fund, name in ARK_FUNDS.items():
        url = f'https://assets.ark-funds.com/fund-documents/funds-etf-csv/{name}.csv'
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = [c.strip().lower() for c in df.columns]
            for _, row in df.dropna(subset=['ticker']).iterrows():
                t = str(row['ticker']).strip().upper()
                sh = float(str(row.get('shares', 0)).replace(',', '') or 0)
                val = float(str(row.get('market value ($)', row.get('market value($)', 0))).replace(',', '').replace('$', '') or 0)
                if t and sh > 0:
                    s = snap.setdefault(t, {'shares': 0.0, 'value': 0.0})
                    s['shares'] += sh
                    s['value'] += val
        except Exception as e:
            log(f'ARK {fund}: {type(e).__name__} {str(e)[:80]}')
    return snap


def from_ark():
    d = os.path.join(OUT, 'ark')
    os.makedirs(d, exist_ok=True)
    snap = ark_snapshot()
    if not snap:
        log('ARK: no data')
        return []
    json.dump(snap, open(os.path.join(d, f'{TODAY}.json'), 'w'), indent=0)
    prev_files = sorted(f for f in glob.glob(os.path.join(d, '20*.json')) if not f.endswith(f'{TODAY}.json'))
    if not prev_files:
        log('ARK: first snapshot saved')
        return []
    prev = json.load(open(prev_files[-1]))
    out = []
    for t, h in snap.items():
        p = prev.get(t)
        px = h['value'] / h['shares'] if h['shares'] else None
        if p is None or h['shares'] >= 1.10 * p['shares']:
            out.append(ev('ARK:Cathie Wood', 'ARK', t, 'buy', TODAY, px))
    for t, p in prev.items():
        h = snap.get(t)
        if h is None or h['shares'] <= 0.70 * p['shares']:
            out.append(ev('ARK:Cathie Wood', 'ARK', t, 'sell', TODAY))
    for f in prev_files[:-30]:
        os.remove(f)
    log(f'ARK: {len(out)} events')
    return [e for e in out if e]


# ---------------------------------------------------------------- 3) کنگره
def congress_universe():
    p = os.path.join(ROOT, 'data', 'pattern_hunter', 'universe_us.json')
    try:
        u = json.load(open(p))
        u = u if isinstance(u, list) else u.get('tickers', list(u))
    except Exception:
        u = []
    return [t for t in u if TICKER.match(t)][:250] or ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO']


def congress_s3(days):
    """House/Senate Stock Watcher (فایل‌های عمومی افشای معاملات) → همان قالب Finnhub."""
    cut = str(dt.date.today() - dt.timedelta(days=days))
    rows = []
    srcs = [('https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json', 'representative'),
            ('https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json', 'senator')]
    for url, who in srcs:
        try:
            r = requests.get(url, headers=UA, timeout=60)
            r.raise_for_status()
            js = r.json()
        except Exception as e:
            log(f'Congress S3 {who}: {type(e).__name__} {str(e)[:60]}')
            continue
        n0 = len(rows)
        for x in js:
            d = str(x.get('transaction_date') or '')
            if '/' in d:
                try:
                    d = str(dt.datetime.strptime(d, '%m/%d/%Y').date())
                except ValueError:
                    continue
            t = str(x.get('ticker') or '').strip().upper()
            if d >= cut and TICKER.match(t) and x.get(who):
                rows.append({'name': x[who], 'symbol': t, 'transactionDate': d, 'transactionType': x.get('type', '')})
        log(f'Congress S3 {who}: {len(rows) - n0} rows (latest {max((r["transactionDate"] for r in rows[n0:]), default="-")})')
    return rows


def congress_trades(days):
    rows = congress_s3(days)
    key = os.getenv('FINNHUB_API_KEY', '')
    if rows or not key:
        return rows
    probe = requests.get('https://finnhub.io/api/v1/stock/congressional-trading',
                         params={'symbol': 'AAPL', 'from': '2024-01-01', 'to': TODAY, 'token': key}, timeout=20)
    log(f'Congress Finnhub probe: {probe.status_code} {probe.text[:80]}')
    if probe.status_code != 200:
        return []
    frm = str(dt.date.today() - dt.timedelta(days=days))
    rows = []
    for i, t in enumerate(congress_universe()):
        try:
            r = requests.get('https://finnhub.io/api/v1/stock/congressional-trading',
                             params={'symbol': t, 'from': frm, 'to': TODAY, 'token': key}, timeout=20)
            if r.status_code == 429:
                time.sleep(30)
                continue
            for x in (r.json() or {}).get('data', []) or []:
                rows.append(dict(x, symbol=x.get('symbol') or t))
        except Exception:
            pass
        time.sleep(1.05)          # سقف ۶۰ درخواست در دقیقه
    return rows


def from_congress(rows, days=21):
    out, cut = [], str(dt.date.today() - dt.timedelta(days=days))
    for x in rows:
        td = (x.get('transactionDate') or '')[:10]
        if not td or td < cut:
            continue
        typ = (x.get('transactionType') or '').lower()
        side = 'buy' if 'purchase' in typ or typ == 'buy' else ('sell' if 'sale' in typ or 'sell' in typ else None)
        if side and x.get('name'):
            out.append(ev(f"Congress:{x['name'].strip()}", 'Congress', x['symbol'], side, td))
    log(f'Congress: {len(out)} events from {len(rows)} rows')
    return [e for e in out if e]


# ---------------------------------------------------------------- 4) خرید گروهی مدیران
def from_insiders():
    try:
        r = requests.get('http://openinsider.com/latest-cluster-buys', headers=UA, timeout=30)
        r.raise_for_status()
        tabs = pd.read_html(io.StringIO(r.text))
        df = max(tabs, key=len)
    except Exception as e:
        log(f'Insiders: {type(e).__name__} {str(e)[:80]}')
        return []
    df.columns = [re.sub(r'\W+', '', str(c)).lower() for c in df.columns]
    out = []
    for _, x in df.iterrows():
        try:
            val = float(re.sub(r'[^\d.]', '', str(x.get('value', '0'))) or 0)
            px = float(re.sub(r'[^\d.]', '', str(x.get('price', '0'))) or 0)
            td = str(x.get('tradedate', ''))[:10]
            if val >= 250000 and td:
                out.append(ev('Insiders:Cluster buys', 'Insiders', x['ticker'], 'buy', td, px or None,
                              {'insiders': int(x.get('ins', 0) or 0), 'value_usd': val}))
        except Exception:
            continue
    out = [e for e in out if e and e['trade_date'] >= str(dt.date.today() - dt.timedelta(days=10))]
    log(f'Insiders: {len(out)} events')
    return out


# ---------------------------------------------------------------- انتخاب رهبرها (شرط ۱)
def closes(tickers, period='3y'):
    import yfinance as yf
    tl = sorted(set(tickers) | {'SPY'})
    frames = []
    for i in range(0, len(tl), 150):
        df = yf.download(tl[i:i + 150], period=period, interval='1d', auto_adjust=True, progress=False, threads=True)
        c = df['Close'] if isinstance(df.columns, pd.MultiIndex) else df[['Close']].rename(columns={'Close': tl[i]})
        frames.append(c)
    return pd.concat(frames, axis=1)


def select(congress_rows):
    leaders = {}
    files = sorted(glob.glob(os.path.join(SUPER, '20*.json')))
    cur = json.load(open(files[-1], encoding='utf-8')) if files else {'managers': []}
    tick = {h['ticker'].replace('.', '-') for m in cur['managers'] for h in m.get('holdings', []) if h.get('ticker')}
    tick |= {x['symbol'] for x in congress_rows} | {'ARKK'}
    C = closes(tick)
    spy3 = float(C['SPY'].dropna().iloc[-1] / C['SPY'].dropna().iloc[0] - 1)

    def r3(t):
        s = C[t].dropna() if t in C else pd.Series(dtype=float)
        return float(s.iloc[-1] / s.iloc[0] - 1) if len(s) > 500 else None
    # 13F: بازده ۳ ساله‌ی پورتفوی فعلی (وزن‌دار) — تقریب، چون بازده واقعی صندوق منتشر نمی‌شود
    for m in cur['managers']:
        num = den = 0.0
        for h in m.get('holdings', [])[:15]:
            r = r3(h['ticker'].replace('.', '-'))
            if r is not None:
                num += h['pct'] * r
                den += h['pct']
        if den >= 40:
            ret = num / den
            leaders[f"13F:{m['name']}"] = {'source': '13F', 'ret3y': round(ret, 3), 'spy3y': round(spy3, 3),
                                          'active': ret > spy3, 'basis': 'بازده ۳ ساله‌ی ۱۵ سهم اول پورتفوی'}
    r = r3('ARKK')
    leaders['ARK:Cathie Wood'] = {'source': 'ARK', 'ret3y': r, 'spy3y': round(spy3, 3),
                                  'active': bool(r is not None and r > spy3), 'basis': 'بازده ۳ ساله‌ی ARKK'}
    # کنگره: میانگین بازده اضافه‌ی ۶ ماهه‌ی خریدهای ۳ سال اخیر نسبت به SPY (دست‌کم ۵ خرید)
    by = {}
    for x in congress_rows:
        typ = (x.get('transactionType') or '').lower()
        if ('purchase' in typ or typ == 'buy') and x.get('name') and x['symbol'] in C:
            by.setdefault(x['name'].strip(), []).append((x['symbol'], (x.get('transactionDate') or '')[:10]))
    for name, buys in by.items():
        ex = []
        for t, d in buys:
            try:
                s, b = C[t].dropna(), C['SPY'].dropna()
                i0 = s.index.searchsorted(pd.Timestamp(d))
                j0 = b.index.searchsorted(pd.Timestamp(d))
                if i0 + 126 < len(s) and j0 + 126 < len(b):
                    ex.append((s.iloc[i0 + 126] / s.iloc[i0]) - (b.iloc[j0 + 126] / b.iloc[j0]))
            except Exception:
                continue
        if len(ex) >= 5:
            avg = sum(ex) / len(ex)
            leaders[f'Congress:{name}'] = {'source': 'Congress', 'excess6m': round(float(avg), 3), 'n': len(ex),
                                           'active': avg > 0, 'basis': 'میانگین بازده اضافه‌ی ۶ ماهه‌ی خریدها نسبت به S&P 500'}
    leaders['Insiders:Cluster buys'] = {'source': 'Insiders', 'active': True,
                                        'basis': 'خرید گروهی مدیران (دست‌کم ۲ مدیر، ≥۲۵۰ هزار دلار) — بدون رتبه‌بندی فردی'}
    n = sum(v['active'] for v in leaders.values())
    log(f'select: {n}/{len(leaders)} leaders pass (SPY 3y {spy3:+.0%})')
    return {'date': TODAY, 'spy3y': round(spy3, 3), 'leaders': leaders}


# ---------------------------------------------------------------- اجرا
def main():
    os.makedirs(OUT, exist_ok=True)
    seen = set()
    if os.path.exists(EVENTS):
        seen = {json.loads(l)['id'] for l in open(EVENTS, encoding='utf-8') if l.strip()}
    need_select = '--select' in sys.argv or not os.path.exists(LEADERS) or dt.date.today().weekday() == 5
    crows = congress_trades(3 * 365 if need_select else 30)
    events = from_13f() + from_ark() + from_congress(crows) + from_insiders()
    new = [e for e in events if e['id'] not in seen]
    with open(EVENTS, 'a', encoding='utf-8') as f:
        for e in new:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    log(f'new events: {len(new)} (total sources: 13F/ARK/Congress/Insiders)')
    if need_select:
        try:
            json.dump(select(crows), open(LEADERS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        except Exception as e:
            log(f'select failed: {e}')
    json.dump({'date': TODAY, 'new': len(new), 'log': LOG}, open(os.path.join(OUT, 'last_run.json'), 'w'),
              ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
