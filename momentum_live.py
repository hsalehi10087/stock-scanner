"""
Live forward test of the candidate stock-picking methods (paper portfolios, monthly cohorts).

On the first trading day of every month (per market) each method picks stocks using only data up to the
last day of the previous month, and a paper portfolio is recorded (bought at that first day's close,
equal weights). Every later scan measures the portfolio's return with a 0.1% cost per side, and compares
it with EW (all stocks of the market held equally) and the market index. Only the picks are stored
(momentum_cohorts.csv); returns are recomputed from fresh prices each run.

This is the one test that cannot be fooled by hindsight, because the picks are written down before the
prices are known.
"""
import datetime as dt
import html
import os

import numpy as np
import pandas as pd

import method_test as mt

HERE = os.path.dirname(os.path.abspath(__file__))
COHORTS = os.path.join(HERE, "momentum_cohorts.csv")
COLS = ["cohort", "market", "method", "entry_date", "tickers"]
FOCUS = ("Mom12-1", "Mom6+Trend")
NAMES = mt.METHODS + ["EW", "Index"]


def load():
    if os.path.exists(COHORTS):
        return pd.read_csv(COHORTS, dtype=str, keep_default_na=False).reindex(columns=COLS).fillna("")
    return pd.DataFrame(columns=COLS)


def make_cohort(label, market, close, idx_close):
    """Picks of every method for the month that the latest row belongs to (data up to the previous month-end)."""
    keys = np.asarray(close.index.year * 12 + close.index.month)
    prior = np.nonzero(keys < keys[-1])[0]
    if len(prior) == 0:
        return []
    p = int(prior[-1])
    e = p + 1
    if p < 252 or e >= len(close):
        return []
    f = mt.features(close)
    entry_date = close.index[e].date().isoformat()
    entry_px = close.values[e]
    rows = []
    for m in mt.METHODS:
        if m == "Timing":
            if idx_close is None or len(idx_close) < 220:
                continue
            now = idx_close.asof(close.index[p])
            sma = idx_close.rolling(200).mean().asof(close.index[p])
            if now != now or sma != sma:
                continue
            tick = "ALL" if now > sma else "CASH"
        else:
            sel, _ = mt.select(m, p, f)
            sel = [int(i) for i in sel if np.isfinite(entry_px[i])]
            if len(sel) < 5:
                continue
            tick = ";".join(str(close.columns[i]) for i in sel)
        rows.append({"cohort": label, "market": market, "method": m, "entry_date": entry_date, "tickers": tick})
    return rows


def evaluate(frames, indexes, cohorts):
    """Pooled (equal weight over markets) net return of every cohort for every method, EW and the index."""
    per = {}          # (name, cohort) -> [(return, is_open)]
    for m, close in frames.items():
        sub = cohorts[cohorts["market"] == m]
        labels = sorted(sub["cohort"].unique())
        idx = indexes.get(m)
        prev_pick, prev_state = {}, {}
        for i, lab in enumerate(labels):
            rows = sub[sub["cohort"] == lab]
            entry = pd.Timestamp(rows["entry_date"].iloc[0])
            is_open = i + 1 >= len(labels)
            exit_ts = close.index[-1] if is_open else pd.Timestamp(sub[sub["cohort"] == labels[i + 1]]["entry_date"].iloc[0])
            if entry >= exit_ts:
                continue
            r0, r1 = close.loc[:entry].iloc[-1].values, close.loc[:exit_ts].iloc[-1].values
            ratio = r1 / r0 - 1
            ok = np.isfinite(ratio)
            if ok.sum() < 5:
                continue
            ew = float(ratio[ok].mean())
            per.setdefault(("EW", lab), []).append((ew, is_open))
            if idx is not None:
                a, b = idx.asof(entry), idx.asof(exit_ts)
                if a == a and b == b and a:
                    per.setdefault(("Index", lab), []).append((float(b / a - 1), is_open))
            for _, row in rows.iterrows():
                name, tk = row["method"], row["tickers"]
                if name == "Timing":
                    on = tk == "ALL"
                    cost = mt.COST * (1.0 if on != prev_state.get("on", False) else 0.0)
                    prev_state["on"] = on
                    per.setdefault((name, lab), []).append(((ew if on else 0.0) - cost, is_open))
                    continue
                cols = [c for c in tk.split(";") if c in close.columns]
                pos = close.columns.get_indexer(cols)
                vals = ratio[pos][np.isfinite(ratio[pos])]
                if len(vals) < 5:
                    continue
                w = {c: 1.0 / len(cols) for c in cols}
                pw = prev_pick.get(name, {})
                turn = sum(abs(w.get(c, 0.0) - pw.get(c, 0.0)) for c in set(w) | set(pw))
                prev_pick[name] = w
                per.setdefault((name, lab), []).append((float(vals.mean()) - mt.COST * turn, is_open))
    out = {}
    for (name, lab), lst in per.items():
        out.setdefault(name, {})[lab] = (float(np.mean([x[0] for x in lst])), any(x[1] for x in lst))
    return out


def scoreboard(res):
    """Rows for the table: cumulative return since start, month-to-date, and standing against EW."""
    labels = sorted({lab for d in res.values() for lab in d})
    if not labels:
        return [], labels
    ew = res.get("EW", {})
    cum = lambda d: float(np.prod([1 + d[l][0] for l in labels if l in d]) - 1) * 100
    last = labels[-1]
    rows = []
    for name in NAMES:
        d = res.get(name)
        if not d:
            continue
        closed = [l for l in labels if l in d and not d[l][1] and l in ew]
        beat = sum(1 for l in closed if d[l][0] > ew[l][0])
        rows.append({"name": name, "cum": cum(d), "mtd": d[last][0] * 100 if last in d else None,
                     "vs_ew": cum(d) - cum(ew) if ew else None, "beat": beat, "closed": len(closed)})
    return rows, labels


def run(series_cache, uni, bench_series, pre, short, force_send=False):
    """Returns (telegram_blocks_or_empty, summary_lines). Updates momentum_cohorts.csv."""
    today = dt.date.today()
    frames = {}
    for m in mt.MARKETS:
        s = series_cache.get(m)
        if not s:
            continue
        close = mt.build_frame(s)
        if close.shape[1] >= 30 and len(close) >= 300:
            frames[m] = close
    if not frames:
        return [], []
    indexes = {m: bench_series.get(m) for m in frames} if bench_series else {}
    cohorts = load()
    have = set(zip(cohorts["cohort"], cohorts["market"]))
    new_rows = []
    for m, close in frames.items():
        label = f"{close.index[-1].year}-{close.index[-1].month:02d}"
        if (label, m) in have:
            continue
        new_rows += make_cohort(label, m, close, indexes.get(m))
    first = cohorts.empty
    if new_rows:
        cohorts = pd.concat([cohorts, pd.DataFrame(new_rows, columns=COLS)], ignore_index=True)
        cohorts.to_csv(COHORTS, index=False)
    if cohorts.empty:
        return [], []
    res = evaluate(frames, indexes, cohorts)
    rows, labels = scoreboard(res)
    if not rows:
        return [], []
    n_closed = max((r["closed"] for r in rows), default=0)
    ew = next((r for r in rows if r["name"] == "EW"), None)
    focus = next((r for r in rows if r["name"] == "Mom12-1"), None)
    hl = []
    if focus and ew:
        start = "ماه اول آزمون در جریان است" if n_closed == 0 else f"{n_closed} ماه کامل و ماه جاری"
        hl.append(f"• {start}: مومنتوم ۱۲ماهه {focus['cum']:+.1f}٪ از شروع، "
                  f"EW {ew['cum']:+.1f}٪ (اختلاف {focus['cum'] - ew['cum']:+.1f}).")
    if new_rows:
        hl.append("• سبد ماهانه‌ی جدید ثبت شد؛ فهرست مومنتوم در پیام «آزمون زنده» است.")
    if not (new_rows or first or force_send or today.weekday() == 5):
        return [], hl

    t = [f"{'Method':<11}{'Cum%':>7}{'MTD%':>7}{'vsEW':>7}{'Beat':>6}", "-" * 38]
    for r in rows:
        t.append(f"{r['name']:<11}{mt.f1(r['cum']):>7}{mt.f1(r['mtd']):>7}"
                 f"{(mt.f1(r['vs_ew']) if r['name'] != 'EW' else '-'):>7}"
                 f"{(str(r['beat']) + '/' + str(r['closed']) if r['name'] not in ('EW', 'Index') else '-'):>6}")
    blocks = [
        f"🔬 <b>آزمون زنده‌ی روش‌های انتخاب سهم</b> — {today}\n"
        "<i>روز اول معاملاتی هر ماه هر روش با داده‌ی تا آخر ماه قبل سهم انتخاب می‌کند و یک سبد کاغذی ثبت می‌شود "
        "(خرید در قیمت پایانی همان روز، وزن مساوی). بازده هر سبد با کارمزد ۰٫۱٪ برای هر خرید و فروش دنبال "
        "و با EW (نگه‌داشتن همه‌ی سهم‌های همان بازار) و شاخص مقایسه می‌شود. چون فهرست قبل از دانستن قیمت‌های آینده ثبت می‌شود، "
        "این تنها آزمونی است که خودفریبی در آن ممکن نیست؛ ولی چند ماه طول می‌کشد تا نتیجه روشن شود.</i>",
        "<i>Cum% بازده از شروع آزمون تا امروز · MTD% بازده ماه جاری · vsEW اختلاف Cum% با EW (عدد مثبت یعنی بهتر از «نگه‌داشتن همه») · "
        "Beat تعداد ماه‌های کامل که روش از EW بهتر بود از کل ماه‌های کامل</i>",
        "📊 <b>جدول امتیاز</b> (میانگین پنج بازار با وزن مساوی)\n" + pre(t),
    ]
    if n_closed < 6:
        blocks.append(f"⏳ هنوز فقط {n_closed} ماه کامل داریم. با کمتر از ۶ ماه نمی‌شود نتیجه گرفت؛ هر چه زودتر ببینید، "
                      "بیشتر شانس است تا مهارت. گزارش کامل هر هفته (شنبه‌ها) و در شروع هر ماه می‌آید.")
    else:
        top = max((r for r in rows if r["name"] in mt.METHODS), key=lambda r: r["vs_ew"] if r["vs_ew"] is not None else -999)
        blocks.append(f"📌 تا امروز بهترین روش نسبت به EW: <b>{top['name']}</b> ({mt.f1(top['vs_ew'])} امتیاز). "
                      "پیش از اعتماد، دست‌کم یک سال داده و برتری در بیشتر ماه‌ها (ستون Beat) را ببینید.")
    if new_rows:
        by = {}
        for r in new_rows:
            if r["method"] in FOCUS and r["tickers"] not in ("ALL", "CASH"):
                by.setdefault(r["method"], []).append((r["market"], r["tickers"].split(";")[:10]))
        for method, items in by.items():
            lines = [f"🆕 <b>سبد جدید روش {method}</b> (۱۰ سهم اول هر بازار؛ فهرست کامل در momentum_cohorts.csv)"]
            for m, tk in items:
                lines.append(f"{m}: " + "، ".join(html.escape(short(x)) for x in tk))
            blocks.append("\n".join(lines))
    blocks.append("<i>این فهرست‌ها آزمایشی‌اند و توصیه‌ی خرید یا فروش نیستند.</i>")
    return blocks, hl
