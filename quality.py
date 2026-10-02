"""
Two extra daily Telegram messages:
  1) RSI/MACD buy signals filtered by Warren Buffett's criteria (auto-computable part of the scorecard)
  2) RSI/MACD buy signals filtered by CANSLIM (C, A, N, L, I + market direction M)
Fundamentals come free from Yahoo Finance and are cached weekly in quality_cache.csv.
"""
import datetime as dt
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "quality_cache.csv")
STOCK_MARKETS = ("US", "JP", "IN", "TW", "CN")
MARKET_FA = {"US": "🇺🇸 آمریکا", "JP": "🇯🇵 ژاپن", "IN": "🇮🇳 هند", "TW": "🇹🇼 تایوان", "CN": "🇨🇳 چین"}
INDEX = {"US": "^GSPC", "JP": "^N225", "IN": "^NSEI", "TW": "^TWII", "CN": "000300.SS"}
MAX_AGE_DAYS = 7
TIME_BUDGET = 12 * 60
BUFFETT_MIN = 60      # minimum Buffett score (%) to be listed
TOP = 10              # rows per market


def _num(v):
    try:
        f = float(v)
        return None if f != f or f in (float("inf"), float("-inf")) else f
    except (TypeError, ValueError):
        return None


def _row(df, names):
    if df is None or getattr(df, "empty", True):
        return None
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce").dropna()
            if isinstance(s, pd.Series) and len(s):
                return s.sort_index()  # oldest -> newest
    return None


def fetch_quality(ticker):
    t = yf.Ticker(ticker)
    out = {"ticker": ticker, "fetched_at": dt.date.today().isoformat()}

    def safe(attr):
        try:
            return getattr(t, attr)
        except Exception:
            return None

    info = safe("info") or {}
    inc, bal, cf = safe("income_stmt"), safe("balance_sheet"), safe("cashflow")
    ni = _row(inc, ["Net Income", "Net Income Common Stockholders"])
    eps = _row(inc, ["Diluted EPS", "Basic EPS"])
    eq = _row(bal, ["Stockholders Equity", "Common Stock Equity"])
    debt = _row(bal, ["Total Debt"])
    ltd = _row(bal, ["Long Term Debt"])
    ta = _row(bal, ["Total Assets"])
    fcf = _row(cf, ["Free Cash Flow"])
    capex = _row(cf, ["Capital Expenditure"])

    if ni is not None and eq is not None:
        j = ni.index.intersection(eq.index)
        roe = (ni[j] / eq[j] * 100).replace([np.inf, -np.inf], np.nan).dropna()
        roe = roe[eq[j] > 0] if len(roe) else roe
        if len(roe):
            out["roe_avg"] = round(roe.mean(), 1)
    if ni is not None:
        out["years"] = len(ni)
        out["loss_years"] = int((ni <= 0).sum())
        out["drop_years"] = int(((ni.pct_change() < -0.2) & (ni.shift(1) > 0)).sum())
    base = eps if eps is not None and len(eps) >= 3 else ni
    if base is not None and len(base) >= 3 and base.iloc[0] > 0 and base.iloc[-1] > 0:
        out["eps_cagr"] = round(((base.iloc[-1] / base.iloc[0]) ** (1 / (len(base) - 1)) - 1) * 100, 1)
    if debt is not None and eq is not None and eq.iloc[-1] > 0:
        out["de"] = round(debt.iloc[-1] / eq.iloc[-1], 2)
    if ni is not None and ni.iloc[-1] > 0:
        d = ltd if ltd is not None else debt
        if d is not None:
            out["payback"] = round(d.iloc[-1] / ni.iloc[-1], 1)
        if capex is not None:
            out["capex_ratio"] = round(abs(capex.iloc[-1]) / ni.iloc[-1] * 100, 0)
    if fcf is not None and len(fcf) >= 2:
        out["fcf_all_pos"] = bool((fcf > 0).all())
        out["fcf_rising"] = bool(fcf.iloc[-1] > fcf.iloc[0])
    if ni is not None and ta is not None and ta.iloc[-1] > 0:
        out["roa"] = round(ni.iloc[-1] / ta.iloc[-1] * 100, 2)
    pm = _num(info.get("profitMargins"))
    out["margin"] = round(pm * 100, 1) if pm is not None else None
    out["pe"] = _num(info.get("trailingPE"))
    q = _num(info.get("earningsQuarterlyGrowth"))
    out["eps_q"] = round(q * 100, 1) if q is not None else None
    inst = _num(info.get("heldPercentInstitutions"))
    out["inst"] = round(inst * 100, 1) if inst is not None else None
    out["sector"] = str(info.get("sector") or "")
    return out


def load_quality(tickers):
    cache = pd.read_csv(CACHE, dtype={"ticker": str}) if os.path.exists(CACHE) else pd.DataFrame()
    rows = {r["ticker"]: r for r in cache.to_dict("records")} if len(cache) else {}
    today = dt.date.today()

    def age(t):
        try:
            return (today - dt.date.fromisoformat(str(rows[t]["fetched_at"]))).days
        except Exception:
            return 10 ** 6

    need = [t for t in tickers if age(t) >= MAX_AGE_DAYS]
    print(f"quality: fetching {len(need)} of {len(tickers)}")
    start = time.time()
    with ThreadPoolExecutor(4) as ex:
        for i in range(0, len(need), 40):
            if time.time() - start > TIME_BUDGET:
                print("quality: time budget reached")
                break
            for res in ex.map(fetch_quality, need[i:i + 40]):
                rows[res["ticker"]] = res
    out = pd.DataFrame(list(rows.values()))
    out.to_csv(CACHE, index=False)
    return {r["ticker"]: r for r in out.to_dict("records")}


def buffett_score(r):
    """Auto-computable part of the Buffett scorecard. Returns % of applicable points, or None if knocked out."""
    g = lambda k: _num(r.get(k))
    loss, de = g("loss_years"), g("de")
    fin = "financ" in str(r.get("sector", "")).lower()
    if loss is not None and loss >= 2:
        return None
    if not fin and de is not None and de > 2:
        return None
    pts = mx = 0

    def add(val, rules, cap):
        nonlocal pts, mx
        if val is None:
            return
        mx += cap
        for test, p in rules:
            if test(val):
                pts += p
                return

    add(g("roe_avg"), [(lambda v: v >= 20, 15), (lambda v: v >= 15, 10), (lambda v: v >= 10, 5)], 15)
    add(g("margin"), [(lambda v: v >= 20, 5), (lambda v: v >= 10, 3)], 5)
    add(g("eps_cagr"), [(lambda v: v >= 15, 10), (lambda v: v >= 10, 7), (lambda v: v >= 5, 4)], 10)
    if loss is not None:
        drops = g("drop_years") or 0
        add(1, [(lambda v: loss == 0 and drops == 0, 10), (lambda v: loss == 0 and drops <= 1, 5)], 10)
    if fin:
        add(g("roa"), [(lambda v: v >= 1.5, 15), (lambda v: v >= 1, 10), (lambda v: v >= 0.5, 5)], 15)
    else:
        add(de, [(lambda v: v < 0.5, 10), (lambda v: v < 1, 5)], 10)
        add(g("payback"), [(lambda v: v < 3, 5), (lambda v: v < 5, 2)], 5)
        if r.get("fcf_all_pos") is not None and str(r.get("fcf_all_pos")) != "nan":
            allpos = str(r.get("fcf_all_pos")) == "True"
            rising = str(r.get("fcf_rising")) == "True"
            add(1, [(lambda v: allpos and rising, 10), (lambda v: allpos, 5)], 10)
        add(g("capex_ratio"), [(lambda v: v < 50, 5), (lambda v: v < 75, 2)], 5)
    pe = g("pe")
    add(pe if pe is not None else 999, [(lambda v: 0 < v < 15, 15), (lambda v: 0 < v < 25, 8)], 15)
    if mx < 50:  # not enough data to judge
        return None
    return round(pts / mx * 100)


def market_trend(download_all):
    data = download_all(list(INDEX.values()))
    out = {}
    for m, sym in INDEX.items():
        s = data.get(sym)
        if s is None or len(s) < 200:
            continue
        v = s.values.astype(float)
        out[m] = bool(v[-1] > v[-50:].mean() and v[-50:].mean() > v[-200:].mean())
    return out


def sig_code(r):
    d, w = r.daily_signal == "BUY", r.weekly_signal == "BUY"
    if d and w:
        return "DW"
    if d:
        return "D*" if r.aligned else "D"
    return "W"


def build(df, download_all, pre, short, fmt_price):
    """Returns two lists of message blocks: [buffett_blocks, canslim_blocks]."""
    today = dt.date.today().strftime("%Y-%m-%d")
    stocks = df[df["market"].isin(STOCK_MARKETS)].copy()
    # relative strength: 6-month return percentile within each market (computed on all scanned stocks)
    stocks["rs"] = stocks.groupby("market")["ret_6m"].rank(pct=True) * 100
    buys = stocks[(stocks.daily_signal == "BUY") | (stocks.weekly_signal == "BUY")].copy()
    q = load_quality(list(buys["ticker"]))
    trend = market_trend(download_all)

    # fundamental quarterly growth from the existing ranking cache (fallback for C)
    fq = {}
    fpath = os.path.join(HERE, "fundamentals.csv")
    if os.path.exists(fpath):
        f = pd.read_csv(fpath, dtype={"ticker": str})
        fq = dict(zip(f["ticker"], pd.to_numeric(f["profit_growth"], errors="coerce")))

    rows = []
    for r in buys.itertuples():
        qr = q.get(r.ticker, {})
        bscore = buffett_score(qr) if qr else None
        epsq = _num(qr.get("eps_q")) if qr else None
        if epsq is None:
            epsq = _num(fq.get(r.ticker))
        checks = {
            "C": None if epsq is None else epsq >= 25,
            "A": None if _num(qr.get("eps_cagr")) is None else
                 (_num(qr.get("eps_cagr")) >= 25 and (_num(qr.get("roe_avg")) or 0) >= 17),
            "N": None if _num(r.high_gap) is None else _num(r.high_gap) >= -15,
            "L": None if _num(r.rs) is None else _num(r.rs) >= 80,
            "I": None if _num(qr.get("inst")) is None else _num(qr.get("inst")) >= 20,
        }
        avail = [v for v in checks.values() if v is not None]
        passed = sum(1 for v in avail if v)
        rows.append({"market": r.market, "ticker": r.ticker, "sig": sig_code(r), "close": r.close,
                     "buf": bscore, "roe": _num(qr.get("roe_avg")), "de": _num(qr.get("de")),
                     "pe": _num(qr.get("pe")), "checks": checks, "passed": passed, "avail": len(avail),
                     "epsq": epsq, "rs": _num(r.rs)})
    res = pd.DataFrame(rows)

    def f0(v, fmt="{:.0f}"):
        return "-" if v is None or v != v else fmt.format(v)

    # ---------------- message 1: Buffett ----------------
    b_blocks = [f"🧠 <b>سیگنال خرید + معیار وارن بافت</b> — {today}\n"
                "<i>سهم‌هایی که امروز سیگنال خرید MACD/RSI گرفته‌اند و از نظر روش بافت هم شرکت باکیفیتی هستند "
                f"(امتیاز بافت حداقل {BUFFETT_MIN} از ۱۰۰). "
                "Buf = امتیاز بافت · ROE = بازده حقوق صاحبان سهم (٪) · D/E = نسبت بدهی به سرمایه · PE = نسبت قیمت به سود · "
                "Sig: D = خرید روزانه، W = خرید هفتگی، *= هم‌جهت با روند هفتگی</i>"]
    good = res[res["buf"].notna() & (res["buf"] >= BUFFETT_MIN)] if len(res) else res
    if good.empty:
        b_blocks.append(f"امروز هیچ سهمی هم سیگنال خرید نگرفت و هم امتیاز بافت بالای {BUFFETT_MIN} داشت.")
    for m in STOCK_MARKETS:
        sub = good[good["market"] == m].sort_values("buf", ascending=False).head(TOP) if len(good) else good
        if sub.empty:
            continue
        t = [f"{'Symbol':<9}{'Sig':<4}{'Buf':>4}{'ROE':>5}{'D/E':>5}{'PE':>5}", "-" * 32]
        for r in sub.itertuples():
            t.append(f"{short(r.ticker)[:9]:<9}{r.sig:<4}{f0(r.buf):>4}{f0(r.roe):>5}"
                     f"{f0(r.de, '{:.1f}'):>5}{f0(r.pe):>5}")
        b_blocks.append(f"{MARKET_FA[m]}\n" + pre(t))
    b_blocks.append("<i>امتیاز بافت فقط بخش قابل محاسبه‌ی جدول است. مزیت رقابتی و کیفیت مدیریت را خودتان بررسی کنید. "
                    "این فهرست توصیه‌ی خرید نیست.</i>")

    # ---------------- message 2: CANSLIM ----------------
    trend_lines = []
    for m in STOCK_MARKETS:
        if m in trend:
            trend_lines.append(f"{MARKET_FA[m]}: " + ("بازار در روند صعودی است ✅" if trend[m]
                                                      else "بازار در روند صعودی نیست ⚠️ (روش CANSLIM در این حالت خرید را توصیه نمی‌کند)"))
    c_blocks = [f"🚀 <b>سیگنال خرید + روش CANSLIM</b> — {today}\n"
                "<i>سهم‌هایی که امروز سیگنال خرید MACD/RSI گرفته‌اند و بیشتر شرط‌های CANSLIM را هم دارند. "
                "در ستون CANLI هر حرف یعنی آن شرط برقرار است و «-» یعنی برقرار نیست: "
                "C رشد سود فصلی بالای ۲۵٪ · A رشد سود سالانه بالای ۲۵٪ · N نزدیک سقف قیمت یک‌ساله · "
                "L قوی‌تر از ۸۰٪ سهام بازار خودش · I خرید صندوق‌ها و نهادها. "
                "EPSq = رشد سود فصلی (٪) · RS = رتبه‌ی قدرت قیمت از ۱۰۰</i>",
                "📈 <b>وضعیت بازارها (حرف M)</b>\n" + "\n".join(trend_lines)]
    if len(res):
        cand = res[(res["avail"] >= 3) & (res["passed"] >= res["avail"] - 1) & (res["passed"] >= 3)
                   & res["checks"].map(lambda c: c["C"] is not False)]
    else:
        cand = res
    if cand.empty:
        c_blocks.append("امروز هیچ سهمی هم سیگنال خرید نگرفت و هم شرط‌های CANSLIM را داشت.")
    for m in STOCK_MARKETS:
        sub = cand[cand["market"] == m].sort_values(["passed", "rs"], ascending=False).head(TOP) if len(cand) else cand
        if sub.empty:
            continue
        t = [f"{'Symbol':<9}{'Sig':<4}{'CANLI':<6}{'EPSq':>6}{'RS':>4}", "-" * 29]
        for r in sub.itertuples():
            word = "".join(k if r.checks[k] else "-" for k in "CANLI")
            t.append(f"{short(r.ticker)[:9]:<9}{r.sig:<4}{word:<6}{f0(r.epsq, '{:+.0f}'):>6}{f0(r.rs):>4}")
        c_blocks.append(f"{MARKET_FA[m]}\n" + pre(t))

    # stocks that pass all three filters
    both = cand[cand["buf"].notna() & (cand["buf"] >= BUFFETT_MIN)] if len(cand) else cand
    if len(both):
        names = "، ".join(f"{short(r.ticker)} ({MARKET_FA[r.market].split()[-1]})" for r in both.itertuples())
        c_blocks.append("⭐ <b>هر سه با هم</b> (سیگنال خرید + معیار بافت + CANSLIM):\n" + names)
    c_blocks.append("<i>شرط S (عرضه و تقاضای سهم) خودکار بررسی نمی‌شود. این فهرست توصیه‌ی خرید نیست.</i>")
    return [b_blocks, c_blocks]
