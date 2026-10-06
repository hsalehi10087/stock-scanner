"""
Two extra daily Telegram messages:
  1) RSI/MACD buy signals filtered by Warren Buffett's criteria (auto-computable part of the scorecard)
  2) RSI/MACD buy signals filtered by CANSLIM (C, A, N, L, I + market direction M)
Fundamentals come free from Yahoo Finance and are cached weekly in quality_cache.csv.
Each list's performance since a stock entered it is tracked in quality_track.csv.
"""
import datetime as dt
import html
import os
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf

import bench

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


TRACK = os.path.join(HERE, "quality_track.csv")
TCOLS = ["list", "market", "ticker", "added_date", "entry_price", "last_date", "last_price",
         "return_pct", "max_return", "min_return", "days", "status"]
HOLD_DAYS = 60   # each stock is followed for 60 days after it enters a list


def track(lists, prices):
    """Record the day/price each stock enters a list, and update its return every day."""
    if os.path.exists(TRACK):
        w = pd.read_csv(TRACK, dtype=str, keep_default_na=False).reindex(columns=TCOLS).fillna("")
    else:
        w = pd.DataFrame(columns=TCOLS)
    w = w.astype(object)
    for i in w.index[w["status"] == "OPEN"]:
        key = (w.at[i, "market"], w.at[i, "ticker"])
        if key not in prices or not _num(w.at[i, "entry_price"]):
            continue
        p, d = prices[key]
        ret = (p / float(w.at[i, "entry_price"]) - 1) * 100
        w.at[i, "last_price"], w.at[i, "last_date"] = p, d
        w.at[i, "return_pct"] = round(ret, 2)
        w.at[i, "max_return"] = round(max(_num(w.at[i, "max_return"]) or 0, ret), 2)
        w.at[i, "min_return"] = round(min(_num(w.at[i, "min_return"]) or 0, ret), 2)
        days = (pd.Timestamp(d) - pd.Timestamp(w.at[i, "added_date"])).days
        w.at[i, "days"] = days
        if days >= HOLD_DAYS:
            w.at[i, "status"] = "CLOSED"
    open_keys = set(zip(w.loc[w["status"] == "OPEN", "list"], w.loc[w["status"] == "OPEN", "market"],
                        w.loc[w["status"] == "OPEN", "ticker"]))
    new = []
    for name, keys in lists.items():
        for m, t in keys:
            if (name, m, t) not in open_keys and (m, t) in prices:
                p, d = prices[(m, t)]
                new.append({"list": name, "market": m, "ticker": t, "added_date": d, "entry_price": p,
                            "last_date": d, "last_price": p, "return_pct": 0.0, "max_return": 0.0,
                            "min_return": 0.0, "days": 0, "status": "OPEN"})
                open_keys.add((name, m, t))
    if new:
        w = pd.concat([w, pd.DataFrame(new, columns=TCOLS).astype(object)], ignore_index=True)
    w.to_csv(TRACK, index=False)
    return w


def open_date(w, name, m, t):
    sub = w[(w["list"] == name) & (w["market"] == m) & (w["ticker"] == t) & (w["status"] == "OPEN")]
    return str(sub["added_date"].iloc[-1])[5:] if len(sub) else "-"


def open_return(w, name, m, t):
    sub = w[(w["list"] == name) & (w["market"] == m) & (w["ticker"] == t) & (w["status"] == "OPEN")]
    return _num(sub["return_pct"].iloc[-1]) if len(sub) else None


def perf_block(w, name, short):
    title = "📈 <b>بازدهی این فهرست از روز ورود هر سهم</b>"
    h = w[w["list"] == name].copy()
    h["d"] = pd.to_numeric(h["days"], errors="coerce").fillna(0)
    h["r"] = pd.to_numeric(h["return_pct"], errors="coerce").fillna(0)
    h = h[h["d"] >= 1].copy()
    h["b"] = [bench.ret(m, a, l) for m, a, l in zip(h["market"], h["added_date"], h["last_date"])]
    h["x"] = h["r"] - pd.to_numeric(h["b"], errors="coerce")
    if h.empty:
        return (f"{title}\nتاریخچه‌ی این فهرست از امروز شروع شد. از اسکن بعدی، بازدهی هر سهم "
                "از روزی که وارد فهرست شده اینجا نمایش داده می‌شود.")
    rows = [f"{'Group':<8}{'N':>4}{'Win%':>6}{'Avg%':>7}{'Exc%':>7}", "-" * 32]
    for label, sub in (("All", h), ("Open", h[h["status"] == "OPEN"]), ("Closed", h[h["status"] == "CLOSED"])):
        if len(sub):
            rows.append(f"{label:<8}{len(sub):>4}{(sub['r'] > 0).mean() * 100:>6.0f}"
                        f"{sub['r'].mean():>+7.1f}{('-' if sub['x'].isna().all() else format(sub['x'].mean(), '+.1f')):>7}")
    out = [title, "<i>All = همه‌ی سهم‌هایی که تا حالا وارد این فهرست شده‌اند · Open = هنوز در دوره‌ی ۶۰ روزه‌ی پیگیری · "
           "Win% = درصد سهم‌هایی که سود داده‌اند · Avg% = میانگین بازده · Exc% = برتری نسبت به شاخص بازار همان کشور در همان مدت</i>",
           "<pre>" + "\n".join(rows) + "</pre>"]

    def table(sub):
        t = [f"{'Symbol':<9}{'Mkt':<4}{'Date':<6}{'Ret%':>7}{'Exc%':>7}", "-" * 33]
        for r in sub.itertuples():
            t.append(f"{short(r.ticker)[:9]:<9}{r.market:<4}{str(r.added_date)[5:]:<6}{r.r:>+7.1f}"
                     f"{('-' if r.x != r.x else format(r.x, '+.1f')):>7}")
        return "<pre>" + html.escape("\n".join(t)) + "</pre>"

    op = h[h["status"] == "OPEN"].sort_values("r", ascending=False)
    if len(op):
        out += ["🏆 <b>بهترین‌ها</b>", table(op.head(5))]
        if len(op) > 5:  # show the weakest ones that are not already in the best list
            out += ["📉 <b>ضعیف‌ترین‌ها</b>", table(op.tail(min(5, len(op) - 5)).iloc[::-1])]
    return "\n".join(out)


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

    # which stocks enter each list today
    good = res[res["buf"].notna() & (res["buf"] >= BUFFETT_MIN)] if len(res) else res
    if len(res):
        cand = res[(res["avail"] >= 3) & (res["passed"] >= res["avail"] - 1) & (res["passed"] >= 3)
                   & res["checks"].map(lambda c: c["C"] is not False)]
    else:
        cand = res
    both = cand[cand["buf"].notna() & (cand["buf"] >= BUFFETT_MIN)] if len(cand) else cand
    prices = {(r.market, r.ticker): (float(r.close), r.last_date) for r in df.itertuples()}
    keys = lambda d: list(zip(d["market"], d["ticker"])) if len(d) else []
    tw = track({"buffett": keys(good), "canslim": keys(cand), "all3": keys(both)}, prices)

    # ---------------- message 1: Buffett ----------------
    b_blocks = [f"🧠 <b>سیگنال خرید + معیار وارن بافت</b> — {today}\n"
                "<i>سهم‌هایی که امروز سیگنال خرید MACD/RSI گرفته‌اند و از نظر روش بافت هم شرکت باکیفیتی هستند "
                f"(امتیاز بافت حداقل {BUFFETT_MIN} از ۱۰۰). "
                "Buf = امتیاز بافت · ROE = بازده حقوق صاحبان سهام (٪) · D/E = نسبت بدهی به سرمایه · PE = نسبت قیمت به سود · "
                "Sig: D = خرید روزانه، W = خرید هفتگی، *= هم‌جهت با روند هفتگی</i>"]
    if good.empty:
        b_blocks.append(f"امروز هیچ سهمی هم سیگنال خرید نگرفت و هم امتیاز بافت بالای {BUFFETT_MIN} داشت.")
    for m in STOCK_MARKETS:
        sub = good[good["market"] == m].sort_values("buf", ascending=False).head(TOP) if len(good) else good
        if sub.empty:
            continue
        t = [f"{'Symbol':<8}{'Sig':<3}{'Buf':>4}{'ROE':>4}{'D/E':>5}{'PE':>4}{'Ret%':>6}", "-" * 34]
        for r in sub.itertuples():
            ret = open_return(tw, "buffett", r.market, r.ticker)
            t.append(f"{short(r.ticker)[:8]:<8}{r.sig:<3}{f0(r.buf):>4}{f0(r.roe):>4}"
                     f"{f0(r.de, '{:.1f}'):>5}{f0(r.pe):>4}{f0(ret, '{:+.1f}'):>6}")
        b_blocks.append(f"{MARKET_FA[m]}\n" + pre(t))
    b_blocks.append(perf_block(tw, "buffett", short))
    b_blocks.append("<i>Ret% = بازده هر سهم از روزی که وارد این فهرست شده. "
                    "امتیاز بافت فقط بخش قابل محاسبه‌ی جدول است. مزیت رقابتی و کیفیت مدیریت را خودتان بررسی کنید. "
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
    if cand.empty:
        c_blocks.append("امروز هیچ سهمی هم سیگنال خرید نگرفت و هم شرط‌های CANSLIM را داشت.")
    for m in STOCK_MARKETS:
        sub = cand[cand["market"] == m].sort_values(["passed", "rs"], ascending=False).head(TOP) if len(cand) else cand
        if sub.empty:
            continue
        t = [f"{'Symbol':<9}{'Sig':<4}{'CANLI':<6}{'EPSq':>5}{'RS':>4}{'Ret%':>6}", "-" * 34]
        for r in sub.itertuples():
            word = "".join(k if r.checks[k] else "-" for k in "CANLI")
            ret = open_return(tw, "canslim", r.market, r.ticker)
            t.append(f"{short(r.ticker)[:9]:<9}{r.sig:<4}{word:<6}{f0(r.epsq, '{:+.0f}'):>5}{f0(r.rs):>4}"
                     f"{f0(ret, '{:+.1f}'):>6}")
        c_blocks.append(f"{MARKET_FA[m]}\n" + pre(t))

    # stocks that pass all three filters
    if len(both):
        def nm(r):
            ret = open_return(tw, "all3", r.market, r.ticker)
            return f"{html.escape(short(r.ticker))} ({MARKET_FA[r.market].split()[-1]}، {f0(ret, '{:+.1f}')}٪)"
        names = "، ".join(nm(r) for r in both.itertuples())
        c_blocks.append("⭐ <b>هر سه با هم</b> (سیگنال خرید + معیار بافت + CANSLIM):\n" + names)
    c_blocks.append(perf_block(tw, "canslim", short))
    c_blocks.append("⭐ " + perf_block(tw, "all3", short).replace("📈 <b>بازدهی این فهرست", "<b>بازدهی فهرست «هر سه با هم»", 1))
    c_blocks.append("<i>Ret% = بازده هر سهم از روزی که وارد این فهرست شده. شرط S (عرضه و تقاضای سهم) خودکار بررسی نمی‌شود. این فهرست توصیه‌ی خرید نیست.</i>")
    hl = []
    if len(good):
        hl.append(f"• {len(good)} سهم هم سیگنال خرید دارند و هم از نظر معیار بافت امتیاز بالای {BUFFETT_MIN} گرفته‌اند.")
    else:
        hl.append("• امروز سهمی همزمان سیگنال خرید و امتیاز بالای بافت نداشت.")
    hl.append(f"• {len(cand)} سهم سیگنال خرید دارند و بیشتر شرط‌های CANSLIM را هم دارند." if len(cand)
              else "• امروز سهمی همزمان سیگنال خرید و شرط‌های CANSLIM نداشت.")
    if len(both):
        hl.append("• ⭐ هر سه فیلتر با هم: " + "، ".join(html.escape(short(r.ticker)) for r in both.head(6).itertuples()) + ".")
    weak = [MARKET_FA[m] for m in STOCK_MARKETS if m in trend and not trend[m]]
    if weak:
        hl.append("• بازار این کشورها در روند صعودی نیست و روش CANSLIM در آن‌ها احتیاط می‌گوید: " + "، ".join(weak) + ".")
    return [b_blocks, c_blocks, hl]
