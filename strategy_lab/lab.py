"""آزمایشگاه استراتژی: تحلیل نمودار + بک‌تست واقعی با دوره‌ی آزمون جدا.

استفاده: python strategy_lab/lab.py GC=F XAUUSD
- داده‌ی روزانه‌ی واقعی از Yahoo
- سیگنال در بسته‌شدن روز t، اجرا از روز t+1 (بدون نگاه به آینده)
- کارمزد + لغزش: COST به‌ازای هر بار تغییر موقعیت
- بهینه‌سازی پارامتر فقط روی دوره‌ی آموزش (IS)، گزارش جدا روی دوره‌ی آزمون (OOS)
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

SYM = sys.argv[1] if len(sys.argv) > 1 else 'GC=F'
NAME = sys.argv[2] if len(sys.argv) > 2 else SYM
OUT = os.path.join('data', 'strategy_lab', NAME)
IS_END = '2021-12-31'
START = '2010-01-01'
COST = 0.0003  # ۰.۰۳٪ هر بار ورود یا خروج


def load():
    df = yf.download(SYM, start='2008-01-01', interval='1d', progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def atr(df, n=14):
    tr = pd.concat([df.High - df.Low, (df.High - df.Close.shift()).abs(), (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df, n=14):
    up, dn = df.High.diff(), -df.Low.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(pdm, df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    ndi = 100 * pd.Series(ndm, df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


# ---------- استراتژی‌ها: هر کدام سری موقعیت 0/1 برمی‌گرداند ----------
def donchian(df, n, m):
    hi, lo = df.High.rolling(n).max().shift(), df.Low.rolling(m).min().shift()
    pos, cur = [], 0
    for c, h, l in zip(df.Close, hi, lo):
        if cur == 0 and c > h:
            cur = 1
        elif cur == 1 and c < l:
            cur = 0
        pos.append(cur)
    return pd.Series(pos, df.index)


def pullback(df, th, hold):
    r2 = rsi(df.Close, 2)
    ma200 = df.Close.rolling(200).mean()
    ma5 = df.Close.rolling(5).mean()
    pos, cur, days = [], 0, 0
    for c, r, m200, m5 in zip(df.Close, r2, ma200, ma5):
        if cur == 0 and c > m200 and r < th:
            cur, days = 1, 0
        elif cur == 1:
            days += 1
            if c > m5 or days >= hold:
                cur = 0
        pos.append(cur)
    return pd.Series(pos, df.index)


def ma_cross(df, f, s):
    return (df.Close.rolling(f).mean() > df.Close.rolling(s).mean()).astype(int)


def regime_switch(df, n, m, th):
    """روند قوی (ADX>25 و بالای MA200) → شکست دانچیان؛ بازار رنج (ADX<20) → خرید در اصلاح؛ بقیه → بیرون."""
    a = adx(df)
    up = df.Close > df.Close.rolling(200).mean()
    d = donchian(df, n, m)
    p = pullback(df, th, 10)
    trend = (a > 25) & up
    rng = (a < 20) & up
    return ((d.astype(bool) & trend) | (p.astype(bool) & rng)).astype(int)


GRID = {
    'شکست کانال دانچیان (دنبال‌کننده‌ی روند)': (donchian, [(20, 10), (20, 20), (55, 20), (55, 10), (40, 15)]),
    'خرید در اصلاح در روند صعودی (RSI2)': (pullback, [(5, 10), (10, 10), (15, 10), (10, 5)]),
    'تقاطع میانگین متحرک': (ma_cross, [(20, 100), (50, 200), (20, 50)]),
    'سوئیچ رژیم بازار': (regime_switch, [(20, 10, 10), (55, 20, 10), (20, 20, 15)]),
}


def metrics(pos, r):
    pos = pos.reindex(r.index).fillna(0)
    strat = pos.shift(1).fillna(0) * r - COST * pos.diff().abs().fillna(0)
    eq = (1 + strat).cumprod()
    yrs = len(strat) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    sharpe = strat.mean() / strat.std() * np.sqrt(252) if strat.std() > 0 else np.nan
    dd = (eq / eq.cummax() - 1).min()
    entries = int((pos.diff() == 1).sum())
    # نرخ برد معاملات
    wins, trades, inpos, acc = 0, 0, False, 0.0
    for p, s in zip(pos.shift(1).fillna(0), strat):
        if p == 1:
            acc = (1 + acc) * (1 + s) - 1 if inpos else s
            inpos = True
        elif inpos:
            trades += 1
            wins += acc > 0
            inpos, acc = False, 0.0
    return {'cagr': round(cagr * 100, 2), 'sharpe': round(sharpe, 2), 'max_dd': round(dd * 100, 2),
            'trades': entries, 'win_rate': round(100 * wins / trades, 1) if trades else None,
            'exposure': round(100 * pos.mean(), 1), 'equity': eq}


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    c = df.Close
    r = c.pct_change().fillna(0)
    last = df.iloc[-1]
    a14 = atr(df)
    snap = {
        'symbol': NAME, 'source': SYM, 'last_date': str(df.index[-1].date()), 'close': round(float(last.Close), 2),
        'ma50': round(float(c.rolling(50).mean().iloc[-1]), 2), 'ma200': round(float(c.rolling(200).mean().iloc[-1]), 2),
        'ma200_slope_20d_pct': round(float((c.rolling(200).mean().iloc[-1] / c.rolling(200).mean().iloc[-21] - 1) * 100), 2),
        'rsi14': round(float(rsi(c, 14).iloc[-1]), 1), 'adx14': round(float(adx(df).iloc[-1]), 1),
        'atr14': round(float(a14.iloc[-1]), 2), 'atr_pct': round(float(a14.iloc[-1] / last.Close * 100), 2),
        'atr_vs_30d_avg': round(float(a14.iloc[-1] / a14.iloc[-31:-1].mean()), 2),
        'high_52w': round(float(df.High.tail(252).max()), 2), 'low_52w': round(float(df.Low.tail(252).min()), 2),
        'donchian20_high': round(float(df.High.tail(20).max()), 2), 'donchian20_low': round(float(df.Low.tail(20).min()), 2),
        'donchian55_high': round(float(df.High.tail(55).max()), 2), 'donchian55_low': round(float(df.Low.tail(55).min()), 2),
        'ret_1m': round(float((c.iloc[-1] / c.iloc[-22] - 1) * 100), 2), 'ret_3m': round(float((c.iloc[-1] / c.iloc[-64] - 1) * 100), 2),
        'ret_12m': round(float((c.iloc[-1] / c.iloc[-253] - 1) * 100), 2),
    }
    d = df[df.index >= START]
    ris, roos = r[(r.index >= START) & (r.index <= IS_END)], r[r.index > IS_END]
    results, curves = [], {}
    bh_pos = pd.Series(1, d.index)
    for label, pos_full, params in [('خرید و نگهداری', bh_pos, None)]:
        results.append({'strategy': label, 'params': None, 'is': {k: v for k, v in metrics(pos_full, ris).items() if k != 'equity'},
                        'oos': {k: v for k, v in metrics(pos_full, roos).items() if k != 'equity'}})
        curves[label] = metrics(pos_full, roos)['equity']
    for label, (fn, grid) in GRID.items():
        best, best_s, best_pos = None, -9, None
        tried = []
        for p in grid:
            pos = fn(df, *p)
            m = metrics(pos, ris)
            tried.append({'params': p, 'is_sharpe': m['sharpe'], 'is_cagr': m['cagr']})
            if m['sharpe'] > best_s:
                best, best_s, best_pos = p, m['sharpe'], pos
        mi, mo = metrics(best_pos, ris), metrics(best_pos, roos)
        results.append({'strategy': label, 'params': list(best), 'tried_on_is': tried,
                        'is': {k: v for k, v in mi.items() if k != 'equity'},
                        'oos': {k: v for k, v in mo.items() if k != 'equity'},
                        'signal_now': int(best_pos.iloc[-1])})
        curves[label] = mo['equity']
    out = {'snapshot': snap, 'periods': {'is': f'{START} → {IS_END}', 'oos': f'2022-01-01 → {snap["last_date"]}'},
           'cost_per_side_pct': COST * 100, 'results': results}
    with open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    pd.DataFrame(curves).to_csv(os.path.join(OUT, 'oos_equity.csv'), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])


if __name__ == '__main__':
    main()
