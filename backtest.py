"""
Two-year backtest of the scanner's signals (MACD/RSI daily and weekly, plus the price-based
parts of CANSLIM). Runs once when backtest_request.txt has a new id; results go to Telegram and
backtest_results.json / backtest_results.csv.

How it is measured (kept simple and conservative):
  * a signal is seen after the close of day t; the buy is assumed at the close of day t+1
  * return = price change 5 / 20 / 60 trading days after that entry (no costs, no dividends)
  * "Exc" = signal return minus the average return of ALL stocks of the same market over the same
    horizon in the same 2-year window (what you would get picking a random stock on a random day)
  * "t" = significance of Exc, computed with one average per calendar month (so that signals bunched
    on the same days are not counted as independent) and shrunk for overlapping horizons.
    |t| >= 2.5 means "probably not luck" (stricter than 2 because many tests are run at once).
Not tested (no point-in-time data is available for free): the earnings-based parts of CANSLIM
(C, A, I) and the whole Buffett scorecard.
"""
import datetime as dt
import html as _html
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(HERE, "backtest_results.json")
RESULT_CSV = os.path.join(HERE, "backtest_results.csv")
HORIZONS = (5, 20, 60)
YEARS = 2
INDEX = {"US": "^GSPC", "JP": "^N225", "IN": "^NSEI", "TW": "^TWII", "CN": "000300.SS"}
SIGNALS = ["D-BUY", "D-BUY+W", "W-BUY", "CANSLIM*", "BUY+N+L", "BUY Mup", "BUY Mdn", "D-SELL", "W-SELL"]


def build_frame(series_dict):
    cols = {}
    for t, s in series_dict.items():
        s = s.copy()
        idx = pd.to_datetime(s.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        s.index = idx.normalize()
        s = s[~s.index.duplicated(keep="last")]
        cols[t] = s.astype(float)
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index().ffill(limit=3)


def indicators(close):
    """MACD histogram and Wilder RSI for every column at once (same formulas as the live scanner)."""
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    d = close.diff()
    ag = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    al = (-d).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + ag / al)
    rsi = rsi.where(al > 0, 100.0)
    rsi = rsi.where(ag.notna() & al.notna())
    return hist, rsi


def events(hist, rsi):
    """First day of each new BUY / SELL signal (same rules as the live classify())."""
    bull = hist > 0
    prev = hist.shift(1)
    cross_up = bull & (prev <= 0)
    cross_dn = (hist < 0) & (prev >= 0)
    buy = (cross_up & (rsi < 70)) | (bull & (rsi < 30))
    sell = ~buy & (cross_dn | ((rsi > 70) & ~bull)) & rsi.notna()
    buy_ev = buy & ~buy.shift(1, fill_value=False)
    sell_ev = sell & ~sell.shift(1, fill_value=False)
    return buy_ev.fillna(False), sell_ev.fillna(False)


def weekly_to_daily(ev_w, wk_index, day_index):
    """Place weekly events on the last trading day on or before the weekly bar's date."""
    pos = day_index.searchsorted(wk_index, side="right") - 1
    ok = pos >= 0
    arr = np.zeros((len(day_index), ev_w.shape[1]), dtype=bool)
    np.logical_or.at(arr, pos[ok], ev_w.values[ok])
    return arr


def analyse_market(m, close, idx_close):
    """Returns ({signal: {h: (values, month_ids)}}, {h: (n, mean, win)}) for one market."""
    start = close.index.max() - pd.DateOffset(years=YEARS)
    win = np.asarray(close.index >= start)

    hist, rsi = indicators(close)
    buy_ev, sell_ev = events(hist, rsi)
    wk = close.resample("W-FRI").last().dropna(how="all")
    whist, wrsi = indicators(wk)
    wbuy, wsell = events(whist, wrsi)
    wbull = (whist > 0).astype(float).reindex(close.index, method="ffill").fillna(0).values > 0.5
    w_buy_d = weekly_to_daily(wbuy, wk.index, close.index)
    w_sell_d = weekly_to_daily(wsell, wk.index, close.index)

    B = buy_ev.values
    sigs = {"D-BUY": B, "D-BUY+W": B & wbull, "W-BUY": w_buy_d, "D-SELL": sell_ev.values, "W-SELL": w_sell_d}
    if idx_close is not None and len(idx_close) > 220:
        sma50, sma200 = idx_close.rolling(50).mean(), idx_close.rolling(200).mean()
        up = ((idx_close > sma50) & (sma50 > sma200)).astype(float)
        mu = (up.reindex(close.index, method="ffill").fillna(0).values > 0.5)[:, None]
        near = (close >= 0.85 * close.rolling(252, min_periods=200).max()).values
        rs = (close / close.shift(126) - 1).rank(axis=1, pct=True).values * 100
        L = rs >= 80
        sigs.update({"CANSLIM*": B & near & L & mu, "BUY+N+L": B & near & L,
                     "BUY Mup": B & mu, "BUY Mdn": B & ~mu})

    months = np.broadcast_to((close.index.year * 12 + close.index.month).values[:, None], close.shape)
    entry = close.shift(-1)
    out, base = {}, {}
    for h in HORIZONS:
        fwd = (close.shift(-1 - h) / entry - 1).values * 100
        valid = ~np.isnan(fwd) & win[:, None]
        v = fwd[valid]
        base[h] = (int(v.size), float(v.mean()) if v.size else float("nan"),
                   float((v > 0).mean() * 100) if v.size else float("nan"))
        for name, mask in sigs.items():
            sel = mask & valid
            out.setdefault(name, {})[h] = (fwd[sel], months[sel])
    return out, base


def aggregate(collected, bases):
    """Pool markets: excess is measured against each market's own baseline."""
    rows = []
    for name in SIGNALS:
        for h in HORIZONS:
            vals, exc_parts, months = [], [], []
            n_by_m = {}
            for m, (out, _) in collected.items():
                if name not in out:
                    continue
                v, mo = out[name][h]
                if v.size == 0:
                    continue
                b = bases[m][h][1]
                vals.append(v)
                exc_parts.append(v - b)
                months.append(mo)
                n_by_m[m] = (int(v.size), float((v - b).mean()))
            if not vals:
                continue
            v = np.concatenate(vals)
            e = np.concatenate(exc_parts)
            mo = np.concatenate(months)
            m_means = pd.Series(e).groupby(mo).mean()
            t = float("nan")
            if len(m_means) >= 6 and m_means.std(ddof=1) > 0:
                t = float(m_means.mean() / (m_means.std(ddof=1) / np.sqrt(len(m_means))))
                t /= np.sqrt(max(1.0, h / 21))  # neighbouring months share the same forward window
            rows.append({"signal": name, "h": h, "n": int(v.size), "win": float((v > 0).mean() * 100),
                         "avg": float(v.mean()), "median": float(np.median(v)), "exc": float(e.mean()),
                         "t": t, "by_market": n_by_m})
    # all-days baseline pooled over all markets
    for h in HORIZONS:
        n = sum(bases[m][h][0] for m in bases)
        avg = sum(bases[m][h][0] * bases[m][h][1] for m in bases if bases[m][h][0]) / max(n, 1)
        win = sum(bases[m][h][0] * bases[m][h][2] for m in bases if bases[m][h][0]) / max(n, 1)
        rows.append({"signal": "All days", "h": h, "n": int(n), "win": float(win), "avg": float(avg),
                     "median": float("nan"), "exc": 0.0, "t": float("nan"), "by_market": {}})
    return rows


def f(v, fmt="{:+.1f}"):
    return "-" if v is None or v != v else fmt.format(v)


def table(rows, h, pre):
    t = [f"{'Signal':<10}{'N':>6}{'Win%':>5}{'Avg%':>6}{'Exc%':>6}{'t':>5}", "-" * 38]
    for name in SIGNALS + ["All days"]:
        r = next((x for x in rows if x["signal"] == name and x["h"] == h), None)
        if r is None:
            continue
        n = f"{r['n']:,}" if r["n"] < 100000 else f"{r['n'] // 1000}k"
        t.append(f"{name:<10}{n:>6}{r['win']:>5.0f}{f(r['avg']):>6}{f(r['exc']) if name != 'All days' else '-':>6}"
                 f"{f(r['t'], '{:+.1f}') if name != 'All days' else '-':>5}")
    return pre(t)


def verdict(r):
    if r is None or r["n"] < 30:
        return "تعداد سیگنال برای قضاوت کافی نبود"
    if r["t"] != r["t"]:
        return "داده‌ی کافی برای سنجش اطمینان نبود"
    if r["exc"] > 0 and r["t"] >= 2.5:
        return "برتری روشن نسبت به بازار داشت ✅"
    if r["exc"] < 0 and r["t"] <= -2.5:
        return "ضعیف‌تر از بازار بود ⚠️"
    return "تفاوت روشنی با بازار نداشت (می‌تواند اتفاقی باشد)"


def run(request_id, uni, download_all, short, pre, send):
    today = dt.date.today().strftime("%Y-%m-%d")
    markets = [m for m in ("US", "JP", "IN", "TW", "CN", "CM", "FX") if uni.get(m)]
    print("backtest: downloading 5y history for", {m: len(uni[m]) for m in markets})
    idx_data = download_all(list(INDEX.values()), period="5y")
    collected, bases = {}, {}
    for m in markets:
        series = download_all(uni[m], period="5y")
        close = build_frame(series)
        if close.shape[1] < 3 or len(close) < 500:
            print(f"backtest: {m}: not enough data ({close.shape})")
            continue
        idx_close = None
        if m in INDEX and INDEX[m] in idx_data:
            s = idx_data[INDEX[m]].copy()
            s.index = pd.to_datetime(s.index).tz_localize(None).normalize() if getattr(s.index, "tz", None) \
                else pd.to_datetime(s.index).normalize()
            idx_close = s[~s.index.duplicated(keep="last")].astype(float)
        out, base = analyse_market(m, close, idx_close)
        collected[m] = (out, base)
        bases[m] = base
        print(f"backtest: {m}: {close.shape[1]} symbols, {base[20][0]:,} obs")
    if not collected:
        send(["⚠️ بک‌تست انجام نشد: داده‌ی تاریخی دریافت نشد."], b"", "backtest")
        return False

    rows = aggregate(collected, bases)
    json.dump({"request": request_id, "date": today, "years": YEARS, "rows": rows},
              open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    flat = [{k: v for k, v in r.items() if k != "by_market"} for r in rows]
    pd.DataFrame(flat).to_csv(RESULT_CSV, index=False)

    get = lambda name, h: next((x for x in rows if x["signal"] == name and x["h"] == h), None)
    blocks = [
        f"🔬 <b>بک‌تست دو ساله‌ی سیگنال‌ها</b> — {today}\n"
        "<i>همین قواعد را روی دو سال گذشته‌ی حدود ۱۳۰۰ نماد اجرا کردیم و دیدیم بعد از هر سیگنال قیمت چقدر تغییر کرده است. "
        "خرید در قیمت پایانی روز بعد از سیگنال فرض شده؛ کارمزد حساب نشده.\n"
        "N = تعداد سیگنال · Win% = درصد موارد سودده · Avg% = میانگین تغییر قیمت · "
        "Exc% = برتری نسبت به میانگین همه‌ی نمادهای همان بازار در همان بازه (یعنی نسبت به انتخاب تصادفی) · "
        "t = اطمینان آماری؛ عدد ۲٫۵ یا بیشتر (یا ۲٫۵- و کمتر) یعنی احتمالاً اتفاقی نیست.</i>",
        "<i>D-BUY خرید روزانه · D-BUY+W خرید روزانه هم‌جهت با روند هفتگی · W-BUY خرید هفتگی · "
        "CANSLIM* خرید + نزدیک سقف ۵۲ هفته + قدرت نسبی بالای ۸۰٪ + بازار صعودی · BUY+N+L همان بدون شرط بازار · "
        "BUY Mup/Mdn خرید وقتی بازار صعودی/غیرصعودی بود · SELL: تغییر قیمت بعد از سیگنال فروش "
        "(عدد منفی یعنی سیگنال درست بوده)</i>",
        "📅 <b>۲۰ روز معاملاتی بعد (حدود یک ماه)</b>\n" + table(rows, 20, pre),
        "📅 <b>۶۰ روز معاملاتی بعد (حدود سه ماه)</b>\n" + table(rows, 60, pre),
        "📅 <b>۵ روز معاملاتی بعد (یک هفته)</b>\n" + table(rows, 5, pre),
    ]

    # by-market table at 60 days
    mt = [f"{'Market':<8}{'N':>6}{'D-BUY':>7}{'+W':>7}{'CANSLIM':>8}", "-" * 36]
    for m in markets:
        if m not in collected:
            continue
        cells = []
        for name in ("D-BUY", "D-BUY+W", "CANSLIM*"):
            r = get(name, 60)
            nm, ex = (r["by_market"].get(m, (0, float("nan"))) if r else (0, float("nan")))
            cells.append((nm, ex))
        mt.append(f"{m:<8}{cells[0][0]:>6}{f(cells[0][1] if cells[0][0] >= 30 else None):>7}"
                  f"{f(cells[1][1] if cells[1][0] >= 30 else None):>7}{f(cells[2][1] if cells[2][0] >= 30 else None):>8}")
    blocks.append("🌍 <b>برتری ۶۰ روزه به تفکیک بازار (Exc%)</b>\n<i>«-» یعنی کمتر از ۳۰ سیگنال بود.</i>\n" + pre(mt))

    # plain-language reading
    fa = {"D-BUY": "خرید روزانه", "D-BUY+W": "خرید روزانه هم‌جهت با روند هفتگی", "W-BUY": "خرید هفتگی",
          "CANSLIM*": "فیلتر قیمتیِ CANSLIM"}
    lines = ["🧾 <b>نتیجه به زبان ساده (افق سه ماهه)</b>"]
    for name, label in fa.items():
        r = get(name, 60)
        if r:
            lines.append(f"• {label}: میانگین {f(r['avg'])}٪ در سه ماه بعد، یعنی {f(r['exc'])}٪ نسبت به بازار — {verdict(r)}")
    up, dn = get("BUY Mup", 60), get("BUY Mdn", 60)
    if up and dn:
        lines.append(f"• وقتی بازار صعودی بود، خریدها {f(up['exc'])}٪ نسبت به بازار داشتند و وقتی صعودی نبود {f(dn['exc'])}٪.")
    s = get("D-SELL", 60)
    if s:
        lines.append(f"• بعد از سیگنال فروش روزانه، قیمت‌ها در سه ماه به‌طور میانگین {f(s['avg'])}٪ تغییر کردند "
                     f"(بازار در کل {f(get('All days', 60)['avg'])}٪).")
    blocks.append("\n".join(lines))
    blocks.append(
        "⚠️ <b>محدودیت‌ها</b>\n"
        "• دو سال فقط یک «حال‌وهوای بازار» را نشان می‌دهد؛ ممکن است در دوره‌ی دیگر نتیجه فرق کند.\n"
        "• فهرست نمادها، شرکت‌های امروز هستند؛ شرکت‌هایی که در این دو سال حذف یا ورشکست شده‌اند در آزمون نیستند "
        "(این معمولاً نتیجه را کمی خوش‌بینانه می‌کند).\n"
        "• کارمزد، مالیات و لغزش قیمت حساب نشده است.\n"
        "• چون ده‌ها آزمون هم‌زمان انجام شده، یکی‌دو مورد با t حدود ۲ می‌تواند فقط شانس باشد. "
        "فقط نتیجه‌ای را جدی بگیرید که t بالای ۲٫۵ دارد یا در چند افق زمانی هم‌جهت است.\n"
        "• بخش‌های مبتنی بر گزارش مالی (C، A و I در CANSLIM و کل جدول بافت) را نمی‌شود درست آزمود، چون داده‌ی مالیِ آن روزها "
        "به‌صورت رایگان در دسترس نیست.\n"
        "<i>این نتیجه توصیه‌ی خرید یا فروش نیست.</i>")
    send(blocks, b"", "backtest")
    return True


# ---------------------------------------------------------------------------
# Stop-loss / target experiment (request ids that start with "stops")
# ---------------------------------------------------------------------------
STOPS_RESULT = os.path.join(HERE, "backtest_stops.json")
STOPS_CSV = os.path.join(HERE, "backtest_stops.csv")
T_DAYS = 60
RULES = [  # name, stop (x ATR), target (x ATR), trailing, max days
    ("Hold60", None, None, False, 60),
    ("Exit20", None, None, False, 20),
    ("S2", 2, None, False, 60),
    ("S3", 3, None, False, 60),
    ("S2/T4", 2, 4, False, 60),
    ("S3/T6", 3, 6, False, 60),
    ("S2/T6", 2, 6, False, 60),
    ("Trail3", 3, None, True, 60),
]


def simulate(paths, atrp, rule):
    """paths: (n, T) returns (fraction) on days 1..T after entry. Exits on the first CLOSE that crosses a level."""
    name, ks, kt, trailing, maxd = rule
    n, T = paths.shape
    T = min(T, maxd)
    p = paths[:, :T]
    big = T + 5
    stop_day = np.full(n, big)
    tgt_day = np.full(n, big)
    if ks is not None:
        s = (ks * atrp)[:, None]
        if trailing:
            price = 1 + p
            cond = price <= np.maximum.accumulate(price, axis=1) * (1 - s)
        else:
            cond = p <= -s
        stop_day = np.where(cond.any(1), cond.argmax(1), big)
    if kt is not None:
        cond = p >= (kt * atrp)[:, None]
        tgt_day = np.where(cond.any(1), cond.argmax(1), big)
    exit_day = np.minimum(np.minimum(stop_day, tgt_day), T - 1)
    ret = p[np.arange(n), exit_day] * 100
    stopped = (stop_day <= tgt_day) & (stop_day < big)
    hit_t = (tgt_day < stop_day) & (tgt_day < big)
    return ret, stopped, hit_t, exit_day + 1


def collect_events(close, idx_close_unused=None):
    """Event paths for D-BUY and D-BUY+W (inside the 2-year window) and for random entries every 10th day."""
    start = close.index.max() - pd.DateOffset(years=YEARS)
    nrow = len(close)
    hist, rsi = indicators(close)
    buy_ev, _ = events(hist, rsi)
    wk = close.resample("W-FRI").last().dropna(how="all")
    whist, _ = indicators(wk)
    wbull = (whist > 0).astype(float).reindex(close.index, method="ffill").fillna(0).values > 0.5
    atr = (close.diff().abs().rolling(14).mean() / close).values
    arr = close.values
    in_win = np.asarray(close.index >= start)
    rows_ok = in_win & (np.arange(nrow) + 2 + T_DAYS <= nrow - 1)
    B = buy_ev.values
    rand = np.zeros_like(B)
    rand[::10, :] = True
    groups = {"D-BUY": B, "D-BUY+W": B & wbull, "Random": rand}
    months = (close.index.year * 12 + close.index.month).values
    out = {}
    for g, mask in groups.items():
        r, c = np.where(mask & rows_ok[:, None])
        if r.size == 0:
            continue
        entry = arr[r + 1, c]
        idx = r[:, None] + 2 + np.arange(T_DAYS)[None, :]
        paths = arr[idx, c[:, None]] / entry[:, None] - 1
        a = atr[r, c]
        ok = np.isfinite(paths).all(1) & np.isfinite(a) & (a > 0) & np.isfinite(entry) & (entry > 0)
        out[g] = (paths[ok], a[ok], months[r][ok])
    return out


def run_stops(request_id, uni, download_all, short, pre, send):
    today = dt.date.today().strftime("%Y-%m-%d")
    markets = [m for m in ("US", "JP", "IN", "TW", "CN", "CM", "FX") if uni.get(m)]
    pooled = {}
    for m in markets:
        close = build_frame(download_all(uni[m], period="5y"))
        if close.shape[1] < 3 or len(close) < 500:
            continue
        for g, (paths, a, mo) in collect_events(close).items():
            cur = pooled.setdefault(g, [[], [], []])
            cur[0].append(paths)
            cur[1].append(a)
            cur[2].append(mo)
        print(f"stops: {m}: done")
    rows = []
    for g, (P, A, M) in pooled.items():
        paths, atrp, mo = np.vstack(P), np.concatenate(A), np.concatenate(M)
        hold, *_ = simulate(paths, atrp, RULES[0])
        for rule in RULES:
            ret, stopped, hit_t, days = simulate(paths, atrp, rule)
            d = ret - hold
            mm = pd.Series(d).groupby(mo).mean()
            t = float("nan")
            if rule[0] != "Hold60" and len(mm) >= 6 and mm.std(ddof=1) > 0:
                t = float(mm.mean() / (mm.std(ddof=1) / np.sqrt(len(mm)))) / np.sqrt(60 / 21)
            wins, losses = ret[ret > 0], ret[ret <= 0]
            rows.append({"group": g, "rule": rule[0], "n": int(ret.size), "avg": float(ret.mean()),
                         "win": float((ret > 0).mean() * 100), "avg_win": float(wins.mean()) if wins.size else float("nan"),
                         "avg_loss": float(losses.mean()) if losses.size else float("nan"),
                         "p5": float(np.percentile(ret, 5)), "p1": float(np.percentile(ret, 1)),
                         "stopped": float(stopped.mean() * 100), "target": float(hit_t.mean() * 100),
                         "days": float(days.mean()), "d_vs_hold": float(d.mean()), "t": t,
                         "atr_med": float(np.median(atrp) * 100)})
    if not rows:
        send(["⚠️ آزمون حد ضرر انجام نشد: داده‌ی تاریخی دریافت نشد."], b"", "stops")
        return False
    json.dump({"request": request_id, "date": today, "rows": rows}, open(STOPS_RESULT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=float)
    pd.DataFrame(rows).to_csv(STOPS_CSV, index=False)

    def tbl(g):
        t = [f"{'Rule':<8}{'Avg%':>6}{'Win%':>5}{'P5%':>6}{'Stop%':>6}{'Δ%':>6}{'t':>5}", "-" * 42]
        for r in [x for x in rows if x["group"] == g]:
            t.append(f"{r['rule']:<8}{f(r['avg']):>6}{r['win']:>5.0f}{f(r['p5']):>6}{r['stopped']:>6.0f}"
                     f"{f(r['d_vs_hold']) if r['rule'] != 'Hold60' else '-':>6}"
                     f"{f(r['t'], '{:+.1f}') if r['rule'] != 'Hold60' else '-':>5}")
        return pre(t)

    blocks = [
        f"🛑 <b>آزمون حد ضرر و هدف قیمت</b> — {today}\n"
        "<i>برای همان سیگنال‌های دو سال گذشته، چند قاعده‌ی خروج را امتحان کردیم. هر معامله حداکثر ۶۰ روز نگه داشته می‌شود. "
        "ATR یعنی میانگین نوسان روزانه‌ی همان سهم در ۱۴ روز قبل از سیگنال؛ فاصله‌ی حد ضرر و هدف بر اساس آن تعیین می‌شود. "
        "خروج در اولین قیمت پایانی است که از سطح عبور کند (پس ریزش ناگهانی هم حساب شده).\n"
        "Hold60 = بدون قاعده، ۶۰ روز نگه داشتن · Exit20 = خروج روز بیستم · "
        "S2/S3 = حد ضرر ۲ یا ۳ برابر ATR · T4/T6 = هدف ۴ یا ۶ برابر ATR · Trail3 = حد ضرر متحرک ۳ برابر ATR از بالاترین قیمت.\n"
        "Avg% = میانگین بازده هر معامله · Win% = درصد سودده · P5% = بازده بدترین ۵٪ معاملات · "
        "Stop% = درصد معاملاتی که با حد ضرر بسته شدند · Δ% = تفاوت میانگین با Hold60 روی همان معامله‌ها · "
        "t = اطمینان آماری این تفاوت.</i>",
        "🟢 <b>خرید روزانه (D-BUY)</b>\n" + tbl("D-BUY"),
        "🟢 <b>خرید روزانه هم‌جهت با روند هفتگی (D-BUY+W)</b>\n" + tbl("D-BUY+W"),
        "⚪️ <b>ورود تصادفی (هر ۱۰ روز یک بار، برای مقایسه)</b>\n" + tbl("Random"),
        "<i>این آزمون توصیه‌ی خرید و فروش نیست. کارمزد و لغزش قیمت حساب نشده است.</i>",
    ]
    send(blocks, b"", "stops")
    return True
