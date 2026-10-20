"""آزمایشگاه استراتژی سهام برای جایگزینی ربات یک‌ساعته.

۱) مبنا: قانون فعلی ربات یک‌ساعته روی داده‌ی ساعتی ۲ سال اخیر (Yahoo فقط ~۷۳۰ روز ساعتی دارد).
۲) استراتژی‌های روزانه از ۲۰۰۷ (سیگنال در بسته‌شدن روز t، اجرا در بازگشایی t+1 → بدون نگاه به آینده):
   MR  — خرید پولبک در روند صعودی: close>SMA200 و RSI(2)<th و بازار (SPY>SMA200)، خروج close>SMA(x) یا ۱۰ روز
   MOM — چرخش ماهانه‌ی مومنتوم: بالاترین بازده k ماهه (بدون ماه آخر)، فقط بالای SMA200، بازار مثبت؛ وگرنه نقد
   COMBO — ۵۰٪ MR + ۵۰٪ MOM
   هزینه: ETF ۰٫۰۵٪ و سهام ۰٫۱۰٪ در هر طرف.
دو جهان: ETF (بدون سوگیری بقا) و ۵۰ سهم بزرگ امروز (سوگیری بقا دارد — فقط برای مقایسه).
پارامترها روی ۲۰۰۷–۲۰۱۸ انتخاب و روی ۲۰۱۹ تا امروز (خارج از نمونه) سنجیده می‌شوند.
"""
import itertools
import json
import math
import os

import numpy as np
import pandas as pd
import yfinance as yf

OUT = os.path.join('data', 'strategy_lab', 'equity')
ETF = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLP', 'XLI', 'XLB', 'XLU',
       'TLT', 'IEF', 'GLD']
STK = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'JPM', 'V', 'UNH', 'XOM', 'JNJ', 'PG',
       'MA', 'HD', 'COST', 'ABBV', 'MRK', 'PEP', 'KO', 'WMT', 'BAC', 'CVX', 'ORCL', 'CRM', 'AMD', 'ADBE', 'NFLX',
       'CSCO', 'INTC', 'QCOM', 'TXN', 'AMAT', 'MU', 'LLY', 'TMO', 'ABT', 'MCD', 'NKE', 'DIS', 'CAT', 'GE', 'HON',
       'UPS', 'IBM', 'GS', 'MS', 'PLTR', 'BRK-B']
SPLIT = '2019-01-01'


def load(tickers, start='2005-01-01'):
    df = yf.download(tickers, start=start, interval='1d', auto_adjust=True, progress=False, group_by='column')
    o, c = df['Open'].dropna(how='all'), df['Close'].dropna(how='all')
    return o, c


def rsi2(c):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def stats(r):
    r = r.dropna()
    if len(r) < 20 or r.std() == 0:
        return {'cagr': 0.0, 'sharpe': 0.0, 'max_dd': 0.0, 'vol': 0.0}
    eq = (1 + r).cumprod()
    return {'cagr': round((eq.iloc[-1] ** (252 / len(r)) - 1) * 100, 2),
            'sharpe': round(float(r.mean() / r.std() * math.sqrt(252)), 2),
            'max_dd': round(float((eq / eq.cummax() - 1).min() * 100), 2),
            'vol': round(float(r.std() * math.sqrt(252) * 100), 1)}


def run_weights(W, o, cost):
    """W[t] = وزن تصمیم‌گرفته در بسته‌شدن t؛ از بازگشایی t+1 تا بازگشایی t+2 نگه داشته می‌شود."""
    oo = o.shift(-1) / o - 1                      # بازده از بازگشایی t تا بازگشایی t+1
    held = W.shift(1).fillna(0)                   # وزنی که در بازگشایی t برقرار است
    gross = (held * oo).sum(axis=1)
    turn = held.diff().abs().sum(axis=1).fillna(held.abs().sum(axis=1))
    return (gross - cost * turn).shift(1).dropna()  # بازده در روز تحقق


def mr_weights(o, c, spy_ok, th=10, exit_n=5, slots=10, max_days=10):
    sma200, smax, r2 = c.rolling(200).mean(), c.rolling(exit_n).mean(), rsi2(c)
    Wv = np.zeros(c.shape)
    held, trades = {}, []
    cv, s200, sx, rv = c.values, sma200.values, smax.values, r2.values
    cols = list(c.columns)
    for t in range(len(c.index)):
        for j in list(held):
            ent_t, ent_px = held[j]
            if cv[t, j] > sx[t, j] or t - ent_t >= max_days or np.isnan(cv[t, j]):
                trades.append(cv[t, j] / ent_px - 1 if not np.isnan(cv[t, j]) else 0.0)
                del held[j]
        if spy_ok.iloc[t] and len(held) < slots:
            cand = [(rv[t, j], j) for j in range(len(cols))
                    if j not in held and not np.isnan(s200[t, j]) and cv[t, j] > s200[t, j] and rv[t, j] < th]
            for _, j in sorted(cand)[:slots - len(held)]:
                held[j] = (t, cv[t, j])
        for j in held:
            Wv[t, j] = 1.0 / slots
    return pd.DataFrame(Wv, index=c.index, columns=c.columns), trades


def mom_weights(c, spy_ok, look=6, top=5):
    me = c.resample('ME').last()
    ret = me.shift(1) / me.shift(1 + look) - 1          # بازده k ماهه بدون ماه آخر
    sma = c.rolling(200).mean().resample('ME').last()
    W = pd.DataFrame(0.0, index=c.index, columns=c.columns)
    rows = {}
    for d in me.index:
        ok = spy_ok.asof(d) if len(spy_ok[:d]) else False
        w = pd.Series(0.0, index=c.columns)
        if ok:
            elig = ret.loc[d][(me.loc[d] > sma.loc[d]) & ret.loc[d].notna()]
            pick = elig.nlargest(top).index
            if len(pick):
                w[pick] = 1.0 / top
        rows[d] = w
    M = pd.DataFrame(rows).T
    W = M.reindex(c.index, method='ffill').fillna(0.0)
    return W


def baseline_hourly(symbols):
    """قانون فعلی ربات یک‌ساعته (بدون آپشن) روی داده‌ی ساعتی ~۷۳۰ روز."""
    df = yf.download(symbols + ['SPY'], period='729d', interval='1h', auto_adjust=True, progress=False)['Close']
    df = df.dropna(how='all')
    out = {}
    for every in (1, 7):   # هر ساعت (طراحی) و تقریباً روزی یک بار (واقعیت اجرا در GitHub)
        idx = df.index[::every]
        c = df.loc[idx]
        spy = c['SPY'].values
        eq, rets, trades = 1.0, [], []
        state = {s: None for s in symbols}
        budget = 0.5 / len(symbols)
        for t in range(10, len(idx)):
            def regime(x):
                w = x[t - 10:t + 1] if False else x[max(0, t - 9):t + 1]
                if len(w) < 10 or np.isnan(w).any():
                    return 'R'
                sl, vo = w[-1] / w[0] - 1, np.std(np.diff(w) / w[:-1])
                return 'B' if sl > 0.01 and vo < 0.02 else ('D' if sl < -0.01 and vo < 0.02 else 'R')
            pnl = 0.0
            mkt_bear = regime(spy) == 'D'
            for s in symbols:
                x = c[s].values
                p = x[t]
                if np.isnan(p):
                    continue
                st = state[s]
                if st:
                    pnl += st['w'] * (p / x[t - 1] - 1) if not np.isnan(x[t - 1]) else 0
                    st['peak'] = max(st['peak'], p)
                    a = st['avg']
                    ex = (p >= a * 1.025 or p <= a * 0.97 or (st['peak'] >= a * 1.01 and p <= st['peak'] * 0.99))
                    if ex:
                        trades.append(p / a - 1)
                        pnl -= 0.001 * st['w']
                        state[s] = None
                        continue
                    for lvl, dip, frac in ((1, 0.008, 0.3), (2, 0.015, 0.5)):
                        if st['lvl'] == lvl and p <= st['l1'] * (1 - dip):
                            add = budget * frac
                            st['avg'] = (a * st['w'] + p * add) / (st['w'] + add)
                            st['w'] += add
                            st['lvl'] += 1
                            pnl -= 0.001 * add
                elif not mkt_bear and regime(x) == 'B':
                    state[s] = {'w': budget * 0.2, 'avg': p, 'l1': p, 'peak': p, 'lvl': 1}
                    pnl -= 0.001 * budget * 0.2
            rets.append(pnl)
        r = pd.Series(rets, index=idx[10:])
        daily = (1 + r).groupby(r.index.date).prod() - 1
        st = stats(pd.Series(daily.values))
        st.update({'trades': len(trades), 'win_rate': round(float(np.mean([x > 0 for x in trades])) * 100, 1) if trades else 0,
                   'avg_trade_pct': round(float(np.mean(trades)) * 100, 2) if trades else 0})
        spy_d = c['SPY'].groupby(c.index.date).last().pct_change().dropna()
        out['hourly' if every == 1 else 'once_a_day'] = st
        out['spy_same_period'] = stats(pd.Series(spy_d.values))
    return out


def evaluate(name, W, o, cost, trades=None):
    r = run_weights(W, o, cost)
    expo = float(W.sum(axis=1).mean())
    res = {'full': stats(r), 'in_sample': stats(r[:SPLIT]), 'out_sample': stats(r[SPLIT:]),
           'last_12m': stats(r[r.index >= r.index[-1] - pd.Timedelta(days=365)]), 'exposure': round(expo, 2)}
    if trades is not None:
        res['trades'] = len(trades)
        res['win_rate'] = round(float(np.mean([x > 0 for x in trades])) * 100, 1) if trades else 0
        res['avg_trade_pct'] = round(float(np.mean(trades)) * 100, 2) if trades else 0
    return res, r


def lab(universe_name, tickers, cost, start='2005-01-01'):
    o_all, c_all = load(sorted(set(tickers + ['SPY', 'QQQ'])), start)
    o, c = o_all, c_all
    spy = c['SPY']
    spy_ok = (spy > spy.rolling(200).mean()).reindex(c.index).fillna(False)
    c, o = c[tickers], o[tickers]
    c = c[c.index >= '2006-06-01']
    o = o.reindex(c.index)
    spy_ok = spy_ok.reindex(c.index).fillna(False)
    first = c.index[c.index >= '2007-01-01'][0]
    out = {'universe': tickers, 'start': str(first.date()), 'end': str(c.index[-1].date())}

    # جست‌وجوی پارامتر فقط روی دوره‌ی آموزش
    mr_grid, mom_grid = {}, {}
    for th, ex in itertools.product([5, 10, 20], [3, 5, 10]):
        W, tr = mr_weights(o, c, spy_ok, th=th, exit_n=ex, slots=10 if len(tickers) > 20 else 5)
        res, _ = evaluate('mr', W.loc[first:], o.loc[first:], cost, tr)
        mr_grid[f'rsi<{th}/exit_sma{ex}'] = {k: res[k] for k in ('in_sample', 'out_sample')}
    for look, top in itertools.product([3, 6, 12], [3, 5, 8]):
        W = mom_weights(c, spy_ok, look, top)
        res, _ = evaluate('mom', W.loc[first:], o.loc[first:], cost)
        mom_grid[f'look{look}/top{top}'] = {k: res[k] for k in ('in_sample', 'out_sample')}
    best_mr = max(mr_grid, key=lambda k: mr_grid[k]['in_sample']['sharpe'])
    best_mom = max(mom_grid, key=lambda k: mom_grid[k]['in_sample']['sharpe'])
    th, ex = [int(x) for x in best_mr.replace('rsi<', '').replace('exit_sma', '').split('/')]
    look, top = [int(x) for x in best_mom.replace('look', '').replace('top', '').split('/')]

    Wmr, tr = mr_weights(o, c, spy_ok, th=th, exit_n=ex, slots=10 if len(tickers) > 20 else 5)
    Wmom = mom_weights(c, spy_ok, look, top)
    Wmr, Wmom = Wmr.loc[first:], Wmom.loc[first:]
    oo = o.loc[first:]
    out['MR'], r_mr = evaluate('MR', Wmr, oo, cost, tr)
    out['MOM'], r_mom = evaluate('MOM', Wmom, oo, cost)
    out['COMBO'], r_cb = evaluate('COMBO', 0.5 * Wmr + 0.5 * Wmom, oo, cost)
    out['MR']['params'], out['MOM']['params'] = best_mr, best_mom
    for b in ('SPY', 'QQQ'):
        oc = o_all[b].reindex(oo.index)
        rb = (oc.shift(-1) / oc - 1).shift(1).loc[first:].dropna()
        out[b] = {'full': stats(rb), 'in_sample': stats(rb[:SPLIT]), 'out_sample': stats(rb[SPLIT:]),
                  'last_12m': stats(rb[rb.index >= rb.index[-1] - pd.Timedelta(days=365)])}
    out['grid_MR'], out['grid_MOM'] = mr_grid, mom_grid
    yearly = pd.DataFrame({'MR': r_mr, 'MOM': r_mom, 'COMBO': r_cb}).groupby(lambda d: d.year).apply(lambda x: (1 + x).prod() - 1)
    out['yearly_pct'] = (yearly * 100).round(1).to_dict(orient='index')
    # سیگنال‌های امروز (برای نمونه)
    out['today'] = {'MR_holdings': [k for k, v in Wmr.iloc[-1].items() if v > 0],
                    'MOM_holdings': [k for k, v in Wmom.iloc[-1].items() if v > 0],
                    'spy_above_200': bool(spy_ok.iloc[-1])}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    res = {}
    try:
        res['baseline_1h'] = baseline_hourly(['NVDA', 'PLTR', 'AAPL', 'MSFT', 'AMZN', 'CRGY', 'KRMN', 'MU'])
    except Exception as e:
        res['baseline_1h'] = {'error': repr(e)}
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), indent=1, default=str)
    res['etf'] = lab('etf', ETF, 0.0005)
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), indent=1, default=str)
    res['stocks'] = lab('stocks', STK, 0.0010)
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: (v if k == 'baseline_1h' else {s: v[s].get('full') if isinstance(v.get(s), dict) else None
                                                         for s in ('MR', 'MOM', 'COMBO', 'SPY', 'QQQ')})
                      for k, v in res.items()}, indent=1, default=str))


if __name__ == '__main__':
    main()
