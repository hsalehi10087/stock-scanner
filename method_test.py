"""
Which stock-picking method is worth using? Candidate methods are tested as simple monthly portfolios.

Design (decided before looking at any result, to avoid fooling ourselves):
  * candidates come from well-known, long-documented ideas, not from tuning on this data
  * history is cut in two halves: the OLDER half is used to choose the method, the NEWER half is the
    honest out-of-sample test (only the chosen method's test result is a real out-of-sample number)
  * at the close of each month every method picks stocks; the buy is made at the next day's close and held
    for a month (equal weights); cost = 0.1% per side on whatever is bought or sold
  * the benchmark is "EW": all stocks of the market held equally, which removes market-direction luck
  * results of the 5 stock markets are averaged with equal weight each month
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(HERE, "backtest_method.json")
PICKS_CSV = os.path.join(HERE, "method_picks.csv")
MARKETS = ("US", "JP", "IN", "TW", "CN")
COST = 0.001            # per side
FRAC = 0.20             # share of stocks a method holds
METHODS = ["Mom12-1", "Mom6+Trend", "Pullback", "LowVol", "Trend", "Timing"]
RULES_FA = {
    "Mom12-1": "مومنتوم: ۲۰٪ سهمی که در ۱۲ ماه گذشته (بدون ماه آخر) بیشترین رشد را داشته‌اند",
    "Mom6+Trend": "مومنتوم کوتاه‌تر: ۲۰٪ برترِ رشد ۶ ماهه، فقط بین سهم‌های بالای میانگین ۲۰۰ روزه",
    "Pullback": "خرید افت در روند صعودی: بین سهم‌های بالای میانگین ۲۰۰ روزه، ۲۰٪ که در یک ماه گذشته بیشتر افت کرده‌اند",
    "LowVol": "کم‌نوسان: ۲۰٪ سهمی که نوسان روزانه‌ی ۳ ماه اخیرشان کمتر است",
    "Trend": "فقط روند صعودی: همه‌ی سهم‌های بالای میانگین ۲۰۰ روزه",
    "Timing": "زمان‌بندی بازار: همه‌ی سهم‌ها وقتی شاخص بالای میانگین ۲۰۰ روزه است، وگرنه نقد",
}


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
    return pd.DataFrame(cols).sort_index().ffill(limit=3) if cols else pd.DataFrame()


def features(close):
    sma = close.rolling(200).mean()
    return {
        "mom12": (close.shift(21) / close.shift(252) - 1).values,
        "mom6": (close.shift(21) / close.shift(126) - 1).values,
        "ret21": (close / close.shift(21) - 1).values,
        "vol60": close.pct_change(fill_method=None).rolling(60).std().values,
        "trend": ((close > sma) & sma.notna()).values,
    }


def select(name, p, f):
    """Column positions chosen by `name` using only information up to row p."""
    trend = f["trend"][p]
    if name == "Mom12-1":
        s, ok, best = f["mom12"][p], ~np.isnan(f["mom12"][p]), "high"
    elif name == "Mom6+Trend":
        s, ok, best = f["mom6"][p], ~np.isnan(f["mom6"][p]) & trend, "high"
    elif name == "Pullback":
        s, ok, best = f["ret21"][p], ~np.isnan(f["ret21"][p]) & trend, "low"
    elif name == "LowVol":
        s, ok, best = f["vol60"][p], ~np.isnan(f["vol60"][p]), "low"
    elif name == "Trend":
        return np.nonzero(trend)[0], None
    else:
        return np.array([], dtype=int), None
    cand = np.nonzero(ok)[0]
    if len(cand) < 10:
        return np.array([], dtype=int), None
    k = max(1, int(np.ceil(FRAC * len(cand))))
    order = np.argsort(-s[cand] if best == "high" else s[cand])
    return cand[order[:k]], s


def month_ends(index):
    key = index.year * 12 + index.month
    last = pd.Series(np.arange(len(index)), index=key).groupby(level=0).max()
    return last.index.values, last.values


def run_market(close, idx_close):
    """Monthly net returns per method (+EW, +index) for one market, and the latest picks."""
    f = features(close)
    keys, pos = month_ends(close.index)
    n = len(close)
    vals = close.values
    out = {m: {} for m in METHODS + ["EW", "Index"]}
    prev = {m: {} for m in METHODS}
    idx_sma = idx_close.rolling(200).mean() if idx_close is not None else None
    timing_on = False
    for k in range(len(pos) - 1):
        p = pos[k]
        if p < 252:
            continue
        e0, e1 = p + 1, pos[k + 1] + 1
        if e1 >= n:
            break
        r = vals[e1] / vals[e0] - 1
        ok = np.isfinite(r)
        if ok.sum() < 10:
            continue
        key = int(keys[k])
        ew = float(r[ok].mean())
        out["EW"][key] = ew
        if idx_close is not None:
            a, b = idx_close.asof(close.index[e0]), idx_close.asof(close.index[e1])
            if a == a and b == b and a:
                out["Index"][key] = float(b / a - 1)
        for m in METHODS:
            if m == "Timing":
                if idx_sma is None:
                    continue
                s_now, s_sma = idx_close.asof(close.index[p]), idx_sma.asof(close.index[p])
                if s_now != s_now or s_sma != s_sma:
                    continue
                on = bool(s_now > s_sma)
                cost = COST * (1.0 if on != timing_on else 0.0)
                timing_on = on
                out[m][key] = (ew if on else 0.0) - cost
                continue
            sel, _ = select(m, p, f)
            sel = sel[ok[sel]] if len(sel) else sel
            if len(sel) < 5:
                continue
            w = {int(i): 1.0 / len(sel) for i in sel}
            turn = sum(abs(w.get(i, 0.0) - prev[m].get(i, 0.0)) for i in set(w) | set(prev[m]))
            prev[m] = w
            out[m][key] = float(r[sel].mean()) - COST * turn
    # today's picks (latest row)
    picks = {}
    last = n - 1
    for m in METHODS:
        if m == "Timing":
            continue
        sel, s = select(m, last, f)
        if len(sel):
            order = sel if s is None else sel[np.argsort(-s[sel] if m in ("Mom12-1", "Mom6+Trend") else s[sel])]
            picks[m] = [close.columns[i] for i in order]
    return out, picks


def stats(r, ew):
    r, ew = np.asarray(r, float), np.asarray(ew, float)
    n = len(r)
    if n < 6:
        return None
    cum = np.cumprod(1 + r)
    vol = r.std(ddof=1) * np.sqrt(12)
    ex = r - ew
    sd = ex.std(ddof=1)
    return {"n": n, "ann": float(cum[-1] ** (12 / n) - 1) * 100, "vol": float(vol * 100),
            "sharpe": float(r.mean() * 12 / vol) if vol > 0 else float("nan"),
            "mdd": float((cum / np.maximum.accumulate(cum) - 1).min() * 100),
            "exc": float(ex.mean() * 12 * 100), "t": float(ex.mean() / (sd / np.sqrt(n))) if sd > 0 else float("nan"),
            "beat": float((ex > 0).mean() * 100), "growth": float(cum[-1])}


def f1(v, fmt="{:+.1f}"):
    return "-" if v is None or v != v else fmt.format(v)


def run(request_id, uni, download_all, short, pre, send):
    import bench
    today = dt.date.today().strftime("%Y-%m-%d")
    idx_data = download_all(list(bench.INDEX.values()), period="5y")
    per_market, picks_all = {}, {}
    for m in MARKETS:
        if not uni.get(m):
            continue
        close = build_frame(download_all(uni[m], period="5y"))
        if close.shape[1] < 30 or len(close) < 700:
            print(f"method: {m}: not enough data {close.shape}")
            continue
        idx_close = None
        s = idx_data.get(bench.INDEX.get(m))
        if s is not None:
            s = s.copy()
            ix = pd.to_datetime(s.index)
            s.index = (ix.tz_localize(None) if getattr(ix, "tz", None) is not None else ix).normalize()
            idx_close = s[~s.index.duplicated(keep="last")].astype(float).sort_index()
        res, picks = run_market(close, idx_close)
        per_market[m] = res
        picks_all[m] = picks
        print(f"method: {m}: {close.shape[1]} symbols, {len(res['EW'])} months")
    if not per_market:
        send(["⚠️ آزمون روش‌ها انجام نشد: داده‌ی تاریخی دریافت نشد."], b"", "method")
        return False

    names = METHODS + ["EW", "Index"]
    pooled = {}
    for nm in names:
        df = pd.DataFrame({m: pd.Series(per_market[m][nm]) for m in per_market})
        pooled[nm] = df.mean(axis=1, skipna=True).dropna()
    months = sorted(set.intersection(*[set(pooled[nm].index) for nm in names if len(pooled[nm])]))
    half = len(months) // 2
    train, test = months[:half], months[half:]

    def table(period):
        ew = pooled["EW"].loc[period].values
        return {nm: stats(pooled[nm].loc[period].values, ew) for nm in names if len(pooled[nm])}

    st_train, st_test = table(train), table(test)
    cand = [m for m in METHODS if st_train.get(m)]
    best = max(cand, key=lambda m: st_train[m]["sharpe"] if st_train[m]["sharpe"] == st_train[m]["sharpe"] else -9)

    def fmt_period(period):
        a, b = period[0], period[-1]
        return f"{a // 12}-{a % 12 or 12:02d} تا {b // 12}-{b % 12 or 12:02d}"

    def show(st):
        t = [f"{'Method':<11}{'Ann%':>6}{'Vol':>4}{'Shrp':>5}{'MaxDD':>6}{'Exc%':>7}{'t':>5}", "-" * 44]
        for nm in names:
            r = st.get(nm)
            if r:
                t.append(f"{nm:<11}{f1(r['ann']):>6}{f1(r['vol'], '{:.0f}'):>4}{f1(r['sharpe'], '{:.1f}'):>5}"
                         f"{f1(r['mdd'], '{:.0f}'):>6}{(f1(r['exc']) if nm not in ('EW',) else '-'):>7}"
                         f"{(f1(r['t'], '{:+.0f}') if nm not in ('EW',) else '-'):>5}")
        return pre(t)

    b_tr, b_te, ew_te = st_train[best], st_test.get(best), st_test.get("EW")
    # by-market view of the chosen method on the test months
    mt = [f"{'Market':<7}{'Method':>8}{'EW':>7}{'Exc%/yr':>9}", "-" * 31]
    for m, res in per_market.items():
        a = pd.Series(res[best]).reindex(test).dropna()
        e = pd.Series(res["EW"]).reindex(a.index)
        if len(a) >= 6:
            ga, ge = np.prod(1 + a.values) ** (12 / len(a)) - 1, np.prod(1 + e.values) ** (12 / len(a)) - 1
            mt.append(f"{m:<7}{ga * 100:>+8.1f}{ge * 100:>+7.1f}{(a.values - e.values).mean() * 1200:>+9.1f}")

    json.dump({"request": request_id, "date": today, "best": best, "train_months": [int(x) for x in train],
               "test_months": [int(x) for x in test], "train": st_train, "test": st_test},
              open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    rows = []
    for m, dct in picks_all.items():
        for rank, tk in enumerate(dct.get(best, [])[:40], 1):
            rows.append({"market": m, "method": best, "rank": rank, "ticker": tk})
    pd.DataFrame(rows).to_csv(PICKS_CSV, index=False)

    blocks = [
        f"🧭 <b>کدام روش انتخاب سهم بهتر کار می‌کند؟</b> — {today}\n"
        "<i>چند روش شناخته‌شده را به‌صورت یک سبد ماهانه آزمودیم: آخر هر ماه هر روش سهم انتخاب می‌کند، فردا می‌خرد و یک ماه نگه می‌دارد. "
        "کارمزد ۰٫۱٪ برای هر خرید و فروش حساب شده. معیار مقایسه EW است: نگه‌داشتن همه‌ی سهم‌های همان بازار به‌طور مساوی. "
        "نتیجه‌ی پنج بازار (آمریکا، ژاپن، هند، تایوان، چین) با وزن مساوی میانگین گرفته شده است.</i>",
        "<i>چون انتخاب روش از روی خودِ همان داده می‌تواند خودفریبی شود، تاریخچه نصف شد: روش را از روی نیمه‌ی قدیمی‌تر انتخاب کردیم "
        "و فقط نیمه‌ی جدیدتر را «آزمون واقعی» حساب می‌کنیم.</i>",
        "\n".join(f"• <b>{m}</b>: {RULES_FA[m]}" for m in METHODS),
        "<i>Ann% بازده سالانه · Vol% نوسان سالانه · Shrp بازده به ازای هر واحد ریسک · MaxDD بزرگ‌ترین افت از سقف · "
        "Exc% برتری سالانه نسبت به EW · t اطمینان آماری (۲ یا بیشتر یعنی احتمالاً اتفاقی نیست؛ برای EW خالی است) · Index شاخص بازار</i>",
        f"📚 <b>نیمه‌ی قدیمی‌تر (برای انتخاب روش)</b> — {len(train)} ماه، {fmt_period(train)}\n" + show(st_train),
        f"🧪 <b>نیمه‌ی جدیدتر (آزمون واقعی)</b> — {len(test)} ماه، {fmt_period(test)}\n" + show(st_test),
        f"🏁 روش انتخاب‌شده از روی نیمه‌ی قدیمی‌تر (بالاترین Shrp): <b>{best}</b>",
        "🌍 <b>همین روش به تفکیک بازار در آزمون واقعی</b>\n" + pre(mt),
    ]
    # plain-language verdict
    lines = ["🧾 <b>نتیجه به زبان ساده</b>"]
    if b_te and ew_te:
        lines.append(f"• روش {best} در آزمون واقعی سالی {f1(b_te['ann'])}٪ بازده داشت؛ نگه‌داشتن همه‌ی سهم‌ها {f1(ew_te['ann'])}٪ "
                     f"و شاخص بازار {f1(st_test['Index']['ann']) if st_test.get('Index') else '-'}٪.")
        lines.append(f"• بزرگ‌ترین افت روش: {f1(b_te['mdd'], '{:.0f}')}٪؛ نگه‌داشتن همه: {f1(ew_te['mdd'], '{:.0f}')}٪.")
        if b_te["exc"] > 0 and b_te["t"] == b_te["t"] and b_te["t"] >= 2:
            lines.append("• برتری روش نسبت به نگه‌داشتن همه‌ی سهم‌ها از نظر آماری روشن است ✅")
        elif b_te["exc"] > 0:
            lines.append(f"• روش {f1(b_te['exc'])}٪ در سال بهتر از EW بود، ولی با {len(test)} ماه داده نمی‌شود مطمئن بود که شانسی نبوده (t = {f1(b_te['t'], '{:+.1f}')}).")
        else:
            lines.append("• روش از نگه‌داشتن ساده‌ی همه‌ی سهم‌ها بهتر نبود؛ یعنی در این آزمون، انتخاب سهم ارزشی اضافه نکرد.")
    best_te = max((m for m in METHODS if st_test.get(m)), key=lambda m: st_test[m]["sharpe"], default=None)
    if best_te and best_te != best:
        lines.append(f"• برای شفافیت: بهترین روش در خودِ نیمه‌ی جدید {best_te} بود، ولی انتخاب بعد از دیدن نتیجه معتبر نیست.")
    blocks.append("\n".join(lines))
    # latest picks of the chosen method
    pk = [f"<b>فهرست امروزِ روش {best}</b> (۱۰ مورد اول هر بازار؛ فهرست بلندتر در فایل method_picks.csv)"]
    for m, dct in picks_all.items():
        names_ = dct.get(best, [])[:10]
        if names_:
            pk.append(f"{m}: " + "، ".join(short(t) for t in names_))
    blocks.append("\n".join(pk))
    blocks.append(
        "⚠️ <b>محدودیت‌ها</b>\n"
        "• فهرست سهم‌ها شرکت‌های امروزِ هر شاخص است؛ شرکت‌هایی که در این سال‌ها حذف شده‌اند در آزمون نیستند. "
        "این روش‌های مومنتوم را معمولاً خوش‌بین‌تر نشان می‌دهد.\n"
        "• هر نیمه حدود دو سال (۲۴ ماه) است. با این تعداد ماه فقط برتری‌های خیلی بزرگ آماری روشن می‌شوند.\n"
        "• ایده‌ی «خرید افت» تا حدی از دیدنِ نتیجه‌ی بک‌تست قبلی الهام گرفته شد؛ برای همین احتمال خوش‌بینی در آن بیشتر است.\n"
        "• وزن مساوی و بازارهای بزرگ: سهم‌های کوچک و کم‌معامله در فهرست‌ها نیستند و لغزش قیمت حساب نشده.\n"
        "<i>این نتیجه توصیه‌ی خرید یا فروش نیست.</i>")
    send(blocks, b"", "method")
    return True
