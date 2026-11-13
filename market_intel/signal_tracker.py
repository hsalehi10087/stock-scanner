"""پیگیری سیگنال‌ها: هر سهم چند بار سیگنال شده و از روز اولین سیگنال چقدر بازده داده.

وضعیت در data/signal_tracker/<kind>.json ذخیره می‌شود:
  {ticker: {first_date, first_price, count, last_date, events:[...]}}
  - gainers: هر روزی که سهم بیش از ۱۰٪ رشد کرده یک «بار» است (events = تاریخ‌ها)
  - fundamentals: هر فصلی که رشد سود بیش از ۱۰٪ گزارش شده یک «بار» است (events = فصل‌ها)؛
    تکرار روزانه‌ی همان فصل در گزارش، سیگنال تازه حساب نمی‌شود.
قیمت مبنا = قیمت بسته‌شدن روز اولین سیگنال (یعنی بعد از جهش؛ بدون نگاه به آینده).
"""
import glob
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'data', 'signal_tracker')
since_of = {}
FA_DIGITS = str.maketrans('0123456789.-+', '۰۱۲۳۴۵۶۷۸۹٫−+')


def fa(x):
    return str(x).translate(FA_DIGITS)


def _path(kind):
    return os.path.join(DIR, f'{kind}.json')


def load(kind):
    p = _path(kind)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def save(kind, state):
    os.makedirs(DIR, exist_ok=True)
    json.dump(state, open(_path(kind), 'w', encoding='utf-8'), ensure_ascii=False, indent=0, sort_keys=True)


def add(state, ticker, date, event, price, extra=None):
    s = state.get(ticker)
    if s is None:
        if price is None or not price > 0:
            return
        state[ticker] = {'first_date': date, 'first_price': round(float(price), 4), 'count': 1,
                         'last_date': date, 'events': [event]}
        if extra:
            state[ticker].update(extra)   # مثلاً امتیاز کیفیت روز اولین سیگنال، برای سنجش بعدی معیارها
    elif event not in s['events']:
        s['events'].append(event)
        s['count'] = len(s['events'])
        s['last_date'] = date


def close_on(tickers, dates):
    """قیمت بسته‌شدن هر نماد در تاریخ مشخص (یا آخرین روز معاملاتی قبل از آن)."""
    import yfinance as yf
    out = {}
    if not tickers:
        return out
    start = (pd.Timestamp(min(dates.values())) - pd.Timedelta(days=10)).date()
    tl = sorted(tickers)
    for i in range(0, len(tl), 200):
        part = tl[i:i + 200]
        try:
            df = yf.download(part, start=str(start), interval='1d', group_by='ticker', threads=True,
                             progress=False, auto_adjust=False)
        except Exception as e:
            print('⚠️ close_on', e, file=sys.stderr)
            continue
        for t in part:
            try:
                c = (df[t]['Close'] if len(part) > 1 else df['Close']).dropna()
                c = c[c.index <= pd.Timestamp(dates[t]) + pd.Timedelta(hours=23)]
                if len(c):
                    out[t] = float(c.iloc[-1])
            except Exception:
                continue
    return out


def last_prices(tickers):
    import yfinance as yf
    out = {}
    tl = sorted(tickers)
    for i in range(0, len(tl), 200):
        part = tl[i:i + 200]
        try:
            df = yf.download(part, period='5d', interval='1d', group_by='ticker', threads=True,
                             progress=False, auto_adjust=False)
        except Exception as e:
            print('⚠️ last_prices', e, file=sys.stderr)
            continue
        for t in part:
            try:
                c = (df[t]['Close'] if len(part) > 1 else df['Close']).dropna()
                if len(c):
                    out[t] = float(c.iloc[-1])
            except Exception:
                continue
    return out


def price_vol(tickers, days=90):
    """قیمت آخر، میانگین حجم ۵ روزه (نقدشوندگی)، نوسان‌پذیری سالانه و بزرگ‌ترین پرش یک‌روزه (ریسک میس سود) برای
    یک لیست نماد، از ۹۰ روز اخیر؛ برای کنار گذاشتن سهام کم‌حجم/وارانت/پرنوسانِ آسیب‌پذیر در برابر میس سود."""
    import numpy as np
    import yfinance as yf
    out = {}
    tl = sorted(tickers)
    for i in range(0, len(tl), 200):
        part = tl[i:i + 200]
        try:
            df = yf.download(part, period=f'{days}d', interval='1d', group_by='ticker', threads=True,
                             progress=False, auto_adjust=False)
        except Exception as e:
            print('⚠️ price_vol', e, file=sys.stderr)
            continue
        for t in part:
            try:
                sub = df[t] if len(part) > 1 else df
                c, v = sub['Close'].dropna(), sub['Volume'].dropna()
                if not len(c):
                    continue
                r = c.pct_change().dropna()
                out[t] = {'price': float(c.iloc[-1]), 'volume': float(v.tail(5).mean()) if len(v) else 0.0,
                          'ann_vol': float(r.std() * np.sqrt(252)) if len(r) >= 10 else None,
                          'max_abs_move': float(r.abs().max()) if len(r) >= 10 else None}
            except Exception:
                continue
    return out


def bootstrap(kind, hist_dir, event_col=None, price_col=None):
    """بار اول، وضعیت را از فایل‌های تاریخچه‌ی موجود بازسازی می‌کند."""
    state, need = {}, {}
    files = sorted(glob.glob(os.path.join(hist_dir, '20*.csv')))
    for f in files:
        date = os.path.basename(f)[:10]
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        for _, r in df.iterrows():
            t = str(r['ticker'])
            ev = str(r[event_col]) if event_col else date
            if price_col:
                add(state, t, date, ev, float(r[price_col]))
            elif t in state:
                add(state, t, date, ev, None)
            elif t not in need:
                need[t] = (date, ev)
                state[t] = {'first_date': date, 'first_price': None, 'count': 1, 'last_date': date, 'events': [ev]}
    if need:
        px = close_on(list(need), {t: d for t, (d, _) in need.items()})
        for t in need:
            if t in px:
                state[t]['first_price'] = round(px[t], 4)
            else:
                state.pop(t, None)
    return state


def split_factors(tickers, since):
    """ضریب تقسیم سهام (split) پس از تاریخ اولین سیگنال: {ticker: ضرب همه‌ی نسبت‌ها}. نسبت > ۱ یعنی تقسیم عادی (مثلاً ۱۰ به ۱)
    و < ۱ یعنی تقسیم معکوس. اگر داده نیامد، نماد در نتیجه نیست."""
    import yfinance as yf
    out = {}
    tl = sorted(tickers)
    for i in range(0, len(tl), 100):
        part = tl[i:i + 100]
        try:
            df = yf.download(part, start=str(since), interval='1d', group_by='ticker', threads=True, progress=False,
                             auto_adjust=False, actions=True)
        except Exception as e:
            print('⚠️ split_factors', e, file=sys.stderr)
            continue
        for t in part:
            try:
                sp = (df[t]['Stock Splits'] if len(part) > 1 else df['Stock Splits']).dropna()
                f = 1.0
                for d, v in sp.items():
                    if v and d > pd.Timestamp(since_of[t]):
                        f *= float(v)
                out[t] = f
            except Exception:
                continue
    return out


def returns(state, prices):
    """بازده هر سهم از قیمت روز اولین سیگنال. قیمت‌ها خام‌اند، پس برای سهمی که بازده‌اش غیرعادی است (بالای +۸۰٪ یا
    زیر −۴۰٪) تقسیم سهام را از Yahoo می‌گیریم و قیمت مبنا را تعدیل می‌کنیم. اگر نشد تأیید کرد، «مشکوک» علامت می‌خورد."""
    global since_of
    rows = []
    for t, s in state.items():
        p = prices.get(t)
        if p and s.get('first_price'):
            rows.append({'ticker': t, 'count': s['count'], 'first_date': s['first_date'],
                         'ret': (p / s['first_price'] - 1) * 100, 'split': None, 'suspect': False})
    odd = [r for r in rows if r['ret'] > 80 or r['ret'] < -40]
    if odd:
        since_of = {r['ticker']: r['first_date'] for r in odd}
        fac = split_factors(since_of.keys(), min(since_of.values()))
        for r in odd:
            f = fac.get(r['ticker'])
            if f is None:
                r['suspect'] = True            # تقسیم سهام را نتوانستیم بررسی کنیم
            elif abs(f - 1) > 1e-9:
                base = state[r['ticker']]['first_price'] / f
                r['ret'] = (prices[r['ticker']] / base - 1) * 100
                r['split'] = f
                if r['ret'] > 300 or r['ret'] < -80:
                    r['suspect'] = True        # بعد از تعدیل هم افراطی است
            elif r['ret'] > 300 or r['ret'] < -85:
                r['suspect'] = True            # بدون تقسیم، ولی افراطی (مثلاً اسم نماد عوض شده یا داده‌ی ناقص)
    return rows


def summary_text(title, rows, since, unit_word):
    if not rows:
        return ''
    alld = pd.DataFrame(rows)
    bad = alld[alld.suspect] if 'suspect' in alld else alld.iloc[0:0]
    df = alld[~alld.suspect] if 'suspect' in alld else alld
    if df.empty:
        return ''
    pos = (df.ret > 0).mean() * 100
    lines = [f'<b>📊 پیگیری سیگنال‌ها — {title}</b>',
             f'<i>از {since}؛ بازده از قیمت بسته‌شدن روز اولین سیگنال تا امروز</i>',
             f'تعداد سهم‌های سیگنال‌شده: <b>{fa(len(df))}</b> | میانگین بازده: <b>{fa(f"{df.ret.mean():+.1f}")}٪</b> | '
             f'میانه: {fa(f"{df.ret.median():+.1f}")}٪ | مثبت: {fa(f"{pos:.0f}")}٪']

    def fmt(r):
        return (f"{r.ticker} — {fa(int(r['count']))} {unit_word} — <b>{fa(f'{r.ret:+.1f}')}٪</b> "
                f"(از {r.first_date}){' ⚠️ با تعدیل split' if pd.notna(r.get('split')) else ''}")
    rep = df[df['count'] >= 2].sort_values(['count', 'ret'], ascending=[False, False]).head(10)
    if len(rep):
        lines += ['', '<b>🔁 بیشترین تکرار سیگنال:</b>'] + [fmt(r) for _, r in rep.iterrows()]
    lines += ['', '<b>🟢 بهترین بازده از اولین سیگنال:</b>'] + [fmt(r) for _, r in df.nlargest(7, 'ret').iterrows()]
    lines += ['', '<b>🔴 بدترین بازده از اولین سیگنال:</b>'] + [fmt(r) for _, r in df.nsmallest(5, 'ret').iterrows()]
    if len(bad):
        lines += ['', '<i>⚠️ این سهم‌ها در فهرست‌ها و میانگین نیامدند، چون بازدهشان به‌خاطر split یا داده‌ی ناقص قابل‌اعتماد نیست: '
                  + '، '.join(bad.ticker.head(12)) + '</i>']
    out = '\n'.join(lines)
    print('=== TRACK MESSAGE ===\n' + out + '\n=== END ===')
    return out
