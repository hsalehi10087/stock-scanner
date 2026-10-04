"""
Live (paper) forward test of the strategies from core_lab: V1-RAMom (risk-adjusted momentum), V2-Core, and the
old RSI/MACD portfolio (TechOld) as the foil. On the first trading day of each month (per market) the strategy
picks stocks with data up to the last day of the previous month and a paper portfolio is recorded (bought at
that day's close, weights as designed, 0.1% cost per side on turnover). Only the picks are stored
(core_cohorts.csv); returns are recomputed from fresh prices every run, so nothing can be adjusted afterwards.
"""
import datetime as dt
import html
import os

import numpy as np
import pandas as pd

import core_lab as cl
import method_test as mt

HERE = os.path.dirname(os.path.abspath(__file__))
COH = os.path.join(HERE, "core_cohorts.csv")
COLS = ["cohort", "market", "strategy", "entry_date", "picks"]
STRATS = ["V1-RAMom", "V2-Core", "TechOld"]
NAMES = STRATS + ["EW", "Index"]


def load():
    if os.path.exists(COH):
        return pd.read_csv(COH, dtype=str, keep_default_na=False).reindex(columns=COLS).fillna("")
    return pd.DataFrame(columns=COLS)


def make_cohort(label, market, close):
    keys = np.asarray(close.index.year * 12 + close.index.month)
    prior = np.nonzero(keys < keys[-1])[0]
    if len(prior) == 0:
        return []
    p = int(prior[-1])
    e = p + 1
    if p < 252 or e >= len(close):
        return []
    f = cl.feats(close)
    entry = close.index[e].date().isoformat()
    px = close.values[e]
    rows = []
    for s in STRATS:
        w = {c: x for c, x in cl.pick(s, p, f).items() if np.isfinite(px[c])}
        if len(w) < 5:
            continue
        tot = sum(w.values())
        picks = ";".join(f"{close.columns[c]}:{x / tot:.5f}" for c, x in sorted(w.items(), key=lambda kv: -kv[1]))
        rows.append({"cohort": label, "market": market, "strategy": s, "entry_date": entry, "picks": picks})
    return rows


def parse(picks):
    w = {}
    for item in picks.split(";"):
        if ":" in item:
            t, x = item.rsplit(":", 1)
            w[t] = float(x)
    return w


def evaluate(frames, indexes, cohorts):
    """{name: {cohort: (pooled net return, is_open)}} (equal weight over markets)."""
    per = {}
    for m, close in frames.items():
        sub = cohorts[cohorts["market"] == m]
        labels = sorted(sub["cohort"].unique())
        idx = indexes.get(m)
        prev = {}
        for i, lab in enumerate(labels):
            rows = sub[sub["cohort"] == lab]
            entry = pd.Timestamp(rows["entry_date"].iloc[0])
            is_open = i + 1 >= len(labels)
            exit_ts = close.index[-1] if is_open else pd.Timestamp(
                sub[sub["cohort"] == labels[i + 1]]["entry_date"].iloc[0])
            if entry >= exit_ts:
                continue
            ratio = close.loc[:exit_ts].iloc[-1].values / close.loc[:entry].iloc[-1].values - 1
            ok = np.isfinite(ratio)
            if ok.sum() < 5:
                continue
            per.setdefault(("EW", lab), []).append((float(ratio[ok].mean()), is_open))
            if idx is not None:
                a, b = idx.asof(entry), idx.asof(exit_ts)
                if a == a and b == b and a:
                    per.setdefault(("Index", lab), []).append((float(b / a - 1), is_open))
            for _, row in rows.iterrows():
                w = {t: x for t, x in parse(row["picks"]).items() if t in close.columns}
                if len(w) < 5:
                    continue
                vals = ratio[close.columns.get_indexer(list(w))]
                good = np.isfinite(vals)
                if good.sum() < 5:
                    continue
                wv = np.where(good, np.array(list(w.values())), 0.0)
                gross = float((wv / wv.sum() * np.where(good, vals, 0.0)).sum())
                pw = prev.get(row["strategy"], {})
                turn = sum(abs(w.get(t, 0.0) - pw.get(t, 0.0)) for t in set(w) | set(pw))
                prev[row["strategy"]] = w
                per.setdefault((row["strategy"], lab), []).append((gross - mt.COST * turn, is_open))
    out = {}
    for (name, lab), lst in per.items():
        out.setdefault(name, {})[lab] = (float(np.mean([x[0] for x in lst])), any(x[1] for x in lst))
    return out


def run(series_cache, bench_series, pre, short, force=False):
    """Returns (telegram_blocks_or_empty, summary_lines). Updates core_cohorts.csv."""
    today = dt.date.today()
    frames = {}
    for m in mt.MARKETS:
        s = series_cache.get(m)
        if s:
            close = mt.build_frame(s)
            if close.shape[1] >= 30 and len(close) >= 300:
                frames[m] = close
    if not frames:
        return [], []
    indexes = {m: (bench_series or {}).get(m) for m in frames}
    cohorts = load()
    have = set(zip(cohorts["cohort"], cohorts["market"]))
    new_rows = []
    for m, close in frames.items():
        label = f"{close.index[-1].year}-{close.index[-1].month:02d}"
        if (label, m) not in have:
            new_rows += make_cohort(label, m, close)
    first = cohorts.empty
    if new_rows:
        cohorts = pd.concat([cohorts, pd.DataFrame(new_rows, columns=COLS)], ignore_index=True)
        cohorts.to_csv(COH, index=False)
    if cohorts.empty:
        return [], []
    res = evaluate(frames, indexes, cohorts)
    labels = sorted({lab for d in res.values() for lab in d})
    ew = res.get("EW", {})
    if not labels or not ew:
        return [], []
    cum = lambda d: float(np.prod([1 + d[l][0] for l in labels if l in d]) - 1) * 100
    last = labels[-1]
    rows = []
    for name in NAMES:
        d = res.get(name)
        if not d:
            continue
        closed = [l for l in labels if l in d and not d[l][1] and l in ew]
        rows.append({"name": name, "cum": cum(d), "mtd": d[last][0] * 100 if last in d else None,
                     "vs_ew": cum(d) - cum(ew), "beat": sum(1 for l in closed if d[l][0] > ew[l][0]), "closed": len(closed)})
    n_closed = max((r["closed"] for r in rows), default=0)
    main = next((r for r in rows if r["name"] == "V1-RAMom"), None)
    ewr = next((r for r in rows if r["name"] == "EW"), None)
    hl = []
    if main and ewr:
        hl.append(f"• استراتژی مومنتوم تعدیل‌شده با نوسان از شروع آزمون {mt.f1(main['cum'])}٪، EW {mt.f1(ewr['cum'])}٪.")
    if not (new_rows or first or force or today.weekday() == 5):
        return [], hl

    t = [f"{'Strategy':<10}{'Cum%':>7}{'MTD%':>7}{'vsEW':>7}{'Beat':>6}", "-" * 37]
    for r in rows:
        t.append(f"{r['name']:<10}{mt.f1(r['cum']):>7}{mt.f1(r['mtd']):>7}"
                 f"{(mt.f1(r['vs_ew']) if r['name'] != 'EW' else '-'):>7}"
                 f"{(str(r['beat']) + '/' + str(r['closed']) if r['name'] not in ('EW', 'Index') else '-'):>6}")
    blocks = [
        f"🏅 <b>آزمون زنده‌ی استراتژی‌های بهتر از RSI/MACD</b> — {today}\n"
        "<i>در بک‌تست ۱۰ ساله، مومنتوم تعدیل‌شده با نوسان (V1-RAMom) بهترین نتیجه را داشت: سالی حدود ۱۰٪ بهتر از نگه‌داشتن همه‌ی سهم‌ها "
        "و در هر دو نیمه‌ی دوره، در حالی که RSI/MACD از EW عقب بود. چون آن آزمون روی داده‌ی گذشته بود، اینجا همان قاعده‌ها از ماه اکتبر ۲۰۲۶ "
        "به‌صورت زنده و کاغذی ثبت می‌شوند: روز اول هر ماه با داده‌ی تا ماه قبل سهم انتخاب می‌شود و نتیجه با کارمزد ۰٫۱٪ دنبال می‌شود.</i>",
        "• <b>V1-RAMom</b>: ۲۰٪ سهمی که رشد ۱۲ماهه‌اش (بدون ماه آخر) نسبت به نوسان خودش بیشتر است، فقط بین سهم‌های بالای میانگین ۲۰۰ روزه\n"
        "• <b>V2-Core</b>: همان همراه با نزدیکی به سقف ۵۲ هفته و وزن معکوس نوسان (در بک‌تست ضعیف‌تر از V1 بود)\n"
        "• <b>TechOld</b>: سهم‌هایی که MACD مثبت و RSI زیر ۷۰ دارند",
        "<i>Cum% بازده از شروع آزمون · MTD% بازده ماه جاری · vsEW اختلاف با EW (مثبت یعنی بهتر از «نگه‌داشتن همه») · "
        "Beat تعداد ماه‌های کامل که از EW بهتر بود از کل ماه‌های کامل</i>",
        "📊 <b>جدول امتیاز</b> (میانگین پنج بازار با وزن مساوی)\n" + pre(t),
    ]
    if n_closed < 6:
        blocks.append(f"⏳ هنوز فقط {n_closed} ماه کامل داریم. با کمتر از ۶ ماه نمی‌شود نتیجه گرفت.")
    if new_rows:
        lines = ["🆕 <b>سبد جدید V1-RAMom</b> (۱۰ سهم اول هر بازار؛ فهرست کامل در core_cohorts.csv)"]
        for r in new_rows:
            if r["strategy"] == "V1-RAMom":
                lines.append(f"{r['market']}: " + "، ".join(html.escape(short(x.rsplit(':', 1)[0]))
                                                          for x in r["picks"].split(";")[:10]))
        if len(lines) > 1:
            blocks.append("\n".join(lines))
    blocks.append("<i>این فهرست‌ها آزمایشی‌اند و توصیه‌ی خرید یا فروش نیستند. بک‌تست قبلی شرکت‌های حذف‌شده را شامل نمی‌شد و بازده را کمی خوش‌بینانه نشان می‌دهد.</i>")
    return blocks, hl
