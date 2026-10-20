"""مرحله‌ی ۲: هسته + ماهواره.

هسته = شاخص با فیلتر روند: QQQ (یا SPY) وقتی بالای SMA200 است، وگرنه IEF (اوراق میان‌مدت).
ماهواره = خرید پولبک در روند صعودی (MR) که پول بیکارش در هسته می‌ماند:
   وزن هسته = ۱ − مجموع وزن موقعیت‌های MR.
بررسی پایداری: فیلتر ۱۵۰/۲۰۰/۲۵۰ روزه و باند ۰/۲٪ برای کم کردن رفت‌وبرگشت.
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import equity_lab as L  # noqa: E402

OUT = os.path.join('data', 'strategy_lab', 'equity')


def core_weights(c, idx_sym, safe='IEF', n=200, band=0.0):
    px, sma = c[idx_sym], c[idx_sym].rolling(n).mean()
    state, out = 0, []
    for p, s in zip(px, sma):
        if pd.notna(s):
            if state == 0 and p > s * (1 + band):
                state = 1
            elif state == 1 and p < s * (1 - band):
                state = 0
        out.append(state)
    on = pd.Series(out, index=c.index)
    W = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    W[idx_sym] = on.astype(float)
    W[safe] = 1 - on.astype(float)
    return W


def summary(r, W=None):
    d = {'full': L.stats(r), 'in_sample': L.stats(r[:L.SPLIT]), 'out_sample': L.stats(r[L.SPLIT:]),
         'last_12m': L.stats(r[r.index >= r.index[-1] - pd.Timedelta(days=365)])}
    for y0, y1, nm in (('2008-01-01', '2009-03-31', 'gfc_2008'), ('2020-02-15', '2020-04-30', 'covid_2020'),
                       ('2022-01-01', '2022-12-31', 'bear_2022')):
        d[nm] = L.stats(r[y0:y1])
    if W is not None:
        d['switches_per_year'] = round(float((W.diff().abs().sum(axis=1) > 0.5).sum() / (len(W) / 252)), 1)
    return d


def main():
    res = {}
    for uni, tick, cost, slots, mr in (('stocks', L.STK, 0.0010, 10, (5, 5)), ('etf', L.ETF, 0.0005, 5, (10, 10))):
        allt = sorted(set(tick + ['SPY', 'QQQ', 'IEF']))
        o, c = L.load(allt)
        c = c[c.index >= '2006-06-01']
        o = o.reindex(c.index)
        spy_ok = (c['SPY'] > c['SPY'].rolling(200).mean()).fillna(False)
        first = c.index[c.index >= '2007-01-01'][0]
        Wmr, tr = L.mr_weights(o[tick], c[tick], spy_ok, th=mr[0], exit_n=mr[1], slots=slots)
        Wmr = Wmr.reindex(columns=c.columns, fill_value=0.0)
        part = {}
        for idx in ('QQQ', 'SPY'):
            for n, band in ((150, 0.0), (200, 0.0), (250, 0.0), (200, 0.02)):
                Wc = core_weights(c, idx, n=n, band=band)
                rc, _ = L.run_weights(Wc.loc[first:], o.loc[first:], 0.0005), None
                key = f'core_{idx}_sma{n}_band{int(band * 100)}'
                part[key] = summary(rc, Wc.loc[first:])
                if n == 200 and band == 0.02:
                    Wcs = Wmr + Wc.mul(1 - Wmr.sum(axis=1), axis=0)
                    rcs = L.run_weights(Wcs.loc[first:], o.loc[first:], cost)
                    part[f'core_sat_{idx}'] = summary(rcs)
        for b in ('SPY', 'QQQ'):
            ob = o[b].loc[first:]
            part[f'buyhold_{b}'] = summary((ob.shift(-1) / ob - 1).shift(1).dropna())
        part['mr_params'] = f'rsi<{mr[0]}/exit_sma{mr[1]}/slots{slots}'
        res[uni] = part
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'results2.json'), 'w'), indent=1, default=str)
    for u, p in res.items():
        for k, v in p.items():
            if isinstance(v, dict):
                print(u, k, v['full'], 'OOS', v['out_sample']['sharpe'], v['out_sample']['max_dd'])


if __name__ == '__main__':
    main()
