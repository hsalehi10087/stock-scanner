"""
A stronger stock-selection strategy than RSI/MACD, built only from ideas with long published evidence
and tested over 10 years of daily prices (5 markets), as monthly portfolios with costs.

Strategies (rules fixed BEFORE looking at any result; no tuning):
  TechOld  the old way: buy every stock whose MACD is positive and RSI < 70 at month-end (equal weight)
  V0-Mom   12-month momentum (skip last month): top 20% (equal weight)
  V1-RAMom risk-adjusted momentum: momentum divided by the stock's own volatility, only stocks above their
           200-day average, top 20% (equal weight)
  V2-Core  "Core": average rank of risk-adjusted momentum and closeness to the 52-week high, only stocks above
           their 200-day average, top 20%, weights proportional to 1 / volatility (cap: 2.5x equal weight)
  V3-CoreR Core, but invested only 50% when the market index is below its 200-day average
Benchmarks: EW (all stocks of the market, equal weight) and the market index.
Method: signal at month-end, buy at the next day's close, hold one month, cost 0.1% per side on turnover,
results of the 5 markets averaged with equal weight; history split in two halves to check consistency.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

import method_test as mt

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(HERE, "backtest_core.json")
NAMES = ["TechOld", "V0-Mom", "V1-RAMom", "V2-Core", "V3-CoreR"]
FRAC = 0.20
COST = mt.COST
WEIGHTS = {"V0-Mom": "ew", "V1-RAMom": "ew", "TechOld": "ew", "V2-Core": "invvol", "V3-CoreR": "invvol"}


def indicators(close):
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    d = close.diff()
    ag = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    al = (-d).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + ag / al)).where(al > 0, 100.0).where(ag.notna() & al.notna())
    return hist.values, rsi.values


def feats(close):
    ret = close.pct_change(fill_method=None)
    vol252 = ret.rolling(252, min_periods=200).std()
    vol60 = ret.rolling(60).std()
    mom = close.shift(21) / close.shift(252) - 1
    sma = close.rolling(200).mean()
    hist, rsi = indicators(close)
    return {"mom": mom.values, "ramom": (mom / (vol252 * np.sqrt(252))).values,
            "hi52": (close / close.rolling(252, min_periods=200).max()).values,
            "vol60": vol60.values, "trend": ((close > sma) & sma.notna()).values,
            "hist": hist, "rsi": rsi}


def pct_rank(x):
    order = x.argsort().argsort()
    return order / max(len(x) - 1, 1)


def pick(name, p, f):
    """Returns {column_position: weight} for one strategy using only data up to row p."""
    if name == "TechOld":
        ok = (f["hist"][p] > 0) & (f["rsi"][p] < 70) & np.isfinite(f["rsi"][p])
        cols = np.nonzero(ok)[0]
        return {int(c): 1.0 / len(cols) for c in cols} if len(cols) >= 10 else {}
    if name == "V0-Mom":
        s = f["mom"][p]
        valid = np.nonzero(np.isfinite(s))[0]
        score = s[valid]
    elif name == "V1-RAMom":
        s = f["ramom"][p]
        valid = np.nonzero(np.isfinite(s) & f["trend"][p])[0]
        score = s[valid]
    else:   # V2 / V3
        a, h, v = f["ramom"][p], f["hi52"][p], f["vol60"][p]
        valid = np.nonzero(np.isfinite(a) & np.isfinite(h) & np.isfinite(v) & (v > 0) & f["trend"][p])[0]
        score = pct_rank(a[valid]) + pct_rank(h[valid]) if len(valid) else np.array([])
    if len(valid) < 20:
        return {}
    k = max(1, int(np.ceil(FRAC * len(valid))))
    top = valid[np.argsort(-score)[:k]]
    if WEIGHTS[name] == "ew":
        return {int(c): 1.0 / len(top) for c in top}
    w = 1.0 / f["vol60"][p][top]
    w = w / w.sum()
    w = np.minimum(w, 2.5 / len(top))
    w = w / w.sum()
    return {int(c): float(x) for c, x in zip(top, w)}


def run_market(close, idx):
    f = feats(close)
    keys, pos = mt.month_ends(close.index)
    n, vals = len(close), close.values
    out = {k: {} for k in NAMES + ["EW"]}
    prev = {k: {} for k in NAMES}
    sma_idx = idx.rolling(200).mean() if idx is not None else None
    for k in range(len(pos) - 1):
        p = pos[k]
        if p < 252:
            continue
        e0, e1 = p + 1, pos[k + 1] + 1
        if e1 >= n:
            break
        r = vals[e1] / vals[e0] - 1
        ok = np.isfinite(r)
        if ok.sum() < 20:
            continue
        key = int(keys[k])
        out["EW"][key] = float(r[ok].mean())
        for name in NAMES:
            w = pick("V2-Core" if name == "V3-CoreR" else name, p, f)
            w = {c: x for c, x in w.items() if ok[c]}
            if len(w) < 5:
                continue
            tot = sum(w.values())
            w = {c: x / tot for c, x in w.items()}
            gross = sum(x * r[c] for c, x in w.items())
            expo = 1.0
            if name == "V3-CoreR" and sma_idx is not None:
                a, b = idx.asof(close.index[p]), sma_idx.asof(close.index[p])
                expo = 1.0 if (a == a and b == b and a > b) else 0.5
            turn = sum(abs(w.get(c, 0.0) * expo - prev[name].get(c, 0.0)) for c in set(w) | set(prev[name]))
            prev[name] = {c: x * expo for c, x in w.items()}
            out[name][key] = gross * expo - COST * turn
    return out


def f1(v, fmt="{:+.1f}"):
    return mt.f1(v, fmt)


def run(request_id, uni, download_all, short, pre, send):
    import bench
    today = dt.date.today().strftime("%Y-%m-%d")
    idx_data = download_all(list(bench.INDEX.values()), period="10y")
    per = {}
    for m in mt.MARKETS:
        if not uni.get(m):
            continue
        close = mt.build_frame(download_all(uni[m], period="10y"))
        if close.shape[1] < 30 or len(close) < 800:
            print(f"core: {m}: not enough data {close.shape}")
            continue
        s = idx_data.get(bench.INDEX.get(m))
        idx = None
        if s is not None:
            s = s.copy()
            ix = pd.to_datetime(s.index)
            s.index = (ix.tz_localize(None) if getattr(ix, "tz", None) is not None else ix).normalize()
            idx = s[~s.index.duplicated(keep="last")].astype(float).sort_index()
        res = run_market(close, idx)
        if idx is not None:   # market index monthly returns on the same entry dates
            keys, pos = mt.month_ends(close.index)
            res["Index"] = {}
            for k in range(len(pos) - 1):
                e0, e1 = pos[k] + 1, pos[k + 1] + 1
                if pos[k] >= 252 and e1 < len(close):
                    a, b = idx.asof(close.index[e0]), idx.asof(close.index[e1])
                    if a == a and b == b and a:
                        res["Index"][int(keys[k])] = float(b / a - 1)
        per[m] = res
        print(f"core: {m}: {close.shape[1]} symbols, {len(res['EW'])} months")
    if not per:
        send(["⚠️ آزمون انجام نشد: داده‌ی تاریخی دریافت نشد."], b"", "core")
        return False
    names = NAMES + ["EW", "Index"]
    pooled = {nm: pd.DataFrame({m: pd.Series(per[m].get(nm, {})) for m in per}).mean(axis=1, skipna=True).dropna()
              for nm in names}
    months = sorted(set.intersection(*[set(pooled[nm].index) for nm in names if len(pooled[nm])]))
    half = len(months) // 2
    parts = {"full": months, "first": months[:half], "second": months[half:]}
    stats = {k: {nm: mt.stats(pooled[nm].loc[v].values, pooled["EW"].loc[v].values) for nm in names if len(pooled[nm])}
             for k, v in parts.items()}

    def show(st):
        t = [f"{'Strategy':<10}{'Ann%':>6}{'Shrp':>5}{'MaxDD':>6}{'Exc%':>7}{'t':>6}{'Beat':>5}", "-" * 45]
        for nm in names:
            r = st.get(nm)
            if r:
                t.append(f"{nm:<10}{f1(r['ann']):>6}{f1(r['sharpe'], '{:.1f}'):>5}"
                         f"{f1(r['mdd'], '{:.0f}'):>6}{(f1(r['exc']) if nm != 'EW' else '-'):>7}"
                         f"{(f1(r['t'], '{:+.1f}') if nm != 'EW' else '-'):>6}"
                         f"{(f1(r['beat'], '{:.0f}') if nm != 'EW' else '-'):>5}")
        return pre(t)

    def span(ms):
        a, b = ms[0], ms[-1]
        return f"{(a - 1) // 12}-{(a - 1) % 12 + 1:02d} تا {(b - 1) // 12}-{(b - 1) % 12 + 1:02d}"

    # by calendar year: Core minus EW
    yr = {}
    for k in months:
        y = (k - 1) // 12
        for nm in ("V2-Core", "V0-Mom", "TechOld"):
            yr.setdefault(y, {}).setdefault(nm, []).append(pooled[nm].loc[k] - pooled["EW"].loc[k])
    ty = [f"{'Year':<6}{'Core':>7}{'Mom':>7}{'TechOld':>9}", "-" * 29]
    for y in sorted(yr):
        ty.append(f"{y:<6}{np.mean(yr[y]['V2-Core']) * 1200:>+7.1f}{np.mean(yr[y]['V0-Mom']) * 1200:>+7.1f}"
                  f"{np.mean(yr[y]['TechOld']) * 1200:>+9.1f}")
    # worst market months
    worst = pooled["EW"].loc[months].nsmallest(10).index
    wr = {nm: float(np.mean([pooled[nm].loc[k] - pooled["EW"].loc[k] for k in worst])) * 100
          for nm in ("V2-Core", "V3-CoreR", "V0-Mom", "TechOld")}
    # by market (full period): Core excess
    tm = [f"{'Market':<7}{'Core':>8}{'EW':>7}{'Exc%/yr':>9}", "-" * 31]
    for m, res in per.items():
        a = pd.Series(res["V2-Core"]).reindex(months).dropna()
        e = pd.Series(res["EW"]).reindex(a.index)
        if len(a) >= 12:
            ga, ge = np.prod(1 + a.values) ** (12 / len(a)) - 1, np.prod(1 + e.values) ** (12 / len(a)) - 1
            tm.append(f"{m:<7}{ga * 100:>+8.1f}{ge * 100:>+7.1f}{(a.values - e.values).mean() * 1200:>+9.1f}")

    json.dump({"request": request_id, "date": today, "months": len(months), "stats": stats,
               "worst10_excess_pct": wr}, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)

    core_f, core_s = stats["first"]["V2-Core"], stats["second"]["V2-Core"]
    core_all, tech_all, mom_all = stats["full"]["V2-Core"], stats["full"]["TechOld"], stats["full"]["V0-Mom"]
    blocks = [
        f"🏆 <b>استراتژی «هسته» در برابر RSI و MACD</b> — {today}\n"
        f"<i>همه‌ی روش‌ها به‌صورت سبد ماهانه روی {len(months)} ماه (حدود ۱۰ سال) و ۵ بازار آزمایش شدند. آخر هر ماه انتخاب می‌شود، فردا خرید، یک ماه نگه‌داری، "
        "کارمزد ۰٫۱٪. قاعده‌ها قبل از دیدن نتیجه ثابت شدند و تنظیم نشدند. تاریخچه دو نیم شده تا ببینیم نتیجه در هر دو نیمه ثابت است یا نه.</i>",
        "• <b>TechOld</b>: روش قدیمی، سهم‌هایی که MACD مثبت و RSI زیر ۷۰ دارند\n"
        "• <b>V0-Mom</b>: مومنتوم ۱۲ماهه (۲۰٪ برتر)\n"
        "• <b>V1-RAMom</b>: مومنتومِ تعدیل‌شده با نوسان خود سهم، فقط بالای میانگین ۲۰۰ روزه\n"
        "• <b>V2-Core («هسته»)</b>: میانگین رتبه‌ی V1 و نزدیکی به سقف ۵۲ هفته، فقط بالای میانگین ۲۰۰ روزه، وزن هر سهم معکوس نوسانش\n"
        "• <b>V3-CoreR</b>: «هسته» با ۵۰٪ نقد وقتی شاخص بازار زیر میانگین ۲۰۰ روزه است",
        "<i>Ann% بازده سالانه · Shrp بازده به ازای ریسک · MaxDD بزرگ‌ترین افت ماهانه از سقف · Exc% برتری سالانه نسبت به EW (همه‌ی سهم‌ها) · "
        "t اطمینان آماری (۲ یا بیشتر یعنی احتمالاً شانسی نیست) · Beat درصد ماه‌هایی که از EW بهتر بود</i>",
        f"📊 <b>کل دوره</b> — {len(months)} ماه، {span(months)}\n" + show(stats["full"]),
        f"📚 <b>نیمه‌ی اول</b> — {len(parts['first'])} ماه\n" + show(stats["first"]),
        f"🧪 <b>نیمه‌ی دوم</b> — {len(parts['second'])} ماه\n" + show(stats["second"]),
        "📅 <b>برتری سالانه نسبت به EW در هر سال (درصد)</b>\n" + pre(ty),
        "📉 <b>در ۱۰ بدترین ماه بازار</b> (میانگین اختلاف با EW در همان ماه‌ها، درصد)\n"
        + pre([f"{k:<10}{v:>+7.2f}" for k, v in wr.items()]),
        "🌍 <b>«هسته» به تفکیک بازار (کل دوره)</b>\n" + pre(tm),
    ]
    L = ["🧾 <b>نتیجه به زبان ساده</b>"]
    L.append(f"• «هسته» در کل دوره سالی {f1(core_all['ann'])}٪ داشت؛ نگه‌داشتن همه‌ی سهم‌ها {f1(stats['full']['EW']['ann'])}٪؛ "
             f"روش قدیمی RSI/MACD {f1(tech_all['ann'])}٪؛ مومنتوم ساده {f1(mom_all['ann'])}٪.")
    L.append(f"• برتری «هسته» نسبت به EW: {f1(core_all['exc'])}٪ در سال (t = {f1(core_all['t'], '{:+.1f}')}). "
             f"در نیمه‌ی اول {f1(core_f['exc'])}٪ و در نیمه‌ی دوم {f1(core_s['exc'])}٪.")
    L.append(f"• برتری روش قدیمی RSI/MACD نسبت به EW: {f1(tech_all['exc'])}٪ در سال (t = {f1(tech_all['t'], '{:+.1f}')}).")
    if core_all["exc"] > 0 and core_all["t"] >= 2 and core_f["exc"] > 0 and core_s["exc"] > 0:
        L.append("• «هسته» هم در کل دوره و هم در هر دو نیمه از EW جلو بود و اطمینان آماری قابل‌قبول دارد ✅")
    elif core_f["exc"] > 0 and core_s["exc"] > 0:
        L.append("• «هسته» در هر دو نیمه از EW جلو بود، ولی اطمینان آماری هنوز کافی نیست.")
    else:
        L.append("• «هسته» در هر دو نیمه از EW جلو نبود؛ پس برتری‌اش قابل‌اعتماد نیست.")
    L.append(f"• در بدترین ماه‌های بازار، «هسته» به‌طور میانگین {f1(wr['V2-Core'], '{:+.2f}')}٪ نسبت به EW داشت "
             f"(با نقد‌شدن در روند نزولی: {f1(wr['V3-CoreR'], '{:+.2f}')}٪).")
    blocks.append("\n".join(L))
    blocks.append(
        "⚠️ <b>محدودیت‌ها</b>\n"
        "• فهرست سهم‌ها، شرکت‌های امروزِ هر شاخص است. شرکت‌هایی که طی ۱۰ سال حذف یا ورشکست شده‌اند در آزمون نیستند؛ "
        "این برای روش‌های مومنتوم همیشه نتیجه را کمی خوش‌بین می‌کند.\n"
        "• ۱۰ سال شامل چند بحران اصلی بوده، ولی هنوز یک نمونه‌ی محدود از بازار است.\n"
        "• لغزش قیمت و سهم‌های کوچک حساب نشده؛ بازده واقعی معمولاً کمی پایین‌تر است.\n"
        "• تنها آزمون بدون خودفریبی، ثبت زنده‌ی ماه‌به‌ماه است که ادامه دارد.\n"
        "<i>این نتیجه توصیه‌ی خرید یا فروش نیست.</i>")
    send(blocks, b"", "core")
    return True
