"""
Do stop-loss / target rules help? Same 2-year history and same entries as backtest.py.

Entry: close of the day after the signal. The position is followed for up to 60 trading days.
  * stop   = entry - k * U   (checked on daily closes; exit at that day's close)
  * target = entry + k * U
  * U      = "typical daily move": 14-day Wilder average of |close-to-close change| known on the signal day
  * if neither is hit, exit at the close of day 60
Every rule is also applied to a large random sample of entries (any stock, any day, same market), and
"Exc" is the signal's average minus that random-entry average under the SAME rule.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

import backtest as bt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(HERE, "backtest_stops.json")
RESULT_CSV = os.path.join(HERE, "backtest_stops.csv")
HOLD = 60
SAMPLE = 30000
CONFIGS = [("Hold60", None, None), ("Stop3", 3, None), ("Stop5", 5, None), ("Stop8", 8, None),
           ("S3/T6", 3, 6), ("S5/T10", 5, 10), ("S8/T15", 8, 15)]
GROUPS = ["D-BUY", "D-BUY+W", "CANSLIM*"]


def simulate(P, p0, u, ks, kt):
    """P: (n, HOLD) closes after entry. Returns (return %, holding days, reason 0=time 1=stop 2=target)."""
    n = P.shape[0]
    big = HOLD + 1
    first_stop = np.full(n, big)
    first_tgt = np.full(n, big)
    if ks is not None:
        hit = P <= (p0 - ks * u)[:, None]
        first_stop = np.where(hit.any(axis=1), hit.argmax(axis=1), big)
    if kt is not None:
        hit = P >= (p0 + kt * u)[:, None]
        first_tgt = np.where(hit.any(axis=1), hit.argmax(axis=1), big)
    use_stop = (first_stop <= first_tgt) & (first_stop < big)   # a tie counts as the stop (conservative)
    use_tgt = (first_tgt < first_stop) & (first_tgt < big)
    day = np.where(use_stop, first_stop, np.where(use_tgt, first_tgt, HOLD - 1))
    reason = np.where(use_stop, 1, np.where(use_tgt, 2, 0))
    exit_px = P[np.arange(n), day]
    return (exit_px / p0 - 1) * 100, day + 1, reason


def paths(C, U, ii, jj):
    e = ii + 1
    p0 = C[e, jj]
    u = U[ii, jj]
    rows = e[:, None] + 1 + np.arange(HOLD)[None, :]
    P = C[rows, jj[:, None]]
    good = np.isfinite(P).all(axis=1) & np.isfinite(p0) & (p0 > 0) & np.isfinite(u) & (u > 0)
    return P[good], p0[good], u[good]


def collect_market(close, idx_close, rng):
    C = close.values
    n = C.shape[0]
    start = close.index.max() - pd.DateOffset(years=bt.YEARS)
    ok_rows = np.asarray(close.index >= start) & (np.arange(n) <= n - HOLD - 2)

    hist, rsi = bt.indicators(close)
    B, _ = bt.events(hist, rsi)
    B = B.values
    wk = close.resample("W-FRI").last().dropna(how="all")
    whist, wrsi = bt.indicators(wk)
    wbull = (whist > 0).astype(float).reindex(close.index, method="ffill").fillna(0).values > 0.5
    U = close.diff().abs().ewm(alpha=1 / 14, adjust=False).mean().values

    sigs = {"D-BUY": B, "D-BUY+W": B & wbull}
    if idx_close is not None and len(idx_close) > 220:
        sma50, sma200 = idx_close.rolling(50).mean(), idx_close.rolling(200).mean()
        up = ((idx_close > sma50) & (sma50 > sma200)).astype(float)
        mu = (up.reindex(close.index, method="ffill").fillna(0).values > 0.5)[:, None]
        near = (close >= 0.85 * close.rolling(252, min_periods=200).max()).values
        rs = (close / close.shift(126) - 1).rank(axis=1, pct=True).values * 100
        sigs["CANSLIM*"] = B & near & (rs >= 80) & mu

    data = {}
    for name, mask in sigs.items():
        ii, jj = np.nonzero(mask & ok_rows[:, None])
        data[name] = paths(C, U, ii, jj)
    # random entries: any stock, any day
    ii, jj = np.nonzero(np.isfinite(C) & np.isfinite(U) & (U > 0) & ok_rows[:, None])
    if len(ii) > SAMPLE:
        pick = rng.choice(len(ii), SAMPLE, replace=False)
        ii, jj = ii[pick], jj[pick]
    data["random"] = paths(C, U, ii, jj)
    return data


def f(v, fmt="{:+.1f}"):
    return "-" if v is None or v != v else fmt.format(v)


def run(request_id, uni, download_all, short, pre, send):
    today = dt.date.today().strftime("%Y-%m-%d")
    rng = np.random.default_rng(7)
    markets = [m for m in ("US", "JP", "IN", "TW", "CN", "CM", "FX") if uni.get(m)]
    idx_data = download_all(list(bt.INDEX.values()), period="5y")
    per_market = {}
    for m in markets:
        close = bt.build_frame(download_all(uni[m], period="5y"))
        if close.shape[1] < 3 or len(close) < 500:
            continue
        idx_close = None
        if m in bt.INDEX and bt.INDEX[m] in idx_data:
            s = idx_data[bt.INDEX[m]].copy()
            ix = pd.to_datetime(s.index)
            s.index = (ix.tz_localize(None) if getattr(ix, "tz", None) else ix).normalize()
            idx_close = s[~s.index.duplicated(keep="last")].astype(float)
        per_market[m] = collect_market(close, idx_close, rng)
        print(f"stops: {m}: " + ", ".join(f"{k}={len(v[1])}" for k, v in per_market[m].items()))
    if not per_market:
        send(["⚠️ آزمون حد ضرر انجام نشد: داده‌ی تاریخی دریافت نشد."], b"", "stops")
        return False

    rows = []
    for g in GROUPS:
        for cname, ks, kt in CONFIGS:
            rets, excs, days, reasons = [], [], [], []
            for m, d in per_market.items():
                if g not in d or len(d[g][1]) == 0 or len(d["random"][1]) == 0:
                    continue
                rb, _, _ = simulate(*d["random"], ks, kt)
                r, dd, rs = simulate(*d[g], ks, kt)
                rets.append(r)
                excs.append(r - rb.mean())
                days.append(dd)
                reasons.append(rs)
            if not rets:
                continue
            r, e, dd, rs = map(np.concatenate, (rets, excs, days, reasons))
            k = max(1, int(len(r) * 0.05))
            rows.append({"group": g, "rule": cname, "n": int(len(r)), "avg": float(r.mean()),
                         "median": float(np.median(r)), "win": float((r > 0).mean() * 100),
                         "std": float(r.std()), "worst5": float(np.sort(r)[:k].mean()),
                         "days": float(dd.mean()), "stop_pct": float((rs == 1).mean() * 100),
                         "tgt_pct": float((rs == 2).mean() * 100), "exc": float(e.mean())})
    json.dump({"request": request_id, "date": today, "rows": rows}, open(RESULT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    pd.DataFrame(rows).to_csv(RESULT_CSV, index=False)

    get = lambda g, rule: next((x for x in rows if x["group"] == g and x["rule"] == rule), None)

    def t_return(g):
        t = [f"{'Rule':<8}{'Avg%':>6}{'Win%':>5}{'Exc%':>6}{'Days':>5}", "-" * 30]
        for cname, _, _ in CONFIGS:
            r = get(g, cname)
            if r:
                t.append(f"{cname:<8}{f(r['avg']):>6}{r['win']:>5.0f}{f(r['exc']):>6}{r['days']:>5.0f}")
        return pre(t)

    def t_risk(g):
        t = [f"{'Rule':<8}{'Std':>6}{'Worst5':>8}{'Stop%':>6}{'Tgt%':>6}", "-" * 34]
        for cname, _, _ in CONFIGS:
            r = get(g, cname)
            if r:
                t.append(f"{cname:<8}{r['std']:>6.1f}{f(r['worst5']):>8}{r['stop_pct']:>6.0f}{r['tgt_pct']:>6.0f}")
        return pre(t)

    n_main = get("D-BUY", "Hold60")["n"] if get("D-BUY", "Hold60") else 0
    blocks = [
        f"🛡 <b>آزمون حد ضرر و هدف قیمت</b> — {today}\n"
        f"<i>همان سیگنال‌های خرید دو سال گذشته (جمعاً {n_main:,} خرید روزانه) را تا ۶۰ روز دنبال کردیم، یک بار بدون هیچ قاعده‌ی خروج "
        "و بار دیگر با حد ضرر و هدف. فاصله‌ی حد ضرر و هدف بر اساس «نوسان معمول روزانه» همان سهم تنظیم شد "
        "(میانگین ۱۴ روزه‌ی تغییر قیمت پایانی؛ مثلاً Stop5 یعنی ۵ برابر این نوسان زیر قیمت خرید). "
        "خروج با قیمت پایانیِ روزی است که حد ضرر یا هدف رد شود.\n"
        "Avg% = میانگین بازده · Win% = درصد سودده · Exc% = برتری نسبت به خرید تصادفی با همان قاعده · "
        "Days = میانگین روز نگه‌داری · Std = پراکندگی بازده (هرچه کمتر، آرام‌تر) · "
        "Worst5 = میانگین بازده بدترین ۵٪ موارد · Stop%/Tgt% = درصد مواردی که با حد ضرر/هدف بسته شدند.</i>",
        "📊 <b>خرید روزانه — بازده</b>\n" + t_return("D-BUY"),
        "📊 <b>خرید روزانه — ریسک</b>\n" + t_risk("D-BUY"),
        "📊 <b>خرید روزانه هم‌جهت با روند هفتگی</b>\n" + t_return("D-BUY+W"),
        "📊 <b>فیلتر قیمتیِ CANSLIM</b>\n" + t_return("CANSLIM*"),
    ]
    h = get("D-BUY", "Hold60")
    lines = ["🧾 <b>نتیجه به زبان ساده</b>"]
    if h:
        lines.append(f"• بدون حد ضرر (نگه‌داری ۶۰ روزه): میانگین {f(h['avg'])}٪ و بدترین ۵٪ موارد به‌طور میانگین {f(h['worst5'])}٪.")
        for cname in ("Stop5", "Stop8", "S5/T10"):
            r = get("D-BUY", cname)
            if r:
                lines.append(f"• {cname}: میانگین {f(r['avg'])}٪ ({f(r['avg'] - h['avg'])} نسبت به بدون حد ضرر)، "
                             f"بدترین ۵٪: {f(r['worst5'])}٪ ({f(r['worst5'] - h['worst5'])})، "
                             f"{r['stop_pct']:.0f}٪ موارد با حد ضرر بسته شدند.")
    blocks.append("\n".join(lines))
    blocks.append("<i>محدودیت‌ها مثل بک‌تست قبلی: فقط دو سال، فهرست شرکت‌های امروز، بدون کارمزد؛ "
                  "و چون خروج با قیمت پایانی بررسی می‌شود، در افت‌های ناگهانی قیمت خروج می‌تواند پایین‌تر از حد ضرر باشد. "
                  "این نتیجه توصیه‌ی خرید یا فروش نیست.</i>")
    send(blocks, b"", "stops")
    return True
