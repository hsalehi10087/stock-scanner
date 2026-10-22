"""الگویاب — هر روز: امتیاز همه‌ی سهم‌ها با مدل هر بازار، ۵ پیشنهاد برتر، ثبت در تاریخچه با قیمت، و سنجش بازده قبلی‌ها.

خروجی: data/pattern_hunter/history.csv (هر پیشنهاد با تاریخ و قیمت)، today.json، track.json
"""
import datetime as dt
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FEATURES, MARKETS, OUT, download, features, log  # noqa: E402

TOP = 5
HIST = os.path.join(OUT, 'history.csv')


def en_name(t):
    import re
    import yfinance as yf
    try:
        i = yf.Ticker(t).get_info()
        n = i.get('shortName') or i.get('longName') or ''
    except Exception:
        n = ''
    return re.sub(r'[぀-ヿ㐀-鿿가-힯]', '', n).strip(' -,')[:40]


def main():
    today = str(dt.date.today())
    hist = pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame(
        columns=['date', 'market', 'ticker', 'name', 'price', 'prob', 'rank', 'index_price'])
    picks, prices_now = {}, {}
    for m, cfg in MARKETS.items():
        mp = os.path.join(OUT, f'model_{m}.joblib')
        if not os.path.exists(mp):
            log('no model', m)
            continue
        clf = joblib.load(mp)
        names = json.load(open(os.path.join(OUT, f'universe_{m}.json'), encoding='utf-8'))
        extra = list(set(hist[hist.market == m].ticker))
        C, V = download(sorted(set(names) | set(extra)) + [cfg['index']], period='2y')
        if C.empty:
            continue
        idx = C.pop(cfg['index']) if cfg['index'] in C else C.median(axis=1)
        last_day = C.index[-1]
        rows = {}
        for t in names:
            if t not in C or pd.isna(C[t].iloc[-1]) or C[t].dropna().index[-1] < last_day - pd.Timedelta(days=5):
                continue
            c = C[t].dropna()
            f = features(c, V[t].reindex(c.index).fillna(0), idx).iloc[-1]
            if f[FEATURES].isna().sum() <= 3:
                rows[t] = f[FEATURES]
        X = pd.DataFrame(rows).T.astype(float)
        X['p'] = clf.predict_proba(X[FEATURES])[:, 1]
        best = X.nlargest(TOP, 'p')
        lst = []
        for rank, (t, r) in enumerate(best.iterrows(), 1):
            nm = names.get(t, '')
            if m in ('cn', 'jp', 'tw') or not nm:
                nm = en_name(t) or nm
            lst.append({'ticker': t, 'name': nm, 'price': round(float(C[t].dropna().iloc[-1]), 3), 'prob': round(float(r.p), 3),
                        'rank': rank, 'r6m': round(float(r.r6m) * 100, 1), 'from_hi': round(float(r.from_hi) * 100, 1),
                        'volu_ratio': round(float(r.volu_ratio), 2)})
            hist.loc[len(hist)] = [today, m, t, nm, round(float(C[t].dropna().iloc[-1]), 4), round(float(r.p), 4), rank,
                                   round(float(idx.dropna().iloc[-1]), 4)]
        picks[m] = {'data_date': str(last_day.date()), 'scored': int(len(X)), 'picks': lst,
                    'median_prob': round(float(X.p.median()), 3)}
        prices_now[m] = ({t: float(C[t].dropna().iloc[-1]) for t in C.columns if C[t].notna().any()},
                         float(idx.dropna().iloc[-1]))
    hist = hist.drop_duplicates(subset=['date', 'market', 'ticker'], keep='last')
    hist.to_csv(HIST, index=False)
    # سنجش: بازده هر پیشنهاد از روز اولین پیشنهاد تا امروز، در برابر شاخص همان بازار
    track = {}
    first = hist.sort_values('date').drop_duplicates(subset=['market', 'ticker'], keep='first')
    for m, (px, ix) in prices_now.items():
        f = first[first.market == m]
        res = []
        for _, r in f.iterrows():
            if r.ticker in px and r.price > 0:
                res.append({'ticker': r.ticker, 'since': r.date, 'days': (dt.date.today() - dt.date.fromisoformat(r.date)).days,
                            'ret_pct': round((px[r.ticker] / r.price - 1) * 100, 1),
                            'index_ret_pct': round((ix / r.index_price - 1) * 100, 1) if r.index_price > 0 else None})
        old = [x for x in res if x['days'] >= 7]
        track[m] = {'picks_total': len(res), 'evaluated': len(old),
                    'avg_ret_pct': round(float(np.mean([x['ret_pct'] for x in old])), 1) if old else None,
                    'avg_index_pct': round(float(np.mean([x['index_ret_pct'] for x in old if x['index_ret_pct'] is not None])), 1) if old else None,
                    'beat_index_pct': round(float(np.mean([x['ret_pct'] > (x['index_ret_pct'] or 0) for x in old])) * 100, 0) if old else None,
                    'best': max(old, key=lambda x: x['ret_pct']) if old else None,
                    'items': sorted(res, key=lambda x: x['since'])}
    json.dump({'date': today, 'markets': picks}, open(os.path.join(OUT, 'today.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump({'date': today, 'markets': track}, open(os.path.join(OUT, 'track.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(json.dumps({m: [p['ticker'] for p in v['picks']] for m, v in picks.items()}))


if __name__ == '__main__':
    main()
