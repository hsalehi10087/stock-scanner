"""بررسی داده‌ی صورت مالی Yahoo برای سهام ژاپن."""
import json
import os

import yfinance as yf

T = ['6857.T', '7203.T', '6758.T', '7318.T', '3997.T', '6356.T', '5802.T', '8035.T', '9984.T', '4063.T']
out = {}
for t in T:
    tk = yf.Ticker(t)
    d = {}
    for nm in ('quarterly_income_stmt', 'income_stmt', 'quarterly_cashflow'):
        try:
            df = getattr(tk, nm)
            d[nm] = {'cols': [str(c.date()) for c in df.columns], 'has_rev': [r for r in df.index if 'Revenue' in r][:4],
                     'rev': {str(c.date()): (None if v != v else float(v)) for c, v in
                             (df.loc['Total Revenue'].items() if 'Total Revenue' in df.index else [])}}
        except Exception as e:
            d[nm] = repr(e)[:100]
    try:
        i = tk.get_info()
        d['info'] = {k: i.get(k) for k in ('revenueGrowth', 'earningsQuarterlyGrowth', 'totalRevenue', 'mostRecentQuarter')}
    except Exception as e:
        d['info'] = repr(e)[:100]
    out[t] = d
os.makedirs('data/strategy_lab', exist_ok=True)
json.dump(out, open('data/strategy_lab/jp_probe.json', 'w'), indent=1, default=str)
