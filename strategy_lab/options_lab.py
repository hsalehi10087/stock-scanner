"""آزمایش افزودن آپشن به استراتژی روند طلا (GLD) — بک‌تست تقریبی با قیمت‌گذاری Black-Scholes.

داده: GLD روزانه، ^GVZ (شاخص نوسان ضمنی آپشن‌های GLD از Cboe) به‌جای IV، ^IRX برای نرخ بدون ریسک.
محدودیت: زنجیره‌ی واقعی آپشن نداریم؛ اسکیو با ضریب ثابت و هزینه‌ی اسپرد با درصدی از پریمیوم تقریب زده شده.
گونه‌ها:
  base   — همان استراتژی روند (۴۰/۱۰/۲×ATR، اندازه‌گذاری نوسان ۱۲٪)
  put    — base + پوت محافظ ۱۰٪ OTM با سررسید ~۹۰ روز، رول وقتی ≤۳۰ روز مانده، بستن با خروج
  put_b  — مثل put ولی بودجه‌ی سالانه‌ی پریمیوم ≤ ۲٪ سهمیه و فقط وقتی GVZ زیر صدک ۵۰ (پوت ارزان)
  cc80   — base + فروش کال ۵٪ OTM سی‌روزه فقط وقتی GVZ بالای صدک ۸۰ یک‌ساله‌ی گذشته
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

OUT = os.path.join('data', 'strategy_lab', 'GLD_options')
COST, TV, SPREAD = 0.0003, 0.12, 0.04  # هزینه‌ی سهم هر طرف، هدف نوسان، اسپرد آپشن (٪ پریمیوم هر طرف)


def N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, r, v, kind):
    if T <= 0:
        return max(0.0, (K - S) if kind == 'p' else (S - K))
    d1 = (math.log(S / K) + (r + v * v / 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    if kind == 'c':
        return S * N(d1) - K * math.exp(-r * T) * N(d2)
    return K * math.exp(-r * T) * N(-d2) - S * N(-d1)


def flat(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def trend_pos(df, n=40, m=10, k=2.0):
    tr = pd.concat([df.High - df.Low, (df.High - df.Close.shift()).abs(), (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)
    a = tr.ewm(alpha=1 / 14, adjust=False).mean()
    hi, lo = df.High.rolling(n).max().shift(), df.Low.rolling(m).min().shift()
    cur, peak, out = 0, 0.0, []
    for c, h, l, av in zip(df.Close, hi, lo, a):
        if cur == 0 and c > h:
            cur, peak = 1, c
        elif cur == 1:
            peak = max(peak, c)
            if c < l or c < peak - k * av:
                cur = 0
        out.append(cur)
    r = df.Close.pct_change()
    size = (TV / (r.rolling(20).std() * math.sqrt(252))).clip(upper=1).fillna(0)
    return pd.Series(out, df.index) * size


def run(df, w, variant):
    """w = وزن GLD در پایان روز t (از سیگنال روز t)، از روز t+1 اعمال می‌شود. خروجی: بازده روزانه‌ی سبد."""
    S, iv, rf, pct = df.Close.values, df.iv.values, df.rf.values, df.ivpct.values
    W = w.values
    rets, opt, prem_paid, prem_got = [0.0], None, 0.0, 0.0
    budget_year, spent = None, 0.0
    for t in range(1, len(df)):
        wt = W[t - 1]
        day = wt * (S[t] / S[t - 1] - 1) - COST * abs(W[t - 1] - (W[t - 2] if t > 1 else 0))
        # ارزش‌گذاری آپشن باز (بر حسب کسری از سرمایه)
        if opt:
            T_old, T_new = opt['T'], opt['T'] - 1 / 252
            v_old = bs(S[t - 1], opt['K'], T_old, rf[t - 1], opt['ivf'] * iv[t - 1], opt['kind'])
            v_new = bs(S[t], opt['K'], max(T_new, 0), rf[t], opt['ivf'] * iv[t], opt['kind'])
            day += opt['sign'] * opt['units'] * (v_new - v_old)
            opt['T'] = T_new
        # تصمیم پایان روز t
        close_it = opt and (W[t] == 0 or opt['T'] <= (30 / 252 if opt['kind'] == 'p' else 0))
        if close_it:
            v = bs(S[t], opt['K'], max(opt['T'], 0), rf[t], opt['ivf'] * iv[t], opt['kind'])
            day -= SPREAD * v * opt['units']
            opt = None
        if opt is None and W[t] > 0:
            yr = df.index[t].year
            if yr != budget_year:
                budget_year, spent = yr, 0.0
            units = W[t] / S[t]  # تعداد «سهم» پوشش‌داده‌شده به ازای هر ۱ دلار سرمایه
            if variant in ('put', 'put_b'):
                K, T, ivf = 0.9 * S[t], 90 / 252, 1.12
                p = bs(S[t], K, T, rf[t], ivf * iv[t], 'p') * units
                ok = variant == 'put' or (pct[t] < 0.5 and spent + p <= 0.02)
                if ok:
                    opt = {'K': K, 'T': T, 'kind': 'p', 'sign': 1, 'units': units, 'ivf': ivf}
                    day -= SPREAD * p
                    prem_paid += p
                    spent += p
            elif variant == 'cc80' and pct[t] >= 0.8:
                K, T, ivf = 1.05 * S[t], 30 / 252, 0.95
                c = bs(S[t], K, T, rf[t], ivf * iv[t], 'c') * units
                opt = {'K': K, 'T': T, 'kind': 'c', 'sign': -1, 'units': units, 'ivf': ivf}
                day -= SPREAD * c
                prem_got += c
        rets.append(day)
    yrs = len(df) / 252
    return pd.Series(rets, df.index), prem_paid / yrs, prem_got / yrs


def stats(s):
    eq = (1 + s).cumprod()
    return {'cagr': round((eq.iloc[-1] ** (252 / len(s)) - 1) * 100, 2),
            'sharpe': round(float(s.mean() / s.std() * math.sqrt(252)), 2),
            'max_dd': round(float((eq / eq.cummax() - 1).min() * 100), 2),
            'worst_day': round(float(s.min() * 100), 2)}


def main():
    g = flat(yf.download('GLD', start='2008-01-01', progress=False, auto_adjust=False))[['High', 'Low', 'Close']]
    v = flat(yf.download('^GVZ', start='2008-01-01', progress=False, auto_adjust=False))['Close'].rename('gvz')
    ir = flat(yf.download('^IRX', start='2008-01-01', progress=False, auto_adjust=False))['Close'].rename('irx')
    df = g.join(v, how='inner').join(ir, how='left').dropna(subset=['Close', 'gvz'])
    df['iv'] = df.gvz / 100
    df['rf'] = (df.irx.ffill().fillna(2) / 100)
    df['ivpct'] = df.gvz.rolling(252, min_periods=120).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True).fillna(0.5)
    w = trend_pos(df)
    res, lines = {}, []
    for var in ('base', 'put', 'put_b', 'cc80'):
        s, paid, got = run(df, w, var)
        st = stats(s)
        st.update({'premium_paid_pct_yr': round(paid * 100, 2), 'premium_sold_pct_yr': round(got * 100, 2)})
        for nm, a, b in (('full', None, None), ('2020_crash', '2020-02-15', '2020-04-30'),
                         ('2013_crash', '2013-04-01', '2013-07-31'), ('last_12m', str((df.index[-1] - pd.Timedelta(days=365)).date()), None)):
            if nm != 'full':
                st[nm] = stats(s[a:b])
        res[var] = st
        lines.append(f"{var}: {st}")
    res['meta'] = {'start': str(df.index[0].date()), 'end': str(df.index[-1].date()),
                   'gvz_now': float(df.gvz.iloc[-1]), 'gvz_pct_now': round(float(df.ivpct.iloc[-1]), 2),
                   'share_days_gvz_ge_p80': round(float((df.ivpct >= 0.8).mean()), 3),
                   'share_days_in_trend': round(float((w > 0).mean()), 3),
                   'put_10otm_90d_cost_now_pct': round(bs(df.Close.iloc[-1], 0.9 * df.Close.iloc[-1], 90 / 252,
                                                           df.rf.iloc[-1], 1.12 * df.iv.iloc[-1], 'p') / df.Close.iloc[-1] * 100, 2)}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'results.json'), 'w'), indent=1)
    open(os.path.join(OUT, 'diagnostics.txt'), 'w').write('\n'.join(lines + [json.dumps(res['meta'])]))
    print('\n'.join(lines), res['meta'])


if __name__ == '__main__':
    main()
