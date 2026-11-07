"""آزمون تاریخی تقریبی قاعده‌ی اختیار خرید ربات ساعتی (options_overlay.py) — روزانه، ۳ سال.

قاعده‌ی ورود (تقریب روزانه‌ی نسخه‌ی ساعتی):
  - رژیم صعودی: شیب ۱۰ روز اخیر > ۱٪ و نوسان روزانه < ۲٪ (detect_regime روی کندل روزانه به‌جای ساعتی)
  - قیمت بالای میانگین ۲۰ روزه
  - رتبه‌بندی بر اساس بازده ۲۰ روزه؛ حداکثر ۴ موقعیت باز، هر سهم یکی
  - قرارداد: کال ۴۵ روزه با دلتای ۰٫۶۲؛ ورود با بسته‌شدن روز بعد از سیگنال (بدون نگاه به آینده)
قیمت اختیار: بلک‌شولز با نوسان ضمنی = نوسان واقعی ۲۰ روزه × ۱٫۱۵ (حداقل ۲۰٪)، نرخ ۴٪،
  هزینه‌ی اختلاف خرید و فروش ۲٫۵٪ هر طرف. فیلتر گزارش فصلی در این تقریب نیست (داده‌ی تاریخی‌اش در دسترس نیست).
خروج: نصف در +۶۰٪، باقی با حد سود متحرک ۲۵٪ از سقف، حد ضرر −۳۵٪، خروج ۷ روز مانده به سررسید.
بودجه: ۱۰ هزار دلار (۱۰٪ حساب) با سود و زیانش؛ هر ورود یک‌چهارم این سرمایه. مقایسه: همان ۱۰ هزار دلار در QQQ.
قبولی: سود در هر دو نیمه‌ی دوره، بهتر از QQQ در کل دوره، ریزش سرمایه‌ی تخصیص‌یافته کمتر از ۵۰٪، دست‌کم ۳۰ معامله.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'strategy_lab', 'opt1h')
UNIVERSES = {
    'bot8': ['MU', 'NVDA', 'DELL', 'AMZN', 'CRGY', 'KRMN', 'CVX', 'HON'],
    'large30': ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'JPM', 'V', 'MA', 'UNH', 'HD', 'PG',
                'XOM', 'CVX', 'LLY', 'ABBV', 'KO', 'PEP', 'COST', 'MRK', 'AMD', 'NFLX', 'CRM', 'ORCL', 'ADBE', 'INTC',
                'QCOM', 'HON'],
}
R, T0, DELTA, SPREAD = 0.04, 45, 0.62, 0.025
HALF_TP, TRAIL, STOP, MIN_DTE = 0.60, 0.25, -0.35, 7
EQUITY, BUDGET_PCT, MAX_POS = 100_000, 0.10, 4


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def ninv(p):
    lo, hi = -6.0, 6.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ncdf(mid) < p else (lo, mid)
    return (lo + hi) / 2


def bs_call(S, K, T, sig):
    if T <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (R + sig * sig / 2) * T) / (sig * math.sqrt(T))
    return S * ncdf(d1) - K * math.exp(-R * T) * ncdf(d1 - sig * math.sqrt(T))


def strike_for_delta(S, T, sig, delta=DELTA):
    d1 = ninv(delta)
    return S * math.exp(-(d1 * sig * math.sqrt(T) - (R + sig * sig / 2) * T))


def run(closes, qqq):
    C = closes.dropna(how='all')
    rets = C.pct_change()
    vol = (rets.rolling(20).std() * np.sqrt(252) * 1.15).clip(lower=0.20)
    sma20 = C.rolling(20).mean()
    mom = C / C.shift(20) - 1
    slope = C / C.shift(9) - 1
    v10 = rets.rolling(9).std()
    bull = (slope > 0.01) & (v10 < 0.02) & (C > sma20)
    dates = C.index[60:]
    cash_pl, open_pos, trades, curve = 0.0, [], [], []
    pending = []
    for i, d in enumerate(dates):
        # ورودهای سیگنال دیروز با بسته‌شدن امروز
        for t in pending:
            if len(open_pos) >= MAX_POS or any(p['t'] == t for p in open_pos):
                continue
            S, sig = C.at[d, t], vol.at[d, t]
            if not (S == S and sig == sig):
                continue
            T = T0 / 365
            K = strike_for_delta(S, T, sig)
            px = bs_call(S, K, T, sig) * (1 + SPREAD)
            alloc = EQUITY * BUDGET_PCT + cash_pl            # سرمایه‌ی تخصیص‌یافته با سود و زیان تا امروز
            if alloc <= 0:
                continue
            qty = (alloc / MAX_POS) / (px * 100)
            open_pos.append({'t': t, 'K': K, 'exp': i + T0 * 252 // 365, 'cost': px, 'qty': qty, 'peak': px,
                             'half': False, 'd0': str(d.date()), 'realized': 0.0})
        pending = []
        # ارزش‌گذاری و خروج
        keep = []
        for p in open_pos:
            S, sig = C.at[d, p['t']], vol.at[d, p['t']]
            days_left = max(0, (p['exp'] - i) * 365 / 252)
            mid = bs_call(S, p['K'], days_left / 365, sig if sig == sig else 0.3)
            bid = mid * (1 - SPREAD)
            p['peak'] = max(p['peak'], mid)
            pl = bid / p['cost'] - 1
            act = None
            if pl <= STOP:
                act = 'STOP'
            elif days_left <= MIN_DTE:
                act = 'EXPIRY'
            elif p['half'] and mid <= p['peak'] * (1 - TRAIL):
                act = 'TRAIL'
            elif not p['half'] and pl >= HALF_TP:
                act = 'HALF'
            if act == 'HALF':
                sold = p['qty'] / 2
                p['realized'] += sold * (bid - p['cost']) * 100
                cash_pl += sold * (bid - p['cost']) * 100
                p['qty'] -= sold
                p['half'] = True
                keep.append(p)
            elif act:
                g = p['qty'] * (bid - p['cost']) * 100
                cash_pl += g
                invested = (p['qty'] * (2 if p['half'] else 1)) * p['cost'] * 100
                trades.append({'t': p['t'], 'in': p['d0'], 'out': str(d.date()), 'exit': act,
                               'pnl': round(p['realized'] + g, 2), 'ret': round((p['realized'] + g) / invested, 3)})
            else:
                keep.append(p)
            p['mark'] = p['qty'] * (bid - p['cost']) * 100
        open_pos = keep
        curve.append((d, cash_pl + sum(p['mark'] for p in open_pos)))
        # سیگنال امروز
        cands = [t for t in C.columns if bool(bull.at[d, t]) and mom.at[d, t] == mom.at[d, t]]
        pending = sorted(cands, key=lambda t: -mom.at[d, t])[:MAX_POS]
    eq = pd.Series(dict(curve)) + EQUITY * BUDGET_PCT          # سرمایه‌ی تخصیص‌یافته ۱۰ هزار دلار + سود و زیان
    return eq, pd.DataFrame(trades)


def stats(eq):
    r = eq.iloc[-1] / eq.iloc[0] - 1
    dd = (eq / eq.cummax() - 1).min()
    return {'return_pct': round(r * 100, 1), 'max_dd_pct': round(dd * 100, 1)}


def main():
    import yfinance as yf
    os.makedirs(OUT, exist_ok=True)
    allt = sorted({t for u in UNIVERSES.values() for t in u} | {'QQQ'})
    df = yf.download(allt, period='3y', interval='1d', auto_adjust=True, progress=False)['Close']
    qqq = df['QQQ'].dropna()
    res = {}
    for name, tick in UNIVERSES.items():
        eq, tr = run(df[[t for t in tick if t in df]], qqq)
        mid = eq.index[len(eq) // 2]
        q = qqq.reindex(eq.index).ffill()
        qeq = EQUITY * BUDGET_PCT * q / q.iloc[0]
        h1, h2 = stats(eq[eq.index <= mid]), stats(eq[eq.index >= mid])
        full, qf = stats(eq), stats(qeq)
        n = int(len(tr))
        ok = (h1['return_pct'] > 0 and h2['return_pct'] > 0 and full['return_pct'] > qf['return_pct']
              and full['max_dd_pct'] > -50 and n >= 30)
        res[name] = {'full': full, 'first_half': h1, 'second_half': h2, 'qqq': qf, 'trades': n,
                     'win_rate_pct': round(float((tr.pnl > 0).mean() * 100), 1) if n else None,
                     'avg_trade_ret_pct': round(float(tr.ret.mean() * 100), 1) if n else None,
                     'exits': tr.exit.value_counts().to_dict() if n else {}, 'passed': bool(ok),
                     'start': str(eq.index[0].date()), 'end': str(eq.index[-1].date())}
        tr.to_csv(os.path.join(OUT, f'trades_{name}.csv'), index=False)
        print(name, json.dumps(res[name]))
    res['verdict'] = 'قبول' if res['large30']['passed'] else 'رد'
    res['note'] = ('تصمیم بر اساس ۳۰ سهم بزرگ است؛ ۸ سهم ربات در اکتبر به‌خاطر رشد اخیرشان انتخاب شده‌اند و آزمون رویشان '
                   'خوش‌بینانه است. قیمت اختیار با بلک‌شولز تقریب زده شده و فیلتر گزارش فصلی در آزمون نیست.')
    json.dump(res, open(os.path.join(OUT, 'result.json'), 'w'), ensure_ascii=False, indent=1)
    print('verdict', res['verdict'])


if __name__ == '__main__':
    main()
