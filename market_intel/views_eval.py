"""آیا «نظر تحلیلگران» روزانه چیزی درباره‌ی حرکت بعدی قیمت می‌گوید؟

همه‌ی فایل‌های data/analyst_views/YYYY-MM-DD.json را می‌خواند و stance هر دارایی را با بازده ۱ و ۵ روز
معاملاتی بعد از تاریخ گزارش مقایسه می‌کند. برای rates تغییر بازده اوراق ۱۰ ساله (^TNX) ملاک است
(صعودی = احتمال افزایش نرخ ← انتظار بالا رفتن بازده).
خروجی: جدول در خروجی و data/analyst_views/eval.csv. فقط ابزار تحقیق است؛ بعد از چند هفته داده معنی پیدا می‌کند
و اگر پیش‌بینی‌کننده بود، می‌شود stance را به‌عنوان یکی از ویژگی‌های سیستم تشخیص رژیم بازار استفاده کرد.

استفاده: pip install yfinance pandas && python3 market_intel/views_eval.py
"""
import datetime as dt
import glob
import json
import os

import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'data', 'analyst_views')
TICKERS = {'gold': 'GC=F', 'silver': 'SI=F', 'bitcoin': 'BTC-USD', 'copper': 'HG=F', 'oil': 'BZ=F', 'rates': '^TNX'}
SIGN = {'صعودی': 1, 'نزولی': -1}


def load_views():
    rows = []
    for f in sorted(glob.glob(os.path.join(DIR, '20??-??-??.json'))):
        try:
            v = json.load(open(f, encoding='utf-8'))
        except ValueError:
            continue
        for a, x in (v.get('assets') or {}).items():
            if a in TICKERS:
                rows.append({'date': os.path.basename(f)[:10], 'asset': a, 'stance': x.get('stance'),
                             'confidence': x.get('confidence', ''), **{f'n_{k}': c for k, c in (x.get('counts') or {}).items()}})
    return pd.DataFrame(rows)


def forward_returns(df):
    start = (dt.date.fromisoformat(df['date'].min()) - dt.timedelta(days=7)).isoformat()
    px = yf.download(list(TICKERS.values()), start=start, progress=False, auto_adjust=True)['Close']
    out = []
    for _, r in df.iterrows():
        s = px[TICKERS[r['asset']]].dropna()
        d = pd.Timestamp(r['date'])
        before = s[s.index < d]                     # آخرین قیمت قبل از گزارش ۰۵:۰۰ تهران
        after = s[s.index >= d]
        if before.empty or after.empty:
            out.append((None, None))
            continue
        p0 = before.iloc[-1]
        diff = (lambda p: p - p0) if r['asset'] == 'rates' else (lambda p: p / p0 - 1)
        out.append((diff(after.iloc[0]), diff(after.iloc[4]) if len(after) > 4 else None))
    df['fwd1'], df['fwd5'] = zip(*out)
    return df


def main():
    df = load_views()
    if df.empty:
        print('هنوز فایل تاریخ‌داری نیست')
        return
    df = forward_returns(df)
    df['sign'] = df['stance'].map(SIGN)
    for h in ('fwd1', 'fwd5'):
        df[f'hit_{h}'] = (df['sign'] * df[h]).gt(0).where(df['sign'].notna() & df[h].notna())
    df.to_csv(os.path.join(DIR, 'eval.csv'), index=False)
    print(f'{len(df)} ردیف از {df["date"].nunique()} روز')
    g = df[df['sign'].notna()].groupby('asset')
    print(pd.DataFrame({'n': g.size(), 'hit_1d': g['hit_fwd1'].mean().round(2), 'hit_5d': g['hit_fwd5'].mean().round(2),
                        'avg_signed_1d': g.apply(lambda x: (x['sign'] * x['fwd1']).mean()).round(4)}))
    if 'confidence' in df and df['confidence'].astype(bool).any():
        print(df[df['sign'].notna()].groupby('confidence')['hit_fwd1'].agg(['size', 'mean']).round(2))


if __name__ == '__main__':
    main()
