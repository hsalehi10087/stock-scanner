"""
One-off probe: how usable is the free Yahoo Finance option data when the daily scan runs?
Prints and sends a short report (share of contracts with real bid/ask, spreads, open interest, freshness)
and stores options_probe.json. The strategy design depends on the answer.
"""
import datetime as dt
import json
import os

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
RESULT = os.path.join(HERE, "options_probe.json")
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "AVGO", "PLTR", "SPY"]
TARGET_DTE = (30, 45)


def pick_expiry(exps, target, today):
    best = None
    for e in exps:
        d = (dt.date.fromisoformat(e) - today).days
        if d >= 7 and (best is None or abs(d - target) < abs(best[1] - target)):
            best = (e, d)
    return best


def probe_one(sym, today):
    t = yf.Ticker(sym)
    hist = t.history(period="5d")
    if hist is None or hist.empty:
        return {"ticker": sym, "error": "no price history"}
    spot = float(hist["Close"].iloc[-1])
    last_bar = hist.index[-1]
    out = {"ticker": sym, "spot": round(spot, 2), "last_bar": str(last_bar)[:10], "expiries": []}
    try:
        exps = list(t.options)
    except Exception as e:
        return {**out, "error": f"no expiries: {str(e)[:80]}"}
    out["n_expiries"] = len(exps)
    for target in TARGET_DTE:
        pe = pick_expiry(exps, target, today)
        if not pe:
            continue
        exp, dte = pe
        try:
            ch = t.option_chain(exp)
        except Exception as e:
            out["expiries"].append({"expiry": exp, "dte": dte, "error": str(e)[:80]})
            continue
        info = {"expiry": exp, "dte": dte}
        for side, df in (("calls", ch.calls), ("puts", ch.puts)):
            if df is None or df.empty:
                info[side] = {"n": 0}
                continue
            df = df.copy()
            df["mny"] = df["strike"] / spot
            near = df[(df["mny"] > 0.85) & (df["mny"] < 1.15)]
            q = near[(near["bid"] > 0) & (near["ask"] > 0)]
            mid = (q["bid"] + q["ask"]) / 2
            spr = ((q["ask"] - q["bid"]) / mid) if len(q) else pd.Series(dtype=float)
            atm = near.iloc[(near["strike"] - spot).abs().argsort()[:1]]
            a = atm.iloc[0] if len(atm) else None
            info[side] = {
                "n": int(len(df)), "n_near": int(len(near)),
                "pct_bid_ask_ok": round(float(len(q) / len(near) * 100), 0) if len(near) else None,
                "median_spread_pct": round(float(spr.median() * 100), 1) if len(spr) else None,
                "median_open_interest": float(near["openInterest"].fillna(0).median()) if len(near) else None,
                "pct_volume_gt0": round(float((near["volume"].fillna(0) > 0).mean() * 100), 0) if len(near) else None,
                "median_iv_pct": round(float(near["impliedVolatility"].median() * 100), 1) if len(near) else None,
                "atm": None if a is None else {
                    "strike": float(a["strike"]), "bid": float(a["bid"]), "ask": float(a["ask"]),
                    "last": float(a["lastPrice"]), "iv": round(float(a["impliedVolatility"]) * 100, 1),
                    "volume": None if pd.isna(a["volume"]) else float(a["volume"]),
                    "oi": None if pd.isna(a["openInterest"]) else float(a["openInterest"]),
                    "last_trade": str(a["lastTradeDate"])[:19],
                },
            }
        out["expiries"].append(info)
    return out


def run(request_id, send, pre):
    today = dt.date.today()
    rows = []
    for sym in TICKERS:
        try:
            rows.append(probe_one(sym, today))
        except Exception as e:
            rows.append({"ticker": sym, "error": str(e)[:120]})
        print("probe:", sym, "ok" if "error" not in rows[-1] else rows[-1]["error"])
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    json.dump({"request": request_id, "run_at": now, "rows": rows}, open(RESULT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)

    t = [f"{'Symbol':<7}{'BA ok%':>7}{'Spr%':>6}{'OI':>7}{'Vol>0%':>7}{'IV%':>5}", "-" * 39]
    for r in rows:
        if r.get("error") or not r.get("expiries"):
            t.append(f"{r['ticker']:<7}  {r.get('error', 'no expiries')[:28]}")
            continue
        e = next((x for x in r["expiries"] if "calls" in x), None)
        if not e:
            t.append(f"{r['ticker']:<7}  chain error")
            continue
        c = e["calls"]
        f = lambda v, fmt="{:.0f}": "-" if v is None else fmt.format(v)
        t.append(f"{r['ticker']:<7}{f(c.get('pct_bid_ask_ok')):>7}{f(c.get('median_spread_pct'), '{:.1f}'):>6}"
                 f"{f(c.get('median_open_interest')):>7}{f(c.get('pct_volume_gt0')):>7}{f(c.get('median_iv_pct')):>5}")
    blocks = [f"🔬 <b>بررسی کیفیت داده‌ی آپشن در Yahoo</b> — {now}\n"
              "<i>آیا داده‌ی رایگان آپشن برای آزمون استراتژی قابل‌استفاده است؟ ستون‌ها برای آپشن‌های خرید (Call) نزدیک قیمت روز، با حدود ۳۰ روز تا سررسید: "
              "BA ok% = درصد قراردادهایی که قیمت خرید و فروش واقعی دارند · Spr% = میانه‌ی فاصله‌ی قیمت خرید و فروش نسبت به قیمت وسط · "
              "OI = میانه‌ی موقعیت‌های باز · Vol>0% = درصد قراردادهایی که امروز معامله شده‌اند · IV% = نوسان ضمنی</i>",
              pre(t)]
    sample = next((r for r in rows if r.get("expiries") and "calls" in r["expiries"][0]
                   and r["expiries"][0]["calls"].get("atm")), None)
    if sample:
        a = sample["expiries"][0]["calls"]["atm"]
        blocks.append(f"نمونه — {sample['ticker']} (قیمت {sample['spot']}، آخرین کندل {sample['last_bar']}): "
                      f"Call نزدیک قیمت روز، قیمت خرید {a['bid']} / فروش {a['ask']} / آخرین معامله {a['last']} "
                      f"({a['last_trade']}).")
    send(blocks, b"", "optprobe")
    return True
