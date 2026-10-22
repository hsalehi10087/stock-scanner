"""شکارچی روش — موتور آزمون عمومی برای هر روش (سهام، ETF، کریپتو، فارکس، آپشن تقریبی).

هر روش یک فایل YAML در strategy_hunter/specs است. قانون اجرا:
  سیگنال در بسته‌شدن کندل t ← معامله در بازگشایی کندل t+1 (بدون نگاه به آینده).
  حد ضرر / حد سود درون کندل با High/Low سنجیده می‌شود (اگر هر دو در یک کندل خورد، حد ضرر فرض می‌شود).
  هزینه در هر طرف: سهام/ETF ۰٫۰۵٪، کریپتو ۰٫۱۰٪، فارکس ۰٫۰۲٪، آپشن تقریبی ۴٪ پریمیوم.
  ۷۰٪ اول داده = آموزش، ۳۰٪ آخر = آزمون (خارج از نمونه). مقایسه با نگه‌داشتن ساده‌ی همان دارایی.
  «شبیه‌سازی زنده»: همان قانون از روز اضافه شدن روش به بعد، با ۱٬۰۰۰ دلار.
"""
import math
import re

import numpy as np
import pandas as pd

COST = {'stock': 0.0005, 'etf': 0.0005, 'crypto': 0.0010, 'forex': 0.0002, 'option': 0.04}
BARS_PER_YEAR = {'1d': {'crypto': 365, 'default': 252}, '1h': {'crypto': 24 * 365, 'forex': 24 * 260, 'default': 7 * 252}}
SAFE = re.compile(r'^[\w\s\.\(\)<>=!&|+\-*/,]*$')
KEYWORDS = {'and', 'or', 'not', 'abs', 'True', 'False'}


# ---------------- داده ----------------
def load_prices(symbols, timeframe='1d', start='2010-01-01'):
    import yfinance as yf
    kw = {'period': '729d'} if timeframe == '1h' else {'start': start}
    out = {}
    for s in symbols:
        df = yf.download(s, interval=timeframe, auto_adjust=True, progress=False, **kw)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[['open', 'high', 'low', 'close', 'volume']].dropna(subset=['close'])
        if len(df) > 50:
            out[s] = df
    return out


# ---------------- اندیکاتورها ----------------
def _rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _atr(df, n):
    tr = pd.concat([df.high - df.low, (df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def indicator(df, spec):
    fn, n = spec['fn'], int(spec.get('n', 14))
    col = df[spec.get('col', 'close')]
    if fn == 'sma':
        return col.rolling(n).mean()
    if fn == 'ema':
        return col.ewm(span=n, adjust=False).mean()
    if fn == 'rsi':
        return _rsi(col, n)
    if fn == 'atr':
        return _atr(df, n)
    if fn == 'highest':      # سقف n کندل قبل (بدون کندل فعلی)
        return df[spec.get('col', 'high')].rolling(n).max().shift(int(spec.get('shift', 1)))
    if fn == 'lowest':
        return df[spec.get('col', 'low')].rolling(n).min().shift(int(spec.get('shift', 1)))
    if fn == 'roc':
        return col / col.shift(n) - 1
    if fn == 'zscore':
        return (col - col.rolling(n).mean()) / col.rolling(n).std()
    if fn == 'std':
        return col.pct_change().rolling(n).std()
    if fn in ('bb_upper', 'bb_lower', 'bb_mid'):
        m, sd, k = col.rolling(n).mean(), col.rolling(n).std(), float(spec.get('k', 2))
        return {'bb_upper': m + k * sd, 'bb_lower': m - k * sd, 'bb_mid': m}[fn]
    if fn in ('macd', 'macd_signal', 'macd_hist'):
        f, s, g = int(spec.get('fast', 12)), int(spec.get('slow', 26)), int(spec.get('signal', 9))
        macd = col.ewm(span=f, adjust=False).mean() - col.ewm(span=s, adjust=False).mean()
        sig = macd.ewm(span=g, adjust=False).mean()
        return {'macd': macd, 'macd_signal': sig, 'macd_hist': macd - sig}[fn]
    if fn == 'stoch_k':
        lo, hi = df.low.rolling(n).min(), df.high.rolling(n).max()
        return (df.close - lo) / (hi - lo) * 100
    if fn == 'prev':        # مقدار k کندل قبل از یک ستون
        return df[spec.get('col', 'close')].shift(int(spec.get('k', 1)))
    if fn == 'ibs':
        return (df.close - df.low) / (df.high - df.low).replace(0, np.nan)
    if fn == 'weekday':
        return pd.Series(df.index.dayofweek, index=df.index, dtype=float)
    if fn == 'day_of_month':
        return pd.Series(df.index.day, index=df.index, dtype=float)
    raise ValueError(f'unknown indicator fn {fn}')


def build_frame(df, spec):
    """اندیکاتورها به ترتیب ساخته می‌شوند؛ هر اندیکاتور می‌تواند به ستون‌های قبلی ارجاع بدهد (مثلاً prev روی stoch_k)."""
    x = df.copy()
    for name, ind in (spec.get('indicators') or {}).items():
        x[name] = indicator(x, ind)
    return x


def evaluate_expr(x, expr):
    if not expr:
        return pd.Series(False, index=x.index)
    if not SAFE.match(expr):
        raise ValueError(f'unsafe expression: {expr}')
    for tok in re.findall(r'[A-Za-z_]\w*', expr):
        if tok not in x.columns and tok not in KEYWORDS:
            raise ValueError(f'unknown name in expression: {tok}')
    return x.eval(expr, engine='python').fillna(False).astype(bool)


# ---------------- اجرای معاملات ----------------
def simulate(x, spec, asset_class):
    """سیگنال‌ها روی یک نماد → بازده هر کندل (نسبت به سرمایه‌ی اختصاص‌یافته) و فهرست معاملات."""
    side = 1 if spec.get('side', 'long') == 'long' else -1
    ent, exi = evaluate_expr(x, spec.get('entry')), evaluate_expr(x, spec.get('exit'))
    sl, tp = spec.get('stop_loss_pct'), spec.get('take_profit_pct')
    max_hold = spec.get('max_hold_bars')
    cost = COST.get(asset_class, 0.0005)
    o, h, l, c = x.open.values, x.high.values, x.low.values, x.close.values
    E, X = ent.values, exi.values
    n = len(x)
    ret = np.zeros(n)
    trades = []
    pos, entry_px, entry_i = 0, 0.0, 0
    want_in = want_out = False
    for t in range(1, n):
        ref = None
        if want_in and pos == 0:                       # ورود در بازگشایی
            pos, entry_px, entry_i, ref = side, o[t], t, o[t]
            ret[t] -= cost
        elif want_out and pos != 0:                    # خروج در بازگشایی
            ret[t] += pos * (o[t] / c[t - 1] - 1) - cost
            trades.append(pos * (o[t] / entry_px - 1) - 2 * cost)
            pos = 0
        elif pos != 0:
            ref = c[t - 1]
        want_in = want_out = False
        if pos != 0:
            exit_px = None
            if sl:
                stop = entry_px * (1 - pos * sl)
                if (pos == 1 and l[t] <= stop) or (pos == -1 and h[t] >= stop):
                    exit_px = min(o[t], stop) if pos == 1 else max(o[t], stop)
            if exit_px is None and tp:
                tgt = entry_px * (1 + pos * tp)
                if (pos == 1 and h[t] >= tgt) or (pos == -1 and l[t] <= tgt):
                    exit_px = max(o[t], tgt) if pos == 1 else min(o[t], tgt)
            if exit_px is not None:
                ret[t] += pos * (exit_px / ref - 1) - cost
                trades.append(pos * (exit_px / entry_px - 1) - 2 * cost)
                pos = 0
            else:
                ret[t] += pos * (c[t] / ref - 1)
                if X[t] or (max_hold and t - entry_i >= int(max_hold)):
                    want_out = True
        if pos == 0 and E[t]:
            want_in = True
    return pd.Series(ret, index=x.index), trades


def option_proxy(x, spec):
    """آپشن تقریبی: هر سیگنال ورود = خرید کال/پوت با سررسید dte روز و فاصله‌ی moneyness؛ قیمت با Black-Scholes،
    نوسان ضمنی = نوسان ۲۰ روزه × ۱٫۱؛ خروج با سیگنال خروج، max_hold_bars یا سررسید. بازده به نسبت پریمیوم × allocation."""
    o = spec['option']
    kind, dte, mny, alloc = o['type'], int(o.get('dte', 30)), float(o.get('moneyness', 0.0)), float(o.get('allocation', 0.1))
    ent, exi = evaluate_expr(x, spec.get('entry')), evaluate_expr(x, spec.get('exit'))
    vol = (x.close.pct_change().rolling(20).std() * math.sqrt(252) * 1.1).bfill().values
    c = x.close.values
    N = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def bs(S, K, T, v):
        if T <= 0:
            return max(0.0, S - K) if kind == 'call' else max(0.0, K - S)
        d1 = (math.log(S / K) + 0.5 * v * v * T) / (v * math.sqrt(T))
        d2 = d1 - v * math.sqrt(T)
        return S * N(d1) - K * N(d2) if kind == 'call' else K * N(-d2) - S * N(-d1)
    ret, trades = np.zeros(len(c)), []
    t = 1
    while t < len(c) - 1:
        if ent.iloc[t - 1]:
            K = c[t] * (1 + mny if kind == 'call' else 1 - mny)
            p0 = bs(c[t], K, dte / 365, vol[t]) * (1 + COST['option'])
            j = t + 1
            while j < len(c) and j - t < dte * 252 / 365:
                if exi.iloc[j - 1] or (spec.get('max_hold_bars') and j - t >= spec['max_hold_bars']):
                    break
                j += 1
            j = min(j, len(c) - 1)
            p1 = bs(c[j], K, max(0, dte - (j - t) * 365 / 252) / 365, vol[j]) * (1 - COST['option'])
            r = p1 / p0 - 1 if p0 > 0 else 0
            trades.append(r)
            ret[j] += alloc * r
            t = j + 1
        else:
            t += 1
    return pd.Series(ret, index=x.index), trades


# ---------------- سنجه‌ها ----------------
def stats(r, ppy):
    r = r.dropna()
    if len(r) < 10 or r.std() == 0:
        return {'cagr': 0.0, 'sharpe': 0.0, 'max_dd': 0.0, 'total': 0.0}
    eq = (1 + r).cumprod()
    yrs = len(r) / ppy
    return {'cagr': round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 2) if yrs > 0 and eq.iloc[-1] > 0 else -100.0,
            'sharpe': round(float(r.mean() / r.std() * math.sqrt(ppy)), 2),
            'max_dd': round(float((eq / eq.cummax() - 1).min() * 100), 2),
            'total': round((eq.iloc[-1] - 1) * 100, 2)}


def run_spec(spec, prices=None):
    ac = spec.get('asset_class', 'stock')
    tf = spec.get('timeframe', '1d')
    prices = prices or load_prices(spec['symbols'], tf, spec.get('start', '2010-01-01'))
    if not prices:
        raise ValueError('no price data')
    ppy = BARS_PER_YEAR[tf].get(ac, BARS_PER_YEAR[tf]['default'])
    rets, bh, trades = [], [], []
    for s, df in prices.items():
        x = build_frame(df, spec)
        r, tr = option_proxy(x, spec) if ac == 'option' else simulate(x, spec, ac)
        rets.append(r)
        bh.append(df.close.pct_change().fillna(0))
        trades += tr
    R = pd.concat(rets, axis=1).fillna(0).mean(axis=1)      # سرمایه‌ی مساوی بین نمادها
    B = pd.concat(bh, axis=1).fillna(0).mean(axis=1)
    cut = R.index[int(len(R) * 0.7)]
    added = pd.Timestamp(spec.get('added', R.index[-1]))
    if R.index.tz is not None and added.tz is None:
        added = added.tz_localize(R.index.tz)
    fwd = R[R.index > added]
    res = {'full': stats(R, ppy), 'in_sample': stats(R[:cut], ppy), 'out_sample': stats(R[cut:], ppy),
           'buyhold_full': stats(B, ppy), 'buyhold_out_sample': stats(B[cut:], ppy),
           'trades': len(trades), 'win_rate': round(float(np.mean([t > 0 for t in trades])) * 100, 1) if trades else 0.0,
           'avg_trade_pct': round(float(np.mean(trades)) * 100, 2) if trades else 0.0,
           'exposure': round(float((R != 0).mean()), 2),
           'period': f'{R.index[0].date()} → {R.index[-1].date()}', 'oos_start': str(cut.date()),
           'forward_days': int(len(fwd)), 'forward_usd': round(1000 * float((1 + fwd).prod()), 2)}
    res['verdict'] = verdict(res)
    return res


def verdict(r):
    """قبول: آزمون خارج از نمونه سودده، شارپ ≥ ۰٫۵، حداقل ۲۰ معامله، و یا شارپ بهتر از نگه‌داشتن ساده
    یا ریزش دست‌کم ۳۰٪ کمتر با دست‌کم ۷۰٪ بازده آن."""
    o, b = r['out_sample'], r['buyhold_out_sample']
    if r['trades'] < 20:
        return 'رد: معامله‌ی کافی نیست'
    if o['cagr'] <= 0:
        return 'رد: در آزمون خارج از نمونه زیان‌ده'
    if o['sharpe'] < 0.5:
        return 'رد: بازده نسبت به ریسک ضعیف'
    beats = o['sharpe'] > b['sharpe'] or (o['max_dd'] > b['max_dd'] * 0.7 and o['cagr'] >= 0.7 * b['cagr'])
    return 'قبول' if beats else 'رد: بهتر از نگه‌داشتن ساده نیست'
