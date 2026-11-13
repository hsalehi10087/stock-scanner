"""بازده بلندمدت بیت‌کوین و اتریوم در برابر طلا، S&P 500 و نزدک (Yahoo). فقط گزارش.
خروجی: data/us_longterm/crypto_returns.json"""
import json, os
import numpy as np, pandas as pd, yfinance as yf

T = ['BTC-USD', 'ETH-USD', 'GLD', 'SPY', 'QQQ', 'IEF']
px = {}
for t in T:
    d = yf.download(t, start='2010-01-01', auto_adjust=True, progress=False, threads=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    px[t] = d['Close'].dropna()
    assert len(px[t]) > 500, t
out = {'asof': str(px['SPY'].index[-1].date()), 'assets': {}}
end = px['SPY'].index[-1]


def dd_eps(s, th=-0.5):
    """ریزش‌های بیش از ۵۰٪: قله، کف، عمق، تاریخ بازگشت به قله."""
    eps, peak, pk_d, tr, tr_d = [], s.iloc[0], s.index[0], s.iloc[0], s.index[0]
    for d, v in s.items():
        if v >= peak:
            if tr / peak - 1 <= th:
                eps.append({'peak': str(pk_d.date()), 'trough': str(tr_d.date()), 'depth_pct': round((tr / peak - 1) * 100, 1),
                            'recovered': str(d.date()), 'days_to_recover': (d - pk_d).days})
            peak, pk_d, tr, tr_d = v, d, v, d
        elif v < tr:
            tr, tr_d = v, d
    if tr / peak - 1 <= th:
        eps.append({'peak': str(pk_d.date()), 'trough': str(tr_d.date()), 'depth_pct': round((tr / peak - 1) * 100, 1),
                    'recovered': None, 'days_to_recover': None})
    return eps


for t, s in px.items():
    s = s[s.index <= end]
    ann = 365 if t.endswith('-USD') else 252
    r = {'first': str(s.index[0].date()), 'last_close': round(float(s.iloc[-1]), 2)}
    for y in (3, 5, 10, 'all'):
        s0 = s.index[0] if y == 'all' else end - pd.DateOffset(years=y)
        if y != 'all' and s.index[0] > s0 + pd.Timedelta(days=10):
            r[str(y)] = None; continue
        a = s[s.index >= s0]
        yrs = (a.index[-1] - a.index[0]).days / 365.25
        tot = float(a.iloc[-1] / a.iloc[0] - 1)
        r[str(y)] = {'from': str(a.index[0].date()), 'total_pct': round(tot * 100, 1),
                     'cagr_pct': round(((1 + tot) ** (1 / yrs) - 1) * 100, 1),
                     'vol_pct': round(float(a.pct_change().std() * np.sqrt(ann)) * 100, 1),
                     'maxdd_pct': round(float((a / a.cummax() - 1).min()) * 100, 1)}
    r['calendar_pct'] = {str(k): round(float(v) * 100, 1) for k, v in s.resample('YE').last().pct_change().dropna().items()}
    r['calendar_pct'] = {k[:4]: v for k, v in r['calendar_pct'].items()}
    if t.endswith('-USD'):
        r['drawdowns_over_50'] = dd_eps(s)
    out['assets'][t] = r

btc, eth = px['BTC-USD'], px['ETH-USD']
# چرخه‌ها (هاوینگ تا هاوینگ)
cyc = [('2016-07-09', '2020-05-11'), ('2020-05-11', '2024-04-20'), ('2024-04-20', str(end.date()))]
out['btc_cycles'] = []
for a, b in cyc:
    w = btc[(btc.index >= a) & (btc.index <= b)]
    yrs = (w.index[-1] - w.index[0]).days / 365.25
    tot = float(w.iloc[-1] / w.iloc[0])
    out['btc_cycles'].append({'from': a, 'to': b, 'multiple': round(tot, 2), 'cagr_pct': round((tot ** (1 / yrs) - 1) * 100, 1),
                              'peak_multiple_from_start': round(float(w.max() / w.iloc[0]), 2)})
ratio = (eth / btc).dropna()
out['eth_btc'] = {'first': [str(ratio.index[0].date()), round(float(ratio.iloc[0]), 4)], 'last': round(float(ratio.iloc[-1]), 4),
                  'max': [str(ratio.idxmax().date()), round(float(ratio.max()), 4)],
                  'yearly_last': {str(k.year): round(float(v), 4) for k, v in ratio.resample('YE').last().items()}}

# همبستگی ماهانه
m = pd.concat({t: s.resample('ME').last() for t, s in px.items()}, axis=1).pct_change().dropna(subset=['BTC-USD', 'SPY'])
out['corr_monthly'] = {'btc_spy_all': round(float(m['BTC-USD'].corr(m['SPY'])), 2), 'btc_gld_all': round(float(m['BTC-USD'].corr(m['GLD'])), 2),
                       'btc_spy_last3y': round(float(m['BTC-USD'].tail(36).corr(m['SPY'].tail(36))), 2),
                       'btc_gld_last3y': round(float(m['BTC-USD'].tail(36).corr(m['GLD'].tail(36))), 2),
                       'eth_btc_all': round(float(m['ETH-USD'].corr(m['BTC-USD'])), 2), 'eth_spy_all': round(float(m['ETH-USD'].corr(m['SPY'])), 2)}


def win(a, b):
    return {t: round(float(px[t][(px[t].index >= a) & (px[t].index <= b)].iloc[-1] / px[t][(px[t].index >= a) & (px[t].index <= b)].iloc[0] - 1) * 100, 1)
            for t in ('BTC-USD', 'GLD', 'SPY', 'QQQ') if len(px[t][(px[t].index >= a) & (px[t].index <= b)]) > 2}


out['crisis'] = {'covid_2020-02-19_to_03-23': win('2020-02-19', '2020-03-23'), 'year_2022': win('2021-12-31', '2022-12-30')}

# سبد ۶۰/۴۰ با سهم کوچک بیت‌کوین، بازتوازن ماهانه
mm = m[['BTC-USD', 'SPY', 'IEF']].dropna()
out['portfolio'] = {'from': str(mm.index[0].date())}
for wb in (0, 0.01, 0.03, 0.05):
    pr = wb * mm['BTC-USD'] + (1 - wb) * (0.6 * mm['SPY'] + 0.4 * mm['IEF'])
    eq = (1 + pr).cumprod()
    yrs = len(pr) / 12
    out['portfolio'][f'btc_{int(wb * 100)}pct'] = {'cagr_pct': round((float(eq.iloc[-1]) ** (1 / yrs) - 1) * 100, 2),
                                                   'vol_pct': round(float(pr.std() * np.sqrt(12)) * 100, 1),
                                                   'maxdd_pct': round(float((eq / eq.cummax() - 1).min()) * 100, 1)}

# روش‌ها روی بیت‌کوین: نگهداری، خرید ماهانه، روند ۲۰۰ روزه (سیگنال با یک روز تأخیر، هزینه ۰٫۱٪ هر تعویض)
b = btc[btc.index >= '2015-01-01']
ret = b.pct_change().fillna(0)
sig = (b > b.rolling(200).mean()).shift(1).fillna(False).astype(float)
cost = sig.diff().abs().fillna(0) * 0.001
tr = (1 + ret * sig - cost).cumprod()
start = b.index[200]
hold = b[b.index >= start] / b[start]
trend = tr[tr.index >= start] / tr[start]
yrs = (b.index[-1] - start).days / 365.25
out['btc_methods'] = {'from': str(start.date()),
                      'hold': {'cagr_pct': round((float(hold.iloc[-1]) ** (1 / yrs) - 1) * 100, 1), 'maxdd_pct': round(float((hold / hold.cummax() - 1).min()) * 100, 1)},
                      'trend200': {'cagr_pct': round((float(trend.iloc[-1]) ** (1 / yrs) - 1) * 100, 1), 'maxdd_pct': round(float((trend / trend.cummax() - 1).min()) * 100, 1),
                                   'time_in_market_pct': round(float(sig[sig.index >= start].mean()) * 100, 1), 'switches': int(sig[sig.index >= start].diff().abs().sum())}}
for y in (3, 5, 10):
    w = btc[btc.index >= end - pd.DateOffset(years=y)].resample('MS').first()
    units = (100 / w).sum()
    out['btc_methods'][f'dca_{y}y'] = {'invested': int(100 * len(w)), 'value': int(units * float(btc.iloc[-1])),
                                       'gain_pct': round((units * float(btc.iloc[-1]) / (100 * len(w)) - 1) * 100, 1)}
os.makedirs('data/us_longterm', exist_ok=True)
json.dump(out, open('data/us_longterm/crypto_returns.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
