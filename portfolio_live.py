"""
💼 Suggested portfolio (paper trading, tracked from the first run):
  70% core  = a global equity index fund (tracked through VT, a total-world ETF, as a stand-in)
  30% sleeve = the top 8 stocks of each market from the V1-RAMom strategy (core_cohorts.csv), equal weight
The sleeve is renewed when a new monthly cohort appears (cost 0.1% per side on the sleeve turnover).
Returns use local-currency prices (currency moves are ignored); the opening purchase cost is not counted.
State: portfolio_state.csv (which picks since which date) and portfolio_nav.csv (daily value).
"""
import datetime as dt
import html
import os

import numpy as np
import pandas as pd

import core_live
import method_test as mt

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "portfolio_state.csv")
NAV_CSV = os.path.join(HERE, "portfolio_nav.csv")
COLS = ["seg_start", "cohort", "picks"]
CORE_W, SLEEVE_W = 0.70, 0.30
PER_MARKET = 8
COST = mt.COST


def load_state():
    if os.path.exists(STATE):
        return pd.read_csv(STATE, dtype=str, keep_default_na=False).reindex(columns=COLS).fillna("")
    return pd.DataFrame(columns=COLS)


def latest_picks(cohorts, frames):
    """Top picks of the newest V1-RAMom cohort of every market: ([(market, ticker)], label, entry_date)."""
    out, label, entry = [], None, None
    v1 = cohorts[cohorts["strategy"] == "V1-RAMom"]
    for m in frames:
        sub = v1[v1["market"] == m]
        if sub.empty:
            continue
        lab = sub["cohort"].max()
        row = sub[sub["cohort"] == lab].iloc[0]
        tk = [t.rsplit(":", 1)[0] for t in row["picks"].split(";") if ":" in t]
        tk = [t for t in tk if t in frames[m].columns][:PER_MARKET]
        out += [(m, t) for t in tk]
        label = lab if label is None else max(label, lab)
        entry = row["entry_date"] if entry is None else max(entry, row["entry_date"])
    return out, label, entry


def build_nav(segs, frames, vt, mk_of):
    """segs: [{'start': Timestamp, 'picks': [tickers]}]. Returns DataFrame(plan, core, sleeve) and last-segment ratios."""
    dates = vt.index[vt.index >= segs[0]["start"]]
    plan, core, sleeve = [], [], []
    nav0 = sleeve0 = 100.0
    core0 = float(vt.asof(segs[0]["start"]))
    prev_w, ratios = {}, {}
    for i, seg in enumerate(segs):
        s = seg["start"]
        e = segs[i + 1]["start"] if i + 1 < len(segs) else dates[-1]
        idx = dates[(dates >= s) & (dates <= e)] if i == 0 else dates[(dates > s) & (dates <= e)]
        if len(idx) == 0:
            continue
        cols = {}
        for t in seg["picks"]:
            ser = frames[mk_of[t]][t]
            p0 = ser.asof(s)
            if p0 == p0 and p0:
                cols[t] = ser.reindex(idx, method="ffill") / p0
        w = {t: 1.0 / len(cols) for t in cols}
        turn = sum(abs(w.get(t, 0.0) - prev_w.get(t, 0.0)) for t in set(w) | set(prev_w)) if i > 0 else 0.0
        prev_w = w
        nav0 *= 1 - SLEEVE_W * COST * turn
        sleeve0 *= 1 - COST * turn
        sl = pd.DataFrame(cols).mean(axis=1, skipna=True).reindex(idx).ffill().fillna(1.0)
        cr = vt.reindex(idx, method="ffill") / float(vt.asof(s))
        plan.append(nav0 * (CORE_W * cr + SLEEVE_W * sl))
        sleeve.append(sleeve0 * sl)
        core.append(100.0 * vt.reindex(idx, method="ffill") / core0)
        nav0, sleeve0 = float(plan[-1].iloc[-1]), float(sleeve[-1].iloc[-1])
        ratios = {t: float(c.iloc[-1]) for t, c in cols.items()}
    out = pd.DataFrame({"plan": pd.concat(plan), "core": pd.concat(core), "sleeve": pd.concat(sleeve)})
    return out, ratios


def f1(v, fmt="{:+.1f}"):
    return mt.f1(v, fmt)


def run(series_cache, download_all, pre, short, force=False):
    """Returns (telegram_blocks, summary_lines, state_changed)."""
    today = dt.date.today()
    frames = {}
    for m in mt.MARKETS:
        s = series_cache.get(m)
        if s:
            fr = mt.build_frame(s)
            if fr.shape[1] >= 30 and len(fr) >= 100:
                frames[m] = fr
    cohorts = core_live.load()
    vt = (download_all(["VT"]).get("VT"))
    if not frames or cohorts.empty or vt is None or len(vt) < 50:
        return [], [], False
    vt = vt.copy()
    ix = pd.to_datetime(vt.index)
    vt.index = (ix.tz_localize(None) if getattr(ix, "tz", None) is not None else ix).normalize()
    vt = vt[~vt.index.duplicated(keep="last")].astype(float).sort_index()
    picks, label, entry = latest_picks(cohorts, frames)
    if len(picks) < 8:
        return [], [], False
    mk_of = {t: m for m, t in picks}
    state = load_state()
    changed = False
    if state.empty:
        state = pd.DataFrame([{"seg_start": vt.index[-1].date().isoformat(), "cohort": label,
                               "picks": ";".join(t for _, t in picks)}], columns=COLS)
        changed = True
    elif state["cohort"].iloc[-1] != label:
        start = max(pd.Timestamp(entry), pd.Timestamp(state["seg_start"].iloc[-1]) + pd.Timedelta(days=1))
        state = pd.concat([state, pd.DataFrame([{"seg_start": start.date().isoformat(), "cohort": label,
                                                 "picks": ";".join(t for _, t in picks)}], columns=COLS)],
                          ignore_index=True)
        changed = True
    if changed:
        state.to_csv(STATE, index=False)
    # every ticker ever held must be priced
    for p in state["picks"]:
        for t in p.split(";"):
            if t and t not in mk_of:
                for m, fr in frames.items():
                    if t in fr.columns:
                        mk_of[t] = m
    segs = [{"start": pd.Timestamp(r["seg_start"]), "picks": [t for t in r["picks"].split(";") if t in mk_of]}
            for _, r in state.iterrows()]
    nav, ratios = build_nav(segs, frames, vt, mk_of)
    out_csv = nav.round(4)
    out_csv.index.name = "date"
    out_csv.to_csv(NAV_CSV)
    last = nav.index[-1]
    first_of_month = pd.Timestamp(last.year, last.month, 1)

    def stats(col):
        s = nav[col]
        before = s[s.index < first_of_month]
        base = float(before.iloc[-1]) if len(before) else float(s.iloc[0])
        return ((s.iloc[-1] / s.iloc[-2] - 1) * 100 if len(s) > 1 else 0.0,
                (s.iloc[-1] / base - 1) * 100, (s.iloc[-1] / s.iloc[0] - 1) * 100)

    n_cur = len(segs[-1]["picks"])
    rows = {"Plan 70/30": stats("plan"), "Core (VT)": stats("core"), f"Sleeve ({n_cur})": stats("sleeve")}
    plan_s, core_s = rows["Plan 70/30"][2], rows["Core (VT)"][2]
    t = [f"{'Portfolio':<13}{'Day%':>6}{'MTD%':>7}{'Since%':>8}{'vsCore':>8}", "-" * 42]
    for name, (d, m_, s_) in rows.items():
        t.append(f"{name:<13}{f1(d):>6}{f1(m_):>7}{f1(s_):>8}{(f1(s_ - core_s) if name != 'Core (VT)' else '-'):>8}")
    since_date = nav.index[0].date().isoformat()
    cur = segs[-1]
    blocks = [
        f"💼 <b>سبد پیشنهادی</b> — {today}\n"
        f"<i>سبد کاغذی از {since_date} (آخرین قیمت پایانی روز شروع) ثبت شده: ۷۰٪ هسته (صندوق شاخص جهانی؛ به‌جایش VT را دنبال می‌کنیم) + "
        f"۳۰٪ بخش فعال (۸ سهم برتر هر بازار از استراتژی مومنتوم تعدیل‌شده با نوسان، وزن مساوی). بخش فعال با آمدن سبد ماهانه‌ی جدید عوض می‌شود "
        "(کارمزد ۰٫۱٪ برای هر خرید و فروش). بازده‌ها به پول محلی هر بازار است و نوسان ارز حساب نمی‌شود. "
        "vsCore یعنی چند امتیاز بالاتر یا پایین‌تر از «فقط صندوق شاخص جهانی».</i>",
        f"📊 <b>بازده سبد</b> — از {since_date[5:]} ({(today - nav.index[0].date()).days} روز)\n" + pre(t),
    ]
    mv = sorted(((r, t_) for t_, r in ratios.items()), reverse=True)
    if mv:
        def fm(lst):
            return "، ".join(f"{html.escape(short(tk))} {(r - 1) * 100:+.1f}٪" for r, tk in lst)
        blocks.append("🏆 بهترین‌های بخش فعال از شروع این سبد: " + fm(mv[:3]) + "\n📉 ضعیف‌ترین‌ها: " + fm(mv[::-1][:3]))
    if changed or force or today.weekday() == 5:
        hold = [f"<b>سهم‌های بخش فعال (سبد {cur['start'].date()})</b> — هر کدام ≈ {SLEEVE_W / max(len(cur['picks']), 1) * 100:.2f}٪ کل سبد"]
        for m in mt.MARKETS:
            tk = [short(t) for t in cur["picks"] if mk_of.get(t) == m]
            if tk:
                hold.append(f"{m}: " + "، ".join(html.escape(x) for x in tk))
        blocks.append("\n".join(hold))
    ncl = len(state)
    if ncl == 1:
        blocks.append("⏳ این سبد تازه شروع شده؛ چند ماه طول می‌کشد تا مقایسه‌اش با «فقط صندوق جهانی» معنا پیدا کند.")
    blocks.append("<i>این سبد آزمایشی است و توصیه‌ی خرید یا فروش نیست. بخش فعال مومنتوم گاهی ناگهان و شدید افت می‌کند.</i>")
    hl = [f"• سبد پیشنهادی از {since_date}: {f1(plan_s)}٪ (فقط صندوق جهانی {f1(core_s)}٪)."]
    return blocks, hl, changed
