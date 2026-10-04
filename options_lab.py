"""
Stock-option strategies: paper trading with REAL quotes from Yahoo, plus an approximate index backtest.

Why paper trading: free historical option prices do not exist, so the only honest test is to write the trade
down at today's real bid/ask and follow it day by day. Fills are conservative (buy at ask, sell at bid).

Strategies (rules fixed in advance, nothing is tuned):
  LC       long call (about 0.60 delta, 35-60 days to expiry) when a stock gets our daily-buy + weekly-up signal
           and options are not expensive (implied vol / 30-day realised vol <= 1.25).
           exits: +50% target, -40% stop, or 14 days left.
  PCS      put credit spread (sell ~0.25 delta put, buy a put ~5% lower) on stocks in a clean uptrend
           (price > 50d > 200d average, RSI 40-70, positive 6-month return) when options are rich
           (implied / realised vol >= 1.10).  Exits: keep 50% of the credit, or loss = credit, or 7 days left.
  LC-ctrl / PCS-ctrl   the same structures on RANDOM liquid stocks, same number of trades per day.
           If the signals add nothing, the controls will do as well as the real strategies.
Return = profit / money at risk (premium for LC, width - credit for PCS).
"""
import datetime as dt
import html
import json
import math
import os
import random

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(HERE, "options_trades.csv")
RESULT_BT = os.path.join(HERE, "backtest_optbt.json")
R_RATE = 0.04
UNIVERSE = ("AAPL MSFT NVDA AMZN GOOGL META TSLA AMD AVGO NFLX PLTR COST JPM V MA UNH LLY XOM CRM ORCL ADBE "
            "INTC MU QCOM UBER BAC WMT HD DIS BA GS CAT").split()
STRATS = ["LC", "LC-ctrl", "PCS", "PCS-ctrl"]
COLS = ["id", "strategy", "ticker", "signal_date", "entry_date", "expiry", "kind", "long_sym", "short_sym",
        "long_strike", "short_strike", "entry_price", "width", "risk", "spot_entry", "iv_entry", "rv_entry",
        "status", "exit_date", "exit_reason", "exit_price", "ret_pct", "days", "last_mark", "last_mark_date"]
MAX_NEW, MAX_OPEN = 3, 12
LC_TARGET, LC_STOP, LC_MIN_DTE = 0.50, -0.40, 14
PCS_TAKE, PCS_STOP_MULT, PCS_MIN_DTE = 0.50, 2.0, 7
PCS_MIN_CREDIT = 0.18          # minimum credit as a share of the spread width


# ---------------------------------------------------------------- Black-Scholes
def _cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(S, K, T, sig, call=True, r=R_RATE):
    if T <= 0 or sig <= 0:
        return max(S - K, 0.0) if call else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    d2 = d1 - sig * math.sqrt(T)
    if call:
        return S * _cdf(d1) - K * math.exp(-r * T) * _cdf(d2)
    return K * math.exp(-r * T) * _cdf(-d2) - S * _cdf(-d1)


def bs_delta(S, K, T, sig, call=True, r=R_RATE):
    if T <= 0 or sig <= 0:
        return (1.0 if S > K else 0.0) if call else (-1.0 if S < K else 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    return _cdf(d1) if call else _cdf(d1) - 1


# ---------------------------------------------------------------- indicators
def rsi14(v):
    d = np.diff(v)
    if len(d) < 15:
        return float("nan")
    g, l = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = g[:14].mean(), l[:14].mean()
    for a, b in zip(g[14:], l[14:]):
        ag, al = (ag * 13 + a) / 14, (al * 13 + b) / 14
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def stock_stats(s):
    v = s.astype(float).values
    if len(v) < 210:
        return None
    lr = np.diff(np.log(v[-31:]))
    return {"close": v[-1], "sma50": v[-50:].mean(), "sma200": v[-200:].mean(), "rsi": rsi14(v),
            "ret126": v[-1] / v[-127] - 1, "rv30": float(lr.std(ddof=1) * math.sqrt(252))}


# ---------------------------------------------------------------- chains
class Chains:
    """Per-run cache of Yahoo option chains."""

    def __init__(self, yf_module):
        self.yf, self.cache, self.exps = yf_module, {}, {}

    def expiries(self, sym):
        if sym not in self.exps:
            try:
                self.exps[sym] = list(self.yf.Ticker(sym).options)
            except Exception as e:
                print("options: no expiries", sym, str(e)[:60])
                self.exps[sym] = []
        return self.exps[sym]

    def get(self, sym, exp):
        key = (sym, exp)
        if key not in self.cache:
            try:
                ch = self.yf.Ticker(sym).option_chain(exp)
                self.cache[key] = (ch.calls.copy(), ch.puts.copy())
            except Exception as e:
                print("options: chain failed", sym, exp, str(e)[:60])
                self.cache[key] = None
        return self.cache[key]


def pick_expiry(exps, asof, lo=35, hi=60, target=45):
    best = None
    for e in exps:
        d = (dt.date.fromisoformat(e) - asof).days
        if lo <= d <= hi and (best is None or abs(d - target) < abs(best[1] - target)):
            best = (e, d)
    return best


def quote_ok(row, max_spread=0.15, min_oi=100):
    bid, ask = float(row["bid"]), float(row["ask"])
    if not (bid > 0 and ask > 0 and ask >= bid):
        return False
    oi = row["openInterest"]
    if pd.isna(oi) or float(oi) < min_oi:
        return False
    return (ask - bid) / ((ask + bid) / 2) <= max_spread


def atm_iv(calls, puts, spot):
    vals = []
    for df in (calls, puts):
        near = df[(df["strike"] / spot > 0.95) & (df["strike"] / spot < 1.05)]
        vals += [float(r["impliedVolatility"]) for _, r in near.iterrows()
                 if quote_ok(r, 0.25, 50) and float(r["impliedVolatility"]) > 0.05]
    return float(np.median(vals)) if vals else None


# ---------------------------------------------------------------- contract selection
def choose_call(calls, spot, dte):
    T, best = dte / 365, None
    for _, r in calls.iterrows():
        iv = float(r["impliedVolatility"])
        if iv <= 0.05 or not quote_ok(r):
            continue
        d = bs_delta(spot, float(r["strike"]), T, iv, True)
        if 0.50 <= d <= 0.75 and (best is None or abs(d - 0.60) < abs(best[0] - 0.60)):
            best = (d, r)
    if best is None:
        return None
    r = best[1]
    return {"kind": "call", "long_sym": r["contractSymbol"], "short_sym": "", "long_strike": float(r["strike"]),
            "short_strike": float("nan"), "entry_price": float(r["ask"]), "width": float("nan"),
            "risk": float(r["ask"])}


def choose_pcs(puts, spot, dte):
    T = dte / 365
    cand = None
    for _, r in puts.iterrows():
        iv = float(r["impliedVolatility"])
        if iv <= 0.05 or not quote_ok(r):
            continue
        d = bs_delta(spot, float(r["strike"]), T, iv, False)
        if -0.35 <= d <= -0.15 and (cand is None or abs(abs(d) - 0.25) < abs(abs(cand[0]) - 0.25)):
            cand = (d, r)
    if cand is None:
        return None
    sp = cand[1]
    ks = float(sp["strike"])
    lower = puts[(puts["strike"] < ks) & (puts["strike"] <= ks * 0.955)].sort_values("strike", ascending=False)
    for _, lg in lower.iterrows():
        if quote_ok(lg):
            kl = float(lg["strike"])
            width = ks - kl
            if width > ks * 0.10:
                break
            credit = float(sp["bid"]) - float(lg["ask"])
            if credit >= 0.25 and credit >= PCS_MIN_CREDIT * width:
                return {"kind": "pcs", "long_sym": lg["contractSymbol"], "short_sym": sp["contractSymbol"],
                        "long_strike": kl, "short_strike": ks, "entry_price": credit, "width": width,
                        "risk": width - credit}
            break
    return None


# ---------------------------------------------------------------- trade book
def load_trades():
    if os.path.exists(TRADES):
        return pd.read_csv(TRADES, dtype=str, keep_default_na=False).reindex(columns=COLS).fillna("").astype(object)
    return pd.DataFrame(columns=COLS).astype(object)


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def current_value(tr, chains, spot, asof):
    """Conservative value to close the trade now (per share), or None when quotes are missing."""
    exp = dt.date.fromisoformat(tr["expiry"])
    if asof >= exp:
        if tr["kind"] == "call":
            return max(spot - float(tr["long_strike"]), 0.0), "settle"
        return max(float(tr["short_strike"]) - spot, 0.0) - max(float(tr["long_strike"]) - spot, 0.0), "settle"
    ch = chains.get(tr["ticker"], tr["expiry"])
    if ch is None:
        return None, "noquote"
    calls, puts = ch
    if tr["kind"] == "call":
        row = calls[calls["contractSymbol"] == tr["long_sym"]]
        if row.empty:
            return None, "noquote"
        return float(row.iloc[0]["bid"]), "quote"
    ls = puts[puts["contractSymbol"] == tr["long_sym"]]
    ss = puts[puts["contractSymbol"] == tr["short_sym"]]
    if ls.empty or ss.empty or float(ss.iloc[0]["ask"]) <= 0:
        return None, "noquote"
    return float(ss.iloc[0]["ask"]) - float(ls.iloc[0]["bid"]), "quote"


def trade_return(tr, value):
    if tr["kind"] == "call":
        return (value - float(tr["entry_price"])) / float(tr["entry_price"])
    return (float(tr["entry_price"]) - value) / float(tr["risk"])


def update_open(trades, chains, spots, asof, events):
    for i in trades.index[trades["status"] == "OPEN"]:
        tr = trades.loc[i].to_dict()
        spot = spots.get(tr["ticker"])
        if spot is None:
            continue
        value, how = current_value(tr, chains, spot, asof)
        dte = (dt.date.fromisoformat(tr["expiry"]) - asof).days
        if value is None:
            ref = tr["last_mark_date"] or tr["entry_date"]
            if (asof - dt.date.fromisoformat(ref)).days >= 5:      # no usable quote for 5+ days: leave the statistics
                trades.at[i, "status"], trades.at[i, "exit_date"] = "VOID", asof.isoformat()
                trades.at[i, "exit_reason"] = "قیمت در دسترس نبود"
            continue
        ret = trade_return(tr, value)
        trades.at[i, "last_mark"], trades.at[i, "last_mark_date"] = round(value, 4), asof.isoformat()
        trades.at[i, "ret_pct"] = round(ret * 100, 1)
        trades.at[i, "days"] = (asof - dt.date.fromisoformat(tr["entry_date"])).days
        reason = None
        if how == "settle":
            reason = "سررسید"
        elif tr["kind"] == "call":
            reason = ("هدف سود" if ret >= LC_TARGET else "حد ضرر" if ret <= LC_STOP
                      else "نزدیک سررسید" if dte <= LC_MIN_DTE else None)
        else:
            credit = float(tr["entry_price"])
            reason = ("۵۰٪ سود کرد" if value <= PCS_TAKE * credit else "حد ضرر" if value >= PCS_STOP_MULT * credit
                      else "نزدیک سررسید" if dte <= PCS_MIN_DTE else None)
        if reason:
            trades.at[i, "status"], trades.at[i, "exit_date"] = "CLOSED", asof.isoformat()
            trades.at[i, "exit_reason"], trades.at[i, "exit_price"] = reason, round(value, 4)
            events["closed"].append(trades.loc[i].to_dict())


def try_open(strategy, sym, stats, chains, asof, trades, need_vol, events, signal_date):
    """Build a trade for `sym` if liquid contracts exist and the vol filter passes. Returns the row or None."""
    spot = float(stats["close"])
    pe = pick_expiry(chains.expiries(sym), asof)
    if not pe:
        return None
    exp, dte = pe
    ch = chains.get(sym, exp)
    if ch is None:
        return None
    calls, puts = ch
    iv = atm_iv(calls, puts, spot)
    if iv is None:
        return None
    ratio = iv / stats["rv30"] if stats["rv30"] > 0 else None
    if ratio is None:
        return None
    base = strategy.split("-")[0]
    if need_vol:
        if base == "LC" and ratio > 1.25:
            return None
        if base == "PCS" and ratio < 1.10:
            return None
    leg = choose_call(calls, spot, dte) if base == "LC" else choose_pcs(puts, spot, dte)
    if leg is None:
        return None
    row = {"id": f"{strategy}-{sym}-{asof.isoformat()}", "strategy": strategy, "ticker": sym,
           "signal_date": signal_date, "entry_date": asof.isoformat(), "expiry": exp, **leg,
           "spot_entry": round(spot, 2), "iv_entry": round(iv * 100, 1), "rv_entry": round(stats["rv30"] * 100, 1),
           "status": "OPEN", "exit_date": "", "exit_reason": "", "exit_price": "", "ret_pct": 0.0, "days": 0,
           "last_mark": "", "last_mark_date": ""}
    return row


def run(series_cache, df, pre, short, fmt_price, yf_module=None, today=None, rng_seed=None):
    """Daily step. Returns (message_blocks, summary_lines, trades_changed)."""
    if yf_module is None:
        import yfinance as yf_module
    us = series_cache.get("US") or {}
    stats = {t: stock_stats(us[t]) for t in UNIVERSE if t in us}
    stats = {t: s for t, s in stats.items() if s}
    if not stats:
        return [], [], False
    us_rows = df[df["market"] == "US"]
    asof = pd.to_datetime(us_rows["last_date"]).max().date() if len(us_rows) else (today or dt.date.today())
    spots = {t: s["close"] for t, s in stats.items()}
    chains = Chains(yf_module)
    trades = load_trades()
    events = {"opened": [], "closed": []}
    update_open(trades, chains, spots, asof, events)

    def open_syms(strategy):
        return set(trades[(trades["strategy"] == strategy) & (trades["status"] == "OPEN")]["ticker"])

    def n_open(strategy):
        return int(((trades["strategy"] == strategy) & (trades["status"] == "OPEN")).sum())

    already = set(trades["id"])
    new_rows = []

    def add(row):
        nonlocal trades
        if row["id"] in already:
            return False
        trades = pd.concat([trades, pd.DataFrame([row], columns=COLS).astype(object)], ignore_index=True)
        already.add(row["id"])
        events["opened"].append(row)
        return True

    # ---- real strategies
    aligned = set(us_rows[us_rows["aligned"].astype(str) == "True"]["ticker"]) & set(stats)
    lc_c = []
    for t in sorted(aligned - open_syms("LC")):
        r = try_open("LC", t, stats[t], chains, asof, trades, True, events, asof.isoformat())
        if r:
            lc_c.append((float(r["iv_entry"]) / max(float(r["rv_entry"]), 1), r))
    pcs_c = []
    for t, s in stats.items():
        if t in open_syms("PCS"):
            continue
        if s["close"] > s["sma50"] > s["sma200"] and 40 <= s["rsi"] <= 70 and s["ret126"] > 0:
            r = try_open("PCS", t, s, chains, asof, trades, True, events, asof.isoformat())
            if r:
                pcs_c.append((float(r["iv_entry"]) / max(float(r["rv_entry"]), 1), r))
    n_real = {"LC": 0, "PCS": 0}
    for _, r in sorted(lc_c, key=lambda x: x[0])[:MAX_NEW]:
        if n_open("LC") < MAX_OPEN and add(r):
            n_real["LC"] += 1
    for _, r in sorted(pcs_c, key=lambda x: -x[0])[:MAX_NEW]:
        if n_open("PCS") < MAX_OPEN and add(r):
            n_real["PCS"] += 1

    # ---- controls: same number of trades on random liquid stocks, no signal and no vol filter
    rnd = random.Random(rng_seed if rng_seed is not None else asof.toordinal())
    for base in ("LC", "PCS"):
        need, name = n_real[base], f"{base}-ctrl"
        taken = {r["ticker"] for r in events["opened"] if r["strategy"] == base}
        pool = [t for t in stats if t not in open_syms(name) and t not in taken]
        rnd.shuffle(pool)
        for t in pool:
            if need <= 0 or n_open(name) >= MAX_OPEN:
                break
            r = try_open(name, t, stats[t], chains, asof, trades, False, events, "random")
            if r and add(r):
                need -= 1

    changed = bool(events["opened"] or events["closed"] or (trades["status"] == "OPEN").any())
    if changed:
        trades.to_csv(TRADES, index=False)
    blocks, hl = build_message(trades, events, pre, asof, today)
    return blocks, hl, changed


# ---------------------------------------------------------------- report
def stats_table(trades):
    rows = [f"{'Strategy':<9}{'Closed':>6}{'Win%':>5}{'Avg%':>6}{'Open':>5}{'MTM%':>6}{'All%':>6}", "-" * 43]
    for s in STRATS:
        sub = trades[trades["strategy"] == s]
        cl, op = sub[sub["status"] == "CLOSED"], sub[sub["status"] == "OPEN"]
        rc = [num(x) for x in cl["ret_pct"] if num(x) is not None]
        ro = [num(x) for x in op["ret_pct"] if num(x) is not None]
        allr = rc + ro
        f = lambda v: "-" if not v else f"{np.mean(v):+.0f}"
        win = f"{np.mean([x > 0 for x in rc]) * 100:.0f}" if rc else "-"
        rows.append(f"{s:<9}{len(rc):>6}{win:>5}{f(rc):>6}{len(ro):>5}{f(ro):>6}{f(allr):>6}")
    return rows


def desc(tr):
    exp = dt.date.fromisoformat(tr["expiry"]).strftime("%d%b")
    if tr["kind"] == "call":
        return f"Call {float(tr['long_strike']):g} {exp}"
    return f"Put {float(tr['short_strike']):g}/{float(tr['long_strike']):g} {exp}"


def build_message(trades, events, pre, asof, today=None):
    today = today or dt.date.today()
    if trades.empty:
        return [], []
    send_now = bool(events["opened"] or events["closed"]) or today.weekday() == 5
    hl = []
    n_open = int((trades["status"] == "OPEN").sum())
    if events["opened"] or events["closed"]:
        hl.append(f"• معاملات کاغذی آپشن: {len(events['opened'])} باز شد، {len(events['closed'])} بسته شد، {n_open} باز است.")
    if not send_now:
        return [], hl
    blocks = [f"🎯 <b>آزمون استراتژی‌های آپشن (معامله‌ی کاغذی با قیمت‌های واقعی)</b> — {asof}\n"
              "<i>هر معامله با قیمت واقعی خرید و فروش Yahoo ثبت می‌شود (خرید با قیمت فروشنده، فروش با قیمت خریدار) و هر روز تا پایان "
              "پیگیری می‌شود. کارمزد کارگزار حساب نشده است. بازده = سود تقسیم بر پولی که در خطر بود (برای خرید Call: پرمیوم؛ "
              "برای اسپرد: عرض اسپرد منهای اعتبار دریافتی).\n"
              "LC = خرید Call پس از سیگنال خرید ما، وقتی آپشن گران نیست · PCS = فروش اسپرد Put در روند صعودی، وقتی آپشن گران است · "
              "ctrl = همان کار روی سهم‌های تصادفی بدون سیگنال؛ اگر سیگنال‌ها ارزشی نداشته باشند، ctrl هم به همان اندازه خوب است.</i>"]
    if events["opened"]:
        t = [f"{'Strategy':<9}{'Stock':<6}{'Contract':<17}{'Price':>6}", "-" * 39]
        for r in events["opened"]:
            t.append(f"{r['strategy']:<9}{r['ticker']:<6}{desc(r):<17}{float(r['entry_price']):>6.2f}")
        blocks.append("🆕 <b>معامله‌های جدید</b> (Price: پرمیوم پرداختی برای Call، اعتبار دریافتی برای اسپرد)\n" + pre(t))
    if events["closed"]:
        t = [f"{'Strategy':<9}{'Stock':<6}{'Ret%':>6}  Reason", "-" * 34]
        for r in events["closed"]:
            t.append(f"{r['strategy']:<9}{r['ticker']:<6}{num(r['ret_pct']) or 0:>+6.0f}  {r['exit_reason']}")
        blocks.append("✅ <b>معامله‌های بسته‌شده</b>\n" + pre(t))
    blocks.append("📊 <b>جدول نتایج از ابتدا</b>\n"
                  "<i>Closed بسته‌شده‌ها · Win% درصد سودده · Avg% میانگین بازده بسته‌شده‌ها · Open بازها · MTM% میانگین بازده فعلی بازها · "
                  "All% میانگین همه (بسته + باز؛ معیار منصفانه‌تر، چون بستن زودهنگام سودها آمار بسته‌شده‌ها را خوش‌بین می‌کند)</i>\n"
                  + pre(stats_table(trades)))
    closed_n = int((trades["status"] == "CLOSED").sum())
    if closed_n < 30:
        blocks.append(f"<i>تا اینجا فقط {closed_n} معامله بسته شده؛ برای قضاوت دست‌کم ۳۰ معامله‌ی بسته‌شده در هر استراتژی (چند ماه) لازم است.</i>")
    blocks.append("<i>این یک آزمایش کاغذی است و توصیه‌ی معامله نیست. آپشن می‌تواند تمام پرمیوم را از دست بدهد.</i>")
    return blocks, hl


# ---------------------------------------------------------------- approximate index backtest
def backtest(request_id, download_all, send, pre):
    """Weekly entries on the S&P 500 with Black-Scholes prices and VIX as the implied volatility."""
    data = download_all(["^GSPC", "^VIX"], period="5y")
    s, v = data.get("^GSPC"), data.get("^VIX")
    if s is None or v is None:
        send(["⚠️ بک‌تست آپشن انجام نشد: داده‌ی S&P 500 یا VIX دریافت نشد."], b"", "optbt")
        return False
    df = pd.DataFrame({"S": s.astype(float), "V": v.astype(float)}).dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None) if getattr(df.index, "tz", None) else pd.to_datetime(df.index)
    S, V, D = df["S"].values, df["V"].values / 100, df.index
    out = {"LC": [], "PCS": []}
    spread = 0.02            # each leg is bought 2% above / sold 2% below the model mid price
    for i in range(0, len(df) - 35, 5):
        exp_date = D[i] + pd.Timedelta(days=45)
        j_end = int(np.searchsorted(D, exp_date, side="right") - 1)
        if j_end >= len(df) or D[-1] < exp_date:
            break
        T0 = 45 / 365
        # --- long call, strike = spot (about 0.55 delta)
        K = S[i]
        cost = bs_price(S[i], K, T0, V[i], True) * (1 + spread)
        # --- put credit spread: short put near -0.25 delta, long put 5% lower; skew: puts priced at VIX * 1.10
        sg = V[i] * 1.10
        ks = min((S[i] * f for f in np.arange(1.0, 0.70, -0.005)),
                 key=lambda k: abs(bs_delta(S[i], k, T0, sg, False) + 0.25))
        kl = ks * 0.95
        credit = bs_price(S[i], ks, T0, sg, False) * (1 - spread) - bs_price(S[i], kl, T0, sg, False) * (1 + spread)
        res = {}
        for name in ("LC", "PCS"):
            if name == "PCS" and credit < PCS_MIN_CREDIT * (ks - kl):
                continue
            ret, why, last = None, "expiry", i
            for j in range(i + 1, j_end + 1):
                T = max((exp_date - D[j]).days, 0) / 365
                if name == "LC":
                    val = bs_price(S[j], K, T, V[j], True) * (1 - spread)
                    r_ = (val - cost) / cost
                    if r_ >= LC_TARGET:
                        ret, why = r_, "target"
                    elif r_ <= LC_STOP:
                        ret, why = r_, "stop"
                    elif T * 365 <= LC_MIN_DTE:
                        ret, why = r_, "time"
                else:
                    debit = bs_price(S[j], ks, T, V[j] * 1.10, False) * (1 + spread) - \
                        bs_price(S[j], kl, T, V[j] * 1.10, False) * (1 - spread)
                    r_ = (credit - debit) / ((ks - kl) - credit)
                    if debit <= PCS_TAKE * credit:
                        ret, why = r_, "target"
                    elif debit >= PCS_STOP_MULT * credit:
                        ret, why = r_, "stop"
                    elif T * 365 <= PCS_MIN_DTE:
                        ret, why = r_, "time"
                if ret is not None:
                    last = j
                    break
            if ret is None:
                T = 0
                if name == "LC":
                    ret = (max(S[j_end] - K, 0) - cost) / cost
                else:
                    debit = max(ks - S[j_end], 0) - max(kl - S[j_end], 0)
                    ret = (credit - debit) / ((ks - kl) - credit)
                last = j_end
            out[name].append({"date": str(D[i].date()), "ret": float(ret) * 100, "why": why, "days": int(last - i)})
    rows = []
    for name in ("LC", "PCS"):
        r = pd.DataFrame(out[name])
        if r.empty:
            continue
        r["year"] = r["date"].str[:4]
        rows.append({"strategy": name, "n": len(r), "win": float((r["ret"] > 0).mean() * 100),
                     "avg": float(r["ret"].mean()), "median": float(r["ret"].median()), "worst": float(r["ret"].min()),
                     "best": float(r["ret"].max()), "by_year": {y: float(g["ret"].mean()) for y, g in r.groupby("year")},
                     "stop_share": float((r["why"] == "stop").mean() * 100)})
    json.dump({"request": request_id, "date": dt.date.today().isoformat(), "rows": rows},
              open(RESULT_BT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    t = [f"{'Strategy':<9}{'N':>5}{'Win%':>6}{'Avg%':>7}{'Med%':>7}{'Worst':>7}{'Stop%':>7}", "-" * 48]
    for r in rows:
        t.append(f"{r['strategy']:<9}{r['n']:>5}{r['win']:>6.0f}{r['avg']:>+7.0f}{r['median']:>+7.0f}{r['worst']:>+7.0f}{r['stop_share']:>7.0f}")
    years = sorted({y for r in rows for y in r["by_year"]})
    ty = [f"{'Year':<6}" + "".join(f"{r['strategy']:>9}" for r in rows), "-" * (6 + 9 * len(rows))]
    for y in years:
        ty.append(f"{y:<6}" + "".join((f"{r['by_year'][y]:>+9.0f}" if y in r["by_year"] else f"{'-':>9}") for r in rows))
    blocks = [
        f"🧮 <b>بک‌تست تقریبی دو استراتژی آپشن روی S&P 500</b> — {dt.date.today()}\n"
        "<i>داده‌ی رایگان قیمت تاریخی آپشن وجود ندارد، پس قیمت آپشن‌ها را با فرمول بلک-شولز و نوسان ضمنی VIX محاسبه کردیم "
        "(برای Put ها ۱۰٪ بیشتر، چون Put ها معمولاً گران‌ترند). هر هفته یک معامله با سررسید ۴۵ روزه، همان قواعد خروج استراتژی زنده، "
        "خرید ۲٪ بالاتر و فروش ۲٪ پایین‌تر از قیمت وسط. این فقط برآورد «ساختار استراتژی» است و سیگنال‌های ما را نمی‌سنجد.</i>",
        "<i>LC = خرید Call نزدیک قیمت روز · PCS = فروش اسپرد Put (دلتای ۰٫۲۵- و ۵٪ پایین‌تر) · "
        "Stop% = سهم معامله‌هایی که با حد ضرر بسته شدند · Worst بدترین معامله</i>",
        pre(t), "📅 <b>میانگین بازده به تفکیک سال</b>\n" + pre(ty),
        "⚠️ <b>محدودیت‌ها</b>\n"
        "• معامله‌ها هفتگی‌اند و با هم هم‌پوشانی دارند؛ تعداد واقعاً مستقل کمتر از N است.\n"
        "• قیمت‌ها مدل‌اند، نه قیمت واقعی بازار؛ شیب نوسان (Skew) و رویدادهایی مثل گزارش مالی در آن نیست.\n"
        "• فقط شاخص آمریکا؛ برای سهم تکی رفتار آپشن متفاوت و پرنوسان‌تر است.\n"
        "<i>داوری اصلی با آزمون کاغذیِ قیمت‌های واقعی است که از امروز ثبت می‌شود. این توصیه‌ی معامله نیست.</i>"]
    send(blocks, b"", "optbt")
    return True
