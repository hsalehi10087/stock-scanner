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
RESULT = os.path.join(HERE, "backtest_atr.json")
H = 60
RULES = [("Hold60", None, None), ("S2 only", 2, None), ("S3 only", 3, None), ("S5 only", 5, None), ("S3/T6", 3, 6)]
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
        f"🧪 <b>آزمون حد ضرر بر اساس نوسان هر سهم (ATR)</b> — {dt.date.today()}\n"
        "<i>روی همان دو سال تاریخچه، هر سیگنال خرید را تا ۶۰ روز دنبال کردیم. «ATR» اندازه‌ی نوسان معمول روزانه‌ی هر سهم است. "
        "S3 only یعنی خروج اگر قیمت پایانی ۳ ATR پایین‌تر از خرید بسته شود (فقط حد ضرر)؛ S3/T6 یعنی حد ضرر ۳ ATR و هدف ۶ ATR؛ "
        "Hold60 یعنی نگه‌داشتن کامل ۶۰ روز بدون هیچ حدی. "
        "Win% = درصد سودده · Avg% = میانگین · P5% = ضعیف‌ترین ۵٪ نتیجه‌ها (بدترین حالت‌های معمول) · Worst = بدترین مورد.</i>"]
    for name, label in (("D-BUY", "خرید روزانه"), ("D-BUY+W", "خرید روزانه + روند هفتگی"),
                        ("CANSLIM*", "فیلتر قیمتی CANSLIM"), ("Random", "ورود تصادفی (برای مقایسه)")):
        if get(name, "Hold60"):
            blocks.append(f"<b>{label}</b>\n" + table(name))

    # plain-language reading
    lines = ["🧾 <b>نتیجه به زبان ساده</b>"]
    h = get("D-BUY", "Hold60")
    for rule, label in (("S2 only", "۲"), ("S3 only", "۳"), ("S5 only", "۵")):
        r = get("D-BUY", rule)
        if h and r:
            lines.append(f"• حد ضرر {label} ATR: بدترین ۵٪ نتیجه‌ها از {f(h['p5'], '{:.0f}')}٪ به {f(r['p5'], '{:.0f}')}٪ رسید "
                         f"(بدترین مورد: {f(h['worst'], '{:.0f}')}٪ به {f(r['worst'], '{:.0f}')}٪)؛ میانگین بازده از {f(h['avg'])}٪ به {f(r['avg'])}٪ تغییر کرد.")
    t = get("D-BUY", "S3/T6")
    if h and t:
        lines.append(f"• با هدف قیمتی ۶ ATR هم: میانگین فقط {f(t['avg'])}٪ شد؛ هدف قیمتی سودهای بزرگ را زود قطع می‌کند.")
    rh, rr = get("Random", "Hold60"), get("Random", "S3 only")
    if rh and rr:
        lines.append(f"• برای مقایسه، همین حد ضرر ۳ ATR روی ورود تصادفی میانگین را از {f(rh['avg'])}٪ به {f(rr['avg'])}٪ برد؛ "
                     "یعنی حد ضرر بیشتر کنترل ریسک است تا ساختن سود اضافه.")
    blocks.append("\n".join(lines))
    blocks.append("<i>قیمت‌ها بر پایه‌ی قیمت پایانی‌اند؛ کارمزد و لغزش حساب نشده است. این نتیجه توصیه‌ی خرید یا فروش نیست.</i>")
    return rows, blocks


def save(rows, request_id):
    json.dump({"request": request_id, "date": str(dt.date.today()), "rows": rows},
              open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


def run(request_id, uni, download_all, short, pre, send):
    """Stand-alone runner (request kind 'atr'): downloads 5y history and runs the ATR stop experiment."""
    import backtest as bt
    markets = [m for m in ("US", "JP", "IN", "TW", "CN", "CM", "FX") if uni.get(m)]
    idx_data = download_all(list(bt.INDEX.values()), period="5y")
    acc = {}
    for m in markets:
        close = bt.build_frame(download_all(uni[m], period="5y"))
        if close.shape[1] < 3 or len(close) < 500:
            print(f"atr experiment: {m}: not enough data ({close.shape})")
            continue
        idx_close = None
        if m in bt.INDEX and bt.INDEX[m] in idx_data:
            x = idx_data[bt.INDEX[m]].copy()
            xi = pd.to_datetime(x.index)
            if getattr(xi, "tz", None) is not None:
                xi = xi.tz_localize(None)
            x.index = xi.normalize()
            idx_close = x[~x.index.duplicated(keep="last")].astype(float)
        collect(m, close, idx_close, acc, bt)
        print(f"atr experiment: {m}: done ({close.shape[1]} symbols)")
    if not acc:
        send(["⚠️ آزمون حد ضرر انجام نشد: داده‌ی تاریخی دریافت نشد."], b"", "backtest")
        return False
    rows, blocks = report(acc, pre)
    save(rows, request_id)
    send(blocks, b"", "backtest")
    return True
