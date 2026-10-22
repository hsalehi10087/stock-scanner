"""الگویاب — بخش‌های مشترک: فهرست سهام ۵ بازار، دانلود قیمت، و ساخت ویژگی‌های «رفتار قیمت و حجم».

ویژگی‌ها فقط از قیمت و حجم ساخته می‌شوند (داده‌ی بنیادی تاریخی رایگان نیست). هر ویژگی در روز t فقط از داده‌ی
تا همان روز استفاده می‌کند. برچسب «برنده» = قیمت در ۱۲ ماه بعد دست‌کم ۲ برابر شده باشد.
"""
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'pattern_hunter')
UA = {'User-Agent': 'Mozilla/5.0 (compatible; pattern-hunter/1.0)'}
MARKETS = {
    'us': {'fa': 'آمریکا', 'index': 'SPY', 'cap': 1500},
    'cn': {'fa': 'چین', 'index': '000300.SS', 'cap': 1500},
    'in': {'fa': 'هند', 'index': '^NSEI', 'cap': 1000},
    'jp': {'fa': 'ژاپن', 'index': '1306.T', 'cap': 1500},
    'tw': {'fa': 'تایوان', 'index': '0050.TW', 'cap': 1200},
}
FEATURES = ['r1m', 'r3m', 'r6m', 'r12m', 'from_hi', 'from_lo', 'above50', 'above200', 'slope50', 'vol20',
            'vol_ratio', 'volu_ratio', 'dd12m', 'log_price', 'log_dollar_vol', 'rs6m', 'up_days_ratio', 'range_pos']
FA_FEAT = {'r1m': 'بازده ۱ ماهه', 'r3m': 'بازده ۳ ماهه', 'r6m': 'بازده ۶ ماهه', 'r12m': 'بازده ۱۲ ماهه',
           'from_hi': 'فاصله از سقف ۵۲ هفته', 'from_lo': 'فاصله از کف ۵۲ هفته', 'above50': 'نسبت به میانگین ۵۰ روزه',
           'above200': 'نسبت به میانگین ۲۰۰ روزه', 'slope50': 'شیب میانگین ۵۰ روزه', 'vol20': 'نوسان ۲۰ روزه',
           'vol_ratio': 'نوسان کوتاه به بلند', 'volu_ratio': 'حجم ۲۰ روزه به ۱۲۰ روزه', 'dd12m': 'بیشترین افت ۱۲ ماه',
           'log_price': 'سطح قیمت', 'log_dollar_vol': 'اندازه‌ی معاملات (نقدشوندگی)', 'rs6m': 'قدرت نسبی ۶ ماهه در برابر شاخص',
           'up_days_ratio': 'سهم روزهای مثبت ۳ ماه', 'range_pos': 'جای قیمت در دامنه‌ی ۳ ماه'}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------- فهرست سهام ----------------
def _wiki(url, col):
    r = requests.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    t = [x for x in pd.read_html(io.StringIO(r.text)) if col in x.columns][0]
    return {str(s).replace('.', '-'): str(n) for s, n in zip(t[col], t[t.columns[1]])}


def universe(m):
    cache = os.path.join(OUT, f'universe_raw_{m}.json')
    try:
        if m == 'us':
            u = {}
            for url in ('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies',
                        'https://en.wikipedia.org/wiki/List_of_S%26P_400_companies',
                        'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'):
                try:
                    u.update(_wiki(url, 'Symbol'))
                except Exception as e:
                    log('wiki', url, e)
        elif m == 'in':
            u = {}
            for url in ('https://archives.nseindia.com/content/indices/ind_nifty500list.csv',
                        'https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv',
                        'https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv'):
                try:
                    r = requests.get(url, headers=UA, timeout=40)
                    r.raise_for_status()
                    df = pd.read_csv(io.StringIO(r.text))
                    u.update({f'{s}.NS': n for s, n in zip(df['Symbol'], df['Company Name'])})
                except Exception as e:
                    log('nse', url, e)
        elif m == 'jp':
            sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
            sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
            from jp_growth import tse_list
            u = {k: v for k, v in tse_list().items() if k[:4].isdigit() and 1300 <= int(k[:4]) <= 9999}
        elif m == 'cn':
            u = {}
            for f, suf in (('universe_sse.csv', '.SS'), ('universe_szse.csv', '.SZ')):
                df = pd.read_csv(os.path.join(ROOT, 'data', 'cn_gainers', f), dtype=str)
                c = [x for x in df.columns if 'sym' in x.lower() or 'code' in x.lower() or 'ticker' in x.lower()][0]
                n = [x for x in df.columns if 'name' in x.lower()]
                for i, s in enumerate(df[c]):
                    s = str(s).strip()
                    s = s if s.endswith(suf) else s.zfill(6) + suf
                    if s[:6].isdigit() and s[:3] in ('600', '601', '603', '605', '000', '001', '002', '003', '300', '301', '688'):
                        u[s] = str(df[n[0]].iloc[i]) if n else ''
        elif m == 'tw':
            sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
            sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
            from tw_growth import tpex_list, twse_list
            u = {**twse_list(), **tpex_list()}
        if len(u) < 50:
            raise ValueError(f'universe too small: {len(u)}')
        os.makedirs(OUT, exist_ok=True)
        json.dump(u, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
        return u
    except Exception as e:
        log('universe fetch failed, using cache:', m, e)
        return json.load(open(cache, encoding='utf-8'))


# ---------------- قیمت ----------------
def download(tickers, period=None, start=None, chunk=150):
    import yfinance as yf
    closes, vols = {}, {}
    tl = list(tickers)
    for i in range(0, len(tl), chunk):
        part = tl[i:i + chunk]
        for attempt in range(2):
            try:
                df = yf.download(part, period=period, start=start, interval='1d', auto_adjust=True, progress=False,
                                 group_by='ticker', threads=True)
                break
            except Exception as e:
                log('download retry', i, e)
                time.sleep(10)
        else:
            continue
        for t in part:
            try:
                d = df[t] if len(part) > 1 else df
                c = d['Close'].dropna()
                if len(c) > 260:
                    closes[t] = c
                    vols[t] = d['Volume'].reindex(c.index).fillna(0)
            except Exception:
                pass
        log(f'downloaded {i + len(part)}/{len(tl)} ok={len(closes)}')
    C = pd.DataFrame(closes).sort_index()
    V = pd.DataFrame(vols).reindex(C.index)
    return C, V


# ---------------- ویژگی‌ها ----------------
def features(c, v, idx_close):
    """c, v: سری قیمت و حجم یک سهم؛ خروجی DataFrame ویژگی‌ها برای هر روز."""
    r = c.pct_change()
    hi, lo = c.rolling(252).max(), c.rolling(252).min()
    s50, s200 = c.rolling(50).mean(), c.rolling(200).mean()
    ic = idx_close.reindex(c.index).ffill()
    dv = (c * v).rolling(60).median()
    f = pd.DataFrame({
        'r1m': c / c.shift(21) - 1, 'r3m': c / c.shift(63) - 1, 'r6m': c / c.shift(126) - 1, 'r12m': c / c.shift(252) - 1,
        'from_hi': c / hi - 1, 'from_lo': c / lo - 1, 'above50': c / s50 - 1, 'above200': c / s200 - 1,
        'slope50': s50 / s50.shift(20) - 1, 'vol20': r.rolling(20).std() * np.sqrt(252),
        'vol_ratio': r.rolling(20).std() / r.rolling(120).std(),
        'volu_ratio': v.rolling(20).mean() / v.rolling(120).mean().replace(0, np.nan),
        'dd12m': (c / c.rolling(252).max()).rolling(252).min() - 1,
        'log_price': np.log(c.clip(lower=0.01)), 'log_dollar_vol': np.log1p(dv),
        'rs6m': (c / c.shift(126)) / (ic / ic.shift(126)) - 1,
        'up_days_ratio': (r > 0).rolling(63).mean(),
        'range_pos': (c - c.rolling(63).min()) / (c.rolling(63).max() - c.rolling(63).min()).replace(0, np.nan),
    }, index=c.index)
    return f.replace([np.inf, -np.inf], np.nan)


def fa_digits(x):
    return str(x).translate(str.maketrans('0123456789.-', '۰۱۲۳۴۵۶۷۸۹٫−'))
