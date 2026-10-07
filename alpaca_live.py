"""
Alpaca PAPER-trading link (virtual money only; the endpoint is paper-api.alpaca.markets).
Target portfolio of the account (weights of equity, 2% kept as cash):
  35%  VT                      (world stock ETF = core of the suggested portfolio)
  15%  US momentum sleeve      (top 8 US picks of the newest V1-RAMom cohort, equal weight)
  50%  AI basket               (the 20 stocks of ai_basket.py, equal weight)
Orders are placed (market, day, notional) only when the target list changes (first run and when a new monthly
cohort changes the sleeve); positions that this script bought earlier and that left the target are closed.
Positions that were not opened by this script are never touched. Open orders block new orders for that symbol.
State: alpaca_state.json. Credentials: ALPACA_KEY / ALPACA_SECRET (env or config.txt).
"""
import datetime as dt
import hashlib
import html
import json
import os
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "alpaca_state.json")
BASE = "https://paper-api.alpaca.markets/v2"
W_VT, W_SLEEVE, W_AI = 0.35, 0.15, 0.50
CASH_KEEP = 0.98
MIN_TRADE = 25.0          # dollars; smaller differences are ignored
N_SLEEVE = 8


def creds():
    k, s = os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET")
    if not (k and s):
        try:
            for line in open(os.path.join(HERE, "config.txt"), encoding="utf-8"):
                if line.startswith("ALPACA_KEY="):
                    k = line.split("=", 1)[1].strip()
                elif line.startswith("ALPACA_SECRET="):
                    s = line.split("=", 1)[1].strip()
        except OSError:
            pass
    return (k, s) if k and s else None


def api(method, path, c, **kw):
    try:
        r = requests.request(method, BASE + path, timeout=40,
                             headers={"APCA-API-KEY-ID": c[0], "APCA-API-SECRET-KEY": c[1]}, **kw)
        try:
            body = r.json()
        except Exception:
            body = r.text[:200]
        return r.status_code, body
    except Exception as e:
        return 0, str(type(e).__name__)


def sym_fix(t):
    return t.strip().upper().replace("-", ".")


def us_sleeve():
    import core_live
    co = core_live.load()
    v1 = co[(co["market"] == "US") & (co["strategy"] == "V1-RAMom")]
    if v1.empty:
        return []
    row = v1[v1["cohort"] == v1["cohort"].max()].iloc[0]
    out = [sym_fix(x.rsplit(":", 1)[0]) for x in row["picks"].split(";") if ":" in x]
    return [t for t in out if re.fullmatch(r"[A-Z.]{1,6}", t)][:N_SLEEVE]


def targets():
    import ai_basket
    w = {}
    w["VT"] = W_VT
    sl = us_sleeve()
    for t in sl:
        w[t] = w.get(t, 0) + W_SLEEVE / len(sl)
    ai = [t for t, _ in ai_basket.BASKET]
    for t in ai:
        w[t] = w.get(t, 0) + W_AI / len(ai)
    return w, sl


def f0(v):
    return f"{v:,.0f}"


def run(pre, today=None):
    """Returns (telegram_blocks, summary_lines, changed)."""
    today = today or dt.date.today()
    c = creds()
    if not c:
        return [], ["• Alpaca: کلید در config.txt نیست."], False
    st, acct = api("GET", "/account", c)
    if st != 200 or not isinstance(acct, dict):
        return [f"⚠️ اتصال به Alpaca برقرار نشد (کد {st}). کلید یا سرویس را بررسی کنید."], [], False
    equity = float(acct.get("equity", 0))
    last_eq = float(acct.get("last_equity", equity) or equity)
    cash = float(acct.get("cash", 0))
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    changed, notes = False, []
    st, pos = api("GET", "/positions", c)
    pos = pos if st == 200 and isinstance(pos, list) else []
    cur_mv = {p["symbol"]: float(p.get("market_value", 0)) for p in pos}
    st, oo = api("GET", "/orders?status=open&limit=200", c)
    open_syms = {o["symbol"] for o in oo} if st == 200 and isinstance(oo, list) else set()

    try:
        tgt, sleeve = targets()
    except Exception as e:
        tgt, sleeve = None, []
        notes.append(f"هدف سبد ساخته نشد ({type(e).__name__})")
    key = hashlib.md5(json.dumps(sorted((k, round(v, 4)) for k, v in (tgt or {}).items())).encode()).hexdigest()[:10]
    placed, failed = [], []
    if tgt and state.get("key") != key:
        managed = set(state.get("managed", []))
        for sym in sorted(managed - set(tgt)):                      # left the target: close
            if sym in cur_mv and sym not in open_syms:
                s2, b = api("DELETE", f"/positions/{sym}", c)
                (placed if s2 in (200, 207) else failed).append((sym, "SELL ALL", cur_mv.get(sym, 0), s2))
        for sym, w in sorted(tgt.items()):
            if sym in open_syms:
                continue
            want = w * equity * CASH_KEEP
            diff = want - cur_mv.get(sym, 0.0)
            if abs(diff) < MIN_TRADE:
                continue
            side = "buy" if diff > 0 else "sell"
            s2, b = api("POST", "/orders", c, json={"symbol": sym, "notional": f"{abs(diff):.2f}", "side": side,
                                                    "type": "market", "time_in_force": "day"})
            (placed if s2 in (200, 201) else failed).append((sym, side.upper(), abs(diff), s2 if s2 not in (200, 201) else
                                                             ""))
        state.update({"key": key if not failed else state.get("key"), "managed": sorted(set(tgt)), "last_rebalance": today.isoformat(),
                      "equity_start": state.get("equity_start", equity), "start_date": state.get("start_date", today.isoformat())})
        changed = True
    elif not state.get("start_date"):
        state.update({"start_date": today.isoformat(), "equity_start": equity})
        changed = True
    if changed:
        json.dump(state, open(STATE, "w"), ensure_ascii=False)

    eq0 = float(state.get("equity_start", equity)) or equity
    t1 = [f"{'Account':<10}{'Value$':>10}{'Day%':>7}{'Since%':>8}", "-" * 35,
          f"{'Equity':<10}{f0(equity):>10}{(equity / last_eq - 1) * 100 if last_eq else 0:>+7.1f}{(equity / eq0 - 1) * 100:>+8.1f}",
          f"{'Cash':<10}{f0(cash):>10}"]
    rows = sorted(pos, key=lambda p: -float(p.get("market_value", 0)))
    t2 = [f"{'Stock':<7}{'Value$':>8}{'P/L%':>7}{'Day%':>7}", "-" * 29]
    for p in rows[:30]:
        t2.append(f"{p['symbol'][:6]:<7}{f0(float(p.get('market_value', 0))):>8}"
                  f"{float(p.get('unrealized_plpc', 0)) * 100:>+7.1f}{float(p.get('change_today', 0)) * 100:>+7.1f}")
    since = state.get("start_date", today.isoformat())
    blocks = [f"🏦 <b>حساب آزمایشی Alpaca</b> — {today}\n<i>پول مجازی؛ سبد: ۳۵٪ VT، ۱۵٪ سهم‌های مومنتوم آمریکا، ۵۰٪ سبد هوش مصنوعی. "
              f"از {since} دنبال می‌شود. سفارش‌ها فقط هنگام عوض شدن فهرست (ابتدا و هر ماه) ثبت می‌شوند و در بازار باز اجرا می‌شوند.</i>",
              "📊 <b>ارزش حساب</b>\n" + pre(t1)]
    if rows:
        blocks.append("📋 <b>سهم‌های حساب</b>\n" + pre(t2))
    elif placed:
        blocks.append("⏳ سفارش‌ها ثبت شد و پس از باز شدن بازار آمریکا اجرا می‌شود؛ سهم‌ها فردا در جدول می‌آیند.")
    if placed or failed:
        msg = f"🧾 <b>سفارش‌های این اجرا</b>: {len(placed)} ثبت شد"
        if failed:
            msg += f"، {len(failed)} ناموفق: " + "، ".join(f"{html.escape(s)}({code})" for s, _, _, code in failed[:12])
        blocks.append(msg)
    if notes:
        blocks.append("⚠️ " + html.escape("؛ ".join(notes)))
    blocks.append("<i>حساب آزمایشی است و توصیه‌ی خرید یا فروش نیست.</i>")
    hl = [f"• حساب Alpaca: {f0(equity)} دلار ({(equity / eq0 - 1) * 100:+.1f}٪ از شروع)."]
    return blocks, hl, changed
