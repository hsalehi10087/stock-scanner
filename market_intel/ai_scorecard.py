"""کارنامه‌ی انتخاب‌های روزانه‌ی سهام هوش مصنوعی — آیا انتخاب‌ها از شاخص‌ها بهتر بوده‌اند؟

از فایل‌های data/ai_stocks/YYYY-MM-DD.json (انتخاب هر روز) دو چیز می‌سازد:
۱. سبد روزانه: هر روز با انتخاب‌های همان روز، وزن برابر، از قیمت بسته‌شدن روز معاملاتی بعد از انتشار تا روز معاملاتی بعدی
   (یعنی فقط با اطلاعاتی که واقعاً در دسترس بود؛ بدون نگاه به آینده). بازده انباشته در برابر QQQ و SMH.
۲. هر سهم: از اولین روز پیوسته‌ای که در فهرست بوده تا امروز (یا تا روز خروج).
هزینه‌ی معامله لحاظ نشده است. خروجی: data/ai_stocks/scorecard.json
"""
import datetime as dt
import glob
import json
import os

import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'data', 'ai_stocks')
BENCH = ['QQQ', 'SMH']


def load_days():
    days = {}
    for f in sorted(glob.glob(os.path.join(DIR, '20??-??-??.json'))):
        d = os.path.basename(f)[:10]
        try:
            v = json.load(open(f, encoding='utf-8'))
            days[d] = [p['ticker'] for p in v.get('picks', []) if p.get('ticker')]
        except Exception:
            pass
    return {d: t for d, t in days.items() if t}


def main():
    days = load_days()
    if not days:
        print('no pick files')
        return
    tickers = sorted({t for ts in days.values() for t in ts} | set(BENCH))
    start = (dt.date.fromisoformat(min(days)) - dt.timedelta(days=7)).isoformat()
    px = yf.download(tickers, start=start, auto_adjust=True, progress=False)['Close']
    if isinstance(px, pd.Series):
        px = px.to_frame(tickers[0])
    px = px.dropna(how='all')
    idx = px.index
    # روز انتشار d (صبح تهران، قبل از باز شدن بازار آمریکا) → ورود با بسته‌شدن روز معاملاتی d، خروج با بسته‌شدن روز معاملاتی بعدی
    port, bench = [], {b: [] for b in BENCH}
    for d, ts in sorted(days.items()):
        pos = idx.searchsorted(pd.Timestamp(d))
        if pos + 1 >= len(idx):
            continue
        a, b = idx[pos], idx[pos + 1]
        rs = [(px.at[b, t] / px.at[a, t] - 1) for t in ts if t in px and pd.notna(px.at[a, t]) and pd.notna(px.at[b, t])]
        if not rs:
            continue
        port.append(sum(rs) / len(rs))
        for k in BENCH:
            bench[k].append(px.at[b, k] / px.at[a, k] - 1)

    def cum(xs):
        c = 1.0
        for x in xs:
            c *= 1 + x
        return round((c - 1) * 100, 1)

    # هر سهم: آخرین دوره‌ی پیوسته‌ی حضور
    dates = sorted(days)
    per = []
    for t in sorted({t for ts in days.values() for t in ts}):
        on = [d for d in dates if t in days[d]]
        first = on[-1]
        for d in reversed(dates[:dates.index(on[-1])]):
            if t in days[d]:
                first = d
            else:
                break
        still = t in days[dates[-1]]
        pa = idx.searchsorted(pd.Timestamp(first))
        end = idx[-1] if still else idx[min(idx.searchsorted(pd.Timestamp(on[-1])) + 1, len(idx) - 1)]
        if pa >= len(idx) or t not in px:
            continue
        a = idx[pa]
        if pd.isna(px.at[a, t]) or pd.isna(px.at[end, t]):
            continue
        r = round((px.at[end, t] / px.at[a, t] - 1) * 100, 1)
        rq = round((px.at[end, 'QQQ'] / px.at[a, 'QQQ'] - 1) * 100, 1)
        per.append({'ticker': t, 'from': first, 'to': str(end.date()), 'in_list_now': still, 'ret_pct': r,
                    'qqq_same_period_pct': rq})
    out = {'date': str(dt.date.today()), 'first_pick_date': dates[0], 'days_measured': len(port),
           'portfolio_pct': cum(port), 'benchmarks_pct': {k: cum(v) for k, v in bench.items()},
           'hit_rate_vs_qqq_pct': round(100 * sum(p > q for p, q in zip(port, bench['QQQ'])) / len(port), 0) if port else None,
           'per_ticker': per,
           'note': 'وزن برابر، ورود با بسته‌شدن روز انتشار، بدون هزینه‌ی معامله'}
    json.dump(out, open(os.path.join(DIR, 'scorecard.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != 'per_ticker'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
