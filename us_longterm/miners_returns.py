"""بازده بلندمدت معدن‌کاران طلا در برابر طلا و S&P 500 (داده‌ی Yahoo، بازده کل با سود تقسیمی).
خروجی: data/us_longterm/miners_returns.json — فقط گزارش، بدون تلگرام."""
import json, os, datetime as dt
import pandas as pd, yfinance as yf

T = ['GDX', 'GDXJ', 'GLD', 'SPY', 'NEM', 'B', 'GOLD', 'AEM', 'KGC', 'AU', 'GFI', 'AGI', 'FNV', 'WPM', 'RGLD']
out = {'asof': None, 'rows': {}, 'notes': []}
for t in T:
    try:
        d = yf.download(t, start='1995-01-01', auto_adjust=False, progress=False, threads=False, actions=True)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d.dropna(subset=['Close'])
        if len(d) < 300:
            out['notes'].append(f'{t}: no data'); continue
        adj, px = d['Adj Close'], d['Close']
        last = adj.index[-1]
        r = {'first': str(adj.index[0].date()), 'last': str(last.date()), 'last_close': round(float(px.iloc[-1]), 2),
             'splits': {str(k.date()): float(v) for k, v in d['Stock Splits'][d['Stock Splits'] != 0].items()} if 'Stock Splits' in d else {}}
        for y in (5, 10, 20):
            s0 = last - pd.DateOffset(years=y)
            a = adj[adj.index >= s0]
            if adj.index[0] > s0 + pd.Timedelta(days=10):
                r[f'{y}y'] = None; continue
            tot = float(a.iloc[-1] / a.iloc[0] - 1)
            p = px[px.index >= s0]
            w = a / a.cummax() - 1
            r[f'{y}y'] = {'from': str(a.index[0].date()), 'total_ret_pct': round(tot * 100, 1),
                          'cagr_pct': round(((1 + tot) ** (1 / y) - 1) * 100, 1),
                          'price_ret_pct': round(float(p.iloc[-1] / p.iloc[0] - 1) * 100, 1),
                          'maxdd_pct': round(float(w.min()) * 100, 1)}
        dd = adj / adj.cummax() - 1
        r['maxdd_all_pct'] = round(float(dd.min()) * 100, 1)
        r['maxdd_all_trough'] = str(dd.idxmin().date())
        try:
            i = yf.Ticker(t).info
            r['info'] = {k: i.get(k) for k in ('longName', 'profitMargins', 'operatingMargins', 'debtToEquity', 'totalDebt',
                                              'totalCash', 'dividendYield', 'trailingPE', 'marketCap')}
        except Exception as e:
            r['info'] = {'error': str(e)[:80]}
        out['rows'][t] = r
        out['asof'] = str(last.date())
    except Exception as e:
        out['notes'].append(f'{t}: {type(e).__name__} {str(e)[:100]}')
os.makedirs('data/us_longterm', exist_ok=True)
json.dump(out, open('data/us_longterm/miners_returns.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
