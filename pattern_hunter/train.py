"""الگویاب — یادگیری الگوی سهم‌هایی که در ۱۰ سال گذشته در ۱۲ ماه دو برابر شده‌اند (ماهی یک بار، برای هر بازار).

python3 pattern_hunter/train.py <us|cn|in|jp|tw>
خروجی در data/pattern_hunter/: universe_<m>.json، model_<m>.joblib، profile_<m>.json (الگو + سنجش خارج از نمونه)
"""
import datetime as dt
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FEATURES, MARKETS, OUT, download, features, log, universe  # noqa: E402

H = 252          # افق: ۱۲ ماه
STEP = 5         # نمونه‌گیری هفتگی


def main(m):
    os.makedirs(OUT, exist_ok=True)
    cfg = MARKETS[m]
    names = universe(m)
    log(m, 'universe raw', len(names))
    start = str(dt.date.today() - dt.timedelta(days=int(365.25 * 11)))
    C, V = download(list(names) + [cfg['index']], start=start)
    idx = C.pop(cfg['index']) if cfg['index'] in C else C.median(axis=1)
    V = V.drop(columns=[cfg['index']], errors='ignore')
    # نقدشوندگی: میانه‌ی ارزش معاملات روزانه در یک سال اخیر
    dv = (C.tail(252) * V.tail(252)).median()
    keep = dv[dv > 0].sort_values(ascending=False).index[:cfg['cap']]
    C, V = C[keep], V[keep]
    json.dump({t: names.get(t, '') for t in keep}, open(os.path.join(OUT, f'universe_{m}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    # سهم‌هایی که در ۱۰ سال بیش از ۲ برابر شده‌اند (توصیفی)
    ten = C.index[C.index >= C.index[-1] - pd.Timedelta(days=3652)]
    first = C.loc[ten[0]:].bfill().iloc[0]
    decade = (C.iloc[-1] / first).dropna()
    rows = []
    for t in C.columns:
        c, v = C[t].dropna(), V[t].reindex(C[t].dropna().index).fillna(0)
        if len(c) < 2 * H + 10:
            continue
        f = features(c, v, idx)
        f['fwd'] = c.shift(-H) / c - 1
        f['ticker'] = t
        f = f.iloc[H:-H:STEP].dropna(subset=['fwd'])
        rows.append(f)
    D = pd.concat(rows)
    D['y'] = (D['fwd'] >= 1.0).astype(int)
    D = D.dropna(subset=FEATURES, thresh=len(FEATURES) - 3)
    split = D.index.max() - pd.Timedelta(days=3 * 365)
    tr, te = D[D.index < split], D[D.index >= split]
    log(m, 'rows', len(D), 'train', len(tr), 'test', len(te), 'base', D.y.mean())
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
                                         l2_regularization=1.0, class_weight='balanced', random_state=0)
    clf.fit(tr[FEATURES], tr.y)
    p = clf.predict_proba(te[FEATURES])[:, 1]
    te = te.assign(p=p)
    # سنجش خارج از نمونه: هر هفته ۱۰ سهم با بیشترین امتیاز
    top = te.groupby(level=0, group_keys=False).apply(lambda g: g.nlargest(10, 'p'))
    oos = {'period': f'{te.index.min().date()} → {te.index.max().date()}', 'base_rate_pct': round(te.y.mean() * 100, 2),
           'top10_hit_rate_pct': round(top.y.mean() * 100, 2),
           'lift': round(top.y.mean() / max(te.y.mean(), 1e-9), 2),
           'top10_avg_fwd_12m_pct': round(top.fwd.mean() * 100, 1), 'all_avg_fwd_12m_pct': round(te.fwd.mean() * 100, 1),
           'top10_median_fwd_12m_pct': round(top.fwd.median() * 100, 1), 'all_median_fwd_12m_pct': round(te.fwd.median() * 100, 1)}
    smp = te.sample(min(20000, len(te)), random_state=0)
    imp = permutation_importance(clf, smp[FEATURES], smp.y, scoring='average_precision', n_repeats=3, random_state=0)
    importance = sorted(zip(FEATURES, imp.importances_mean), key=lambda x: -x[1])
    win, rest = D[D.y == 1][FEATURES].median(), D[D.y == 0][FEATURES].median()
    profile = {f: {'winners_median': round(float(win[f]), 4), 'others_median': round(float(rest[f]), 4)} for f in FEATURES}
    # مدل نهایی روی همه‌ی داده‌ی برچسب‌دار
    clf.fit(D[FEATURES], D.y)
    joblib.dump(clf, os.path.join(OUT, f'model_{m}.joblib'), compress=3)
    out = {'market': m, 'trained': str(dt.date.today()), 'stocks': int(C.shape[1]),
           'decade_doublers': int((decade >= 2).sum()), 'decade_measured': int(decade.notna().sum()),
           'decade_doublers_pct': round(float((decade >= 2).mean()) * 100, 1),
           'top_decade_gainers': {t: round(float(x), 1) for t, x in decade.sort_values(ascending=False).head(15).items()},
           'samples': int(len(D)), 'winner_events': int(D.y.sum()), 'out_of_sample': oos,
           'importance': [(f, round(float(v), 4)) for f, v in importance], 'profile': profile}
    json.dump(out, open(os.path.join(OUT, f'profile_{m}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('market', 'stocks', 'decade_doublers_pct', 'winner_events', 'out_of_sample')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
