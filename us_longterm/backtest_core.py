"""بک‌تست هسته‌ی سبد بلندمدت آمریکا: خرید و نگه‌داری شاخص در برابر قانون روند (میانگین ۱۰ ماهه / ۲۰۰ روزه).
فقط قیمت تعدیل‌شده‌ی Yahoo (سود نقدی و split حساب است). سیگنال با یک ماه تأخیر اجرا می‌شود (بدون نگاه به آینده).
هزینه‌ی هر جابه‌جایی ۰٫۱٪. نقد = SHY (اوراق کوتاه‌مدت)، قبل از ۲۰۰۲ صفر درصد.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

COST = 0.001


def metrics(r, name):
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(12)
    dd = (eq / eq.cummax() - 1).min()
    sharpe = (r.mean() * 12) / vol if vol else float('nan')
    ann = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
    return {'name': name, 'from': str(r.index[0].date()), 'to': str(r.index[-1].date()), 'cagr': round(cagr * 100, 2),
            'vol': round(vol * 100, 2), 'maxdd': round(dd * 100, 1), 'sharpe': round(sharpe, 2),
            'worst_year': f'{ann.idxmin()}: {ann.min() * 100:.1f}%', 'final_x': round(eq.iloc[-1], 2)}


def run(ticker, start):
    px = pd.concat({t: yf.download(t, start=start, interval='1d', auto_adjust=True, progress=False, threads=False)['Close'].squeeze()
                    for t in (ticker, 'SHY')}, axis=1)
    print(ticker, 'قیمت‌های SHY:', int(px['SHY'].notna().sum()), 'روز؛', ticker, int(px[ticker].notna().sum()), 'روز')
    assert px['SHY'].notna().sum() > 1000, 'داده‌ی SHY نیامد'
    m = px.resample('ME').last()
    m = m.iloc[:-1] if px.index[-1] < m.index[-1] else m      # ماه ناقص حذف شود
    ret = m.pct_change()
    cash = ret['SHY'].fillna(0.0)
    asset = ret[ticker]
    out = []
    out.append(metrics(asset, f'{ticker} خرید و نگه‌داری'))
    for name, win in (('میانگین ۱۰ ماهه', 10),):
        sma = m[ticker].rolling(win).mean()
        sig = (m[ticker] > sma).shift(1)            # سیگنال پایان ماه قبل
        valid = sig.notna()
        s = sig.fillna(False).astype(bool)
        r = np.where(s, asset, cash)
        r = pd.Series(r, index=m.index)
        switches = s.astype(int).diff().abs().fillna(0)
        r = r - switches * COST
        r = r[valid]
        out.append(metrics(r, f'{ticker} قانون روند ({name})'))
        time_in = s[valid].mean() * 100
        out[-1]['time_in_market'] = round(time_in, 0)
    # همان بازه برای خرید و نگه‌داری، تا مقایسه عادلانه باشد
    first = r.index[0]
    out[0] = metrics(asset[asset.index >= first], f'{ticker} خرید و نگه‌داری')
    return out


if __name__ == '__main__':
    res = []
    for t, st in (('SPY', '1993-01-01'), ('QQQ', '1999-03-01')):
        res += run(t, st)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    os.makedirs('data/us_longterm', exist_ok=True)
    json.dump(res, open('data/us_longterm/core_backtest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
