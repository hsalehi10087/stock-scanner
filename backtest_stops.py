"""
Does a stop-loss / profit target help? Tested on the same 2-year history as backtest.py.

Each buy signal is followed for up to 60 trading days (entry = close of the day after the signal).
The stop and the target are measured in "ATR" units (ATR = 14-day average of the absolute daily
price change, from closing prices). A position is closed on the first day the CLOSE crosses the
stop or the target (so gaps are charged in full); otherwise it is closed at day 60.
The same rules are applied to random entries (every 7th day of every stock) to see what a rule
does by itself, without any signal.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(HERE, "backtest_stops.json")
H = 60
RULES = [("Hold60", None, None), ("S2/T3", 2, 3), ("S2/T4", 2, 4), ("S3/T6", 3, 6), ("S2 only", 2, None)]
SETS = ["D-BUY", "D-BUY+W", "CANSLIM*", "Random"]


def simulate(close_v, atr_v, mask, win, step=1):
    """Returns {rule: array of % results} for all events in `mask` (inside the window)."""
    n = close_v.shape[0]
    ii, jj = np.nonzero(mask & win[:, None])
    keep = ii + 1 + H < n
    if step > 1:
        keep &= (ii % step == 0)
    ii, jj = ii[keep], jj[keep]
    if ii.size == 0:
        return {name: np.array([]) for name, _, _ in RULES}
    entry = close_v[ii + 1, jj]
    atr = atr_v[ii, jj]
    rows = ii[:, None] + 1 + np.arange(1, H + 1)[None, :]
    path = close_v[rows, jj[:, None]] / entry[:, None] - 1
    good = np.isfinite(entry) & (entry > 0) & np.isfinite(atr) & (atr > 0) & ~np.isnan(path).any(axis=1)
    path, atr, entry = path[good], atr[good], entry[good]
    unit = atr / entry                      # one ATR as a fraction of the entry price
    last = path[:, -1]
    out = {}
    for name, ks, kt in RULES:
        res = last.copy()
        if ks or kt:
            st = np.full(len(path), H)
            tt = np.full(len(path), H)
            if ks:
                hit = path <= (-ks * unit)[:, None]
                st = np.where(hit.any(axis=1), hit.argmax(axis=1), H)
            if kt:
                hit = path >= (kt * unit)[:, None]
                tt = np.where(hit.any(axis=1), hit.argmax(axis=1), H)
            first = np.minimum(st, tt)
            exit_ret = path[np.arange(len(path)), np.minimum(first, H - 1)]
            res = np.where(first < H, exit_ret, last)
        out[name] = res * 100
    return out


def collect(m, close, idx_close, acc, bt):
    """Run the experiment for one market and append the arrays to acc[set][rule]."""
    start = close.index.max() - pd.DateOffset(years=bt.YEARS)
    win = np.asarray(close.index >= start)
    hist, rsi = bt.indicators(close)
    buy_ev, _ = bt.events(hist, rsi)
    wk = close.resample("W-FRI").last().dropna(how="all")
    whist, _ = bt.indicators(wk)
    wbull = (whist > 0).astype(float).reindex(close.index, method="ffill").fillna(0).values > 0.5
    B = buy_ev.values
    atr = close.diff().abs().ewm(alpha=1 / 14, adjust=False).mean().values
    cv = close.values
    sets = {"D-BUY": B, "D-BUY+W": B & wbull, "Random": np.ones_like(B)}
    if idx_close is not None and len(idx_close) > 220:
        sma50, sma200 = idx_close.rolling(50).mean(), idx_close.rolling(200).mean()
        up = ((idx_close > sma50) & (sma50 > sma200)).astype(float)
        mu = (up.reindex(close.index, method="ffill").fillna(0).values > 0.5)[:, None]
        near = (close >= 0.85 * close.rolling(252, min_periods=200).max()).values
        rs = (close / close.shift(126) - 1).rank(axis=1, pct=True).values * 100
        sets["CANSLIM*"] = B & near & (rs >= 80) & mu
    for name, mask in sets.items():
        res = simulate(cv, atr, mask, win, step=7 if name == "Random" else 1)
        for rule, arr in res.items():
            acc.setdefault(name, {}).setdefault(rule, []).append(arr)


def f(v, fmt="{:+.1f}"):
    return "-" if v is None or v != v else fmt.format(v)


def report(acc, pre):
    """Returns (summary_rows, telegram_blocks)."""
    rows = []
    for name in SETS:
        if name not in acc:
            continue
        hold = np.concatenate(acc[name]["Hold60"]) if acc[name]["Hold60"] else np.array([])
        for rule, _, _ in RULES:
            arr = np.concatenate(acc[name][rule]) if acc[name][rule] else np.array([])
            if arr.size == 0:
                continue
            rows.append({"set": name, "rule": rule, "n": int(arr.size), "win": float((arr > 0).mean() * 100),
                         "avg": float(arr.mean()), "median": float(np.median(arr)),
                         "p5": float(np.percentile(arr, 5)), "worst": float(arr.min()),
                         "d_avg_vs_hold": float(arr.mean() - hold.mean()) if hold.size == arr.size else None})
    get = lambda s, r: next((x for x in rows if x["set"] == s and x["rule"] == r), None)

    def table(name):
        t = [f"{'Rule':<9}{'N':>6}{'Win%':>5}{'Avg%':>6}{'P5%':>6}{'Worst':>7}", "-" * 39]
        for rule, _, _ in RULES:
            r = get(name, rule)
            if r:
                t.append(f"{rule:<9}{r['n']:>6,}{r['win']:>5.0f}{f(r['avg']):>6}{f(r['p5'], '{:.0f}'):>6}"
                         f"{f(r['worst'], '{:.0f}'):>7}")
        return pre(t)

    blocks = [
        f"🧪 <b>آزمون حد ضرر و هدف قیمتی</b> — {dt.date.today()}\n"
        "<i>روی همان دو سال تاریخچه، هر سیگنال خرید را تا ۶۰ روز دنبال کردیم. «ATR» اندازه‌ی نوسان معمول روزانه‌ی هر سهم است. "
        "S2/T3 یعنی خروج اگر قیمت پایانی ۲ ATR پایین‌تر از خرید بسته شود (حد ضرر) یا ۳ ATR بالاتر (هدف)؛ "
        "Hold60 یعنی نگه‌داشتن کامل ۶۰ روز بدون حد؛ «S2 only» فقط حد ضرر. "
        "Win% = درصد سودده · Avg% = میانگین · P5% = ضعیف‌ترین ۵٪ نتیجه‌ها (بدترین حالت‌های معمول) · Worst = بدترین مورد.</i>"]
    for name, label in (("D-BUY", "خرید روزانه"), ("D-BUY+W", "خرید روزانه + روند هفتگی"),
                        ("CANSLIM*", "فیلتر قیمتی CANSLIM"), ("Random", "ورود تصادفی (برای مقایسه)")):
        if get(name, "Hold60"):
            blocks.append(f"<b>{label}</b>\n" + table(name))

    # plain-language reading
    lines = ["🧾 <b>نتیجه به زبان ساده</b>"]
    h, s = get("D-BUY", "Hold60"), get("D-BUY", "S2 only")
    s23 = get("D-BUY", "S2/T3")
    if h and s:
        lines.append(f"• حد ضرر ۲ ATR، بدترین ۵٪ نتیجه‌ها را از {f(h['p5'], '{:.0f}')}٪ به {f(s['p5'], '{:.0f}')}٪ رساند "
                     f"و بدترین مورد را از {f(h['worst'], '{:.0f}')}٪ به {f(s['worst'], '{:.0f}')}٪. "
                     f"هزینه‌اش: میانگین بازده از {f(h['avg'])}٪ به {f(s['avg'])}٪ تغییر کرد.")
    if h and s23:
        lines.append(f"• حد ضرر و هدف هم‌زمان (S2/T3): میانگین {f(s23['avg'])}٪ و ضعیف‌ترین ۵٪ برابر {f(s23['p5'], '{:.0f}')}٪.")
    rh, rs_ = get("Random", "Hold60"), get("Random", "S2 only")
    if rh and rs_ and h and s:
        lines.append(f"• برای مقایسه، همین حد ضرر روی ورود تصادفی میانگین را از {f(rh['avg'])}٪ به {f(rs_['avg'])}٪ برد؛ "
                     f"یعنی اثر آن بیشتر کنترل ریسک است تا ساختن سود اضافه.")
    blocks.append("\n".join(lines))
    blocks.append("<i>قیمت‌ها بر پایه‌ی قیمت پایانی‌اند؛ کارمزد و لغزش حساب نشده است. این نتیجه توصیه‌ی خرید یا فروش نیست.</i>")
    return rows, blocks


def save(rows, request_id):
    json.dump({"request": request_id, "date": str(dt.date.today()), "rows": rows},
              open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
