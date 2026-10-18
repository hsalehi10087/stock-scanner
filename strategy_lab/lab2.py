"""مرحله‌ی ۲ آزمایشگاه: دانچیان + حد ضرر ATR + اندازه‌ی موقعیت بر اساس ریسک،
آزمون پایداری پارامترها، Walk-forward سالانه (بهینه‌سازی کنترل‌شده)، و آزمون روی داده‌ی ساعتی.
استفاده: python strategy_lab/lab2.py GC=F XAUUSD
"""
import itertools
import json
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import atr  # noqa: E402

SYM = sys.argv[1] if len(sys.argv) > 1 else 'GC=F'
NAME = sys.argv[2] if len(sys.argv) > 2 else SYM
OUT = os.path.join('data', 'strategy_lab', NAME)
COST = 0.0003
TARGET_VOL = 0.12  # هدف نوسان سالانه برای اندازه‌ی موقعیت (بدون اهرم، حداکثر ۱۰۰٪)


def flat(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[['Open', 'High', 'Low', 'Close']].dropna()


def donch_atr(df, n, m, k):
    hi, lo = df.High.rolling(n).max().shift(), df.Low.rolling(m).min().shift()
    a = atr(df)
    pos, cur, peak = [], 0, 0.0
    for c, h, l, av in zip(df.Close, hi, lo, a):
        if cur == 0 and c > h:
            cur, peak = 1, c
        elif cur == 1:
            peak = max(peak, c)
            stop = peak - k * av if k else -np.inf
            if c < l or c < stop:
                cur = 0
        pos.append(cur)
    return pd.Series(pos, df.index, dtype=float)


def sized(pos, r, ann):
    vol = r.rolling(20).std() * np.sqrt(ann)
    return pos * (TARGET_VOL / vol).clip(upper=1.0).fillna(0)


def metrics(pos, r, ann):
    pos = pos.reindex(r.index).fillna(0)
    strat = pos.shift(1).fillna(0) * r - COST * pos.diff().abs().fillna(0)
    if len(strat) < 2 or strat.std() == 0:
        return {'cagr': 0.0, 'sharpe': 0.0, 'max_dd': 0.0, 'trades': 0, 'exposure': 0.0}
    eq = (1 + strat).cumprod()
    yrs = len(strat) / ann
    return {'cagr': round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2),
            'sharpe': round(strat.mean() / strat.std() * np.sqrt(ann), 2),
            'max_dd': round((eq / eq.cummax() - 1).min() * 100, 2),
            'trades': int(((pos > 0) & (pos.shift(1).fillna(0) == 0)).sum()),
            'exposure': round(100 * (pos > 0).mean(), 1)}


def grid_positions(df, r, ann, grid):
    out = {}
    for n, m, k, s in grid:
        p = donch_atr(df, n, m, k)
        out[(n, m, k, s)] = sized(p, r, ann) if s else p
    return out


def daily_part():
    df = flat(yf.download(SYM, start='2008-01-01', interval='1d', progress=False, auto_adjust=False))
    r = df.Close.pct_change().fillna(0)
    ann = 252
    grid = list(itertools.product([20, 30, 40, 55], [10, 15, 20], [0, 2, 3], [False, True]))
    P = grid_positions(df, r, ann, grid)
    ris, roos = r['2010-01-01':'2021-12-31'], r['2022-01-01':]
    rows = []
    for key, p in P.items():
        rows.append({'n': key[0], 'm': key[1], 'atr_k': key[2], 'vol_sized': key[3],
                     'is': metrics(p, ris, ann), 'oos': metrics(p, roos, ann)})
    best = max(rows, key=lambda x: x['is']['sharpe'])
    oos_sh = [x['oos']['sharpe'] for x in rows]
    stability = {'combos': len(rows), 'median_oos_sharpe': round(float(np.median(oos_sh)), 2),
                 'share_oos_sharpe_gt_0_5': round(100 * float(np.mean(np.array(oos_sh) > 0.5)), 1),
                 'share_oos_cagr_positive': round(100 * float(np.mean([x['oos']['cagr'] > 0 for x in rows])), 1)}
    sizing_cmp = {
        'fixed_median_oos_dd': round(float(np.median([x['oos']['max_dd'] for x in rows if not x['vol_sized']])), 2),
        'sized_median_oos_dd': round(float(np.median([x['oos']['max_dd'] for x in rows if x['vol_sized']])), 2),
        'fixed_median_oos_sharpe': round(float(np.median([x['oos']['sharpe'] for x in rows if not x['vol_sized']])), 2),
        'sized_median_oos_sharpe': round(float(np.median([x['oos']['sharpe'] for x in rows if x['vol_sized']])), 2)}
    # Walk-forward: هر سال پارامتر بر اساس ۶ سال قبل انتخاب و روی همان سال اجرا می‌شود
    wf_pos, picks = pd.Series(0.0, r.index), []
    for y in range(2016, int(r.index[-1].year) + 1):
        train = r[f'{y - 6}-01-01':f'{y - 1}-12-31']
        key = max(P, key=lambda k: metrics(P[k], train, ann)['sharpe'])
        sl = slice(f'{y}-01-01', f'{y}-12-31')
        wf_pos[sl] = P[key][sl]
        picks.append({'year': y, 'n': key[0], 'm': key[1], 'atr_k': key[2], 'vol_sized': key[3],
                      'year_metrics': metrics(P[key], r[sl], ann)})
    rwf = r['2016-01-01':]
    wf = {'strategy': metrics(wf_pos, rwf, ann), 'buy_hold': metrics(pd.Series(1.0, r.index), rwf, ann), 'picks': picks}
    bh = {'is': metrics(pd.Series(1.0, r.index), ris, ann), 'oos': metrics(pd.Series(1.0, r.index), roos, ann)}
    best_key = (best['n'], best['m'], best['atr_k'], best['vol_sized'])
    a = atr(df)
    now = {'signal': round(float(P[best_key].iloc[-1]), 2),
           'entry_level_close_above': round(float(df.High.tail(best['n']).max()), 2),
           'exit_level_close_below': round(float(df.Low.tail(best['m']).min()), 2),
           'atr14': round(float(a.iloc[-1]), 2)}
    return {'best_on_is': best, 'buy_hold': bh, 'stability': stability, 'sizing': sizing_cmp,
            'walk_forward': wf, 'now': now, 'last_date': str(df.index[-1].date())}


def hourly_part():
    df = flat(yf.download(SYM, period='730d', interval='1h', progress=False, auto_adjust=False))
    if len(df) < 1000:
        return {'error': f'hourly bars: {len(df)}'}
    r = df.Close.pct_change().fillna(0)
    days = (df.index[-1] - df.index[0]).days
    ann = len(df) / (days / 365.25)
    cut = df.index[int(len(df) * 0.6)]
    ris, roos = r[:cut], r[cut:]
    grid = list(itertools.product([20, 40, 80, 120], [10, 20, 40], [0, 2, 3], [False, True]))
    P = grid_positions(df, r, ann, grid)
    rows = [{'n': k[0], 'm': k[1], 'atr_k': k[2], 'vol_sized': k[3],
             'is': metrics(p, ris, ann), 'oos': metrics(p, roos, ann)} for k, p in P.items()]
    best = max(rows, key=lambda x: x['is']['sharpe'])
    oos_sh = [x['oos']['sharpe'] for x in rows]
    return {'bars': len(df), 'from': str(df.index[0]), 'to': str(df.index[-1]), 'split_at': str(cut),
            'best_on_is': best,
            'buy_hold': {'is': metrics(pd.Series(1.0, r.index), ris, ann), 'oos': metrics(pd.Series(1.0, r.index), roos, ann)},
            'stability': {'combos': len(rows), 'median_oos_sharpe': round(float(np.median(oos_sh)), 2),
                          'share_oos_sharpe_gt_0_5': round(100 * float(np.mean(np.array(oos_sh) > 0.5)), 1)}}


def main():
    os.makedirs(OUT, exist_ok=True)
    out = {'daily': daily_part(), 'hourly': hourly_part(), 'cost_per_side_pct': COST * 100, 'target_vol': TARGET_VOL}
    with open(os.path.join(OUT, 'results_stage2.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print('done')


if __name__ == '__main__':
    main()
