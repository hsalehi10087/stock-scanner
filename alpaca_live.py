"""
Alpaca PAPER-trading link (virtual money only). Mirrors the paper portfolios into a real Alpaca paper account:
  * Plan bucket (50% of the base capital): 70% VT + 30% equal-weight of the US names in the current momentum sleeve
    (portfolio_state.csv). Re-balanced when a new monthly cohort appears.
  * AI bucket (50%): the 20-stock AI basket (ai_basket.csv), equal weight, bought once and held.
Safety: refuses to run unless the endpoint is paper-api.alpaca.markets; every order is a small notional market order.
State: alpaca_state.json (the dollar target per symbol per bucket that has really been ordered).
Keys are read from env or config.txt: ALPACA_KEY, ALPACA_SECRET, ALPACA_ENDPOINT.
"""
import datetime as dt
import html
import json
import math
import os
import re
import time

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "alpaca_state.json")
DATA = "https://data.alpaca.markets"
BASE_CAP = 100_000.0          # capital the plan is sized on (paper accounts start at 100k)
PLAN_SHARE, AI_SHARE = 0.5, 0.5
CORE_W, SLEEVE_W = 0.70, 0.30
MIN_TRADE = 25.0
US_RE = re.compile(r"^[A-Z]{1,5}$")


def cfg(name, default=None):
    v = os.environ.get(name)
    if v:
        return v.strip()
    try:
        for line in open(os.path.join(HERE, "config.txt"), encoding="utf-8"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return default


class Client:
    def __init__(self):
        self.base = (cfg("ALPACA_ENDPOINT", "https://paper-api.alpaca.markets/v2") or "").rstrip("/")
        if "paper-api.alpaca.markets" not in self.base:
            raise RuntimeError("endpoint is not the paper endpoint; refusing to trade")
        self.h = {"APCA-API-KEY-ID": cfg("ALPACA_KEY") or "", "APCA-API-SECRET-KEY": cfg("ALPACA_SECRET") or ""}
        if not self.h["APCA-API-KEY-ID"] or not self.h["APCA-API-SECRET-KEY"]:
            raise RuntimeError("Alpaca key or secret missing in config.txt")

    def req(self, method, path, **kw):
        url = path if path.startswith("http") else self.base + path
        for i in range(3):
            r = requests.request(method, url, headers=self.h, timeout=40, **kw)
            if r.status_code == 429:
                time.sleep(2 + 2 * i)
                continue
            return r
        return r

    def get(self, path, **kw):
        r = self.req("GET", path, **kw)
        r.raise_for_status()
        return r.json()


def us_only(tickers):
    return [t for t in tickers if US_RE.match(t or "")]


def plan_targets(state_csv=None):
    """{symbol: dollars} for the plan bucket, and the cohort label."""
    path = os.path.join(HERE, "portfolio_state.csv")
    if not os.path.exists(path):
        return {}, None
    st = pd.read_csv(path, dtype=str, keep_default_na=False)
    if st.empty:
        return {}, None
    row = st.iloc[-1]
    picks = us_only([t for t in row["picks"].split(";") if t])
    cap = BASE_CAP * PLAN_SHARE
    tg = {"VT": cap * CORE_W}
    if picks:
        for t in picks:
            tg[t] = tg.get(t, 0.0) + cap * SLEEVE_W / len(picks)
    else:
        tg["VT"] = cap
    return tg, row["cohort"]


def ai_targets():
    path = os.path.join(HERE, "ai_basket.csv")
    if not os.path.exists(path):
        return {}
    st = pd.read_csv(path, dtype={"ticker": str})
    tk = us_only(list(st["ticker"]))
    if not tk:
        return {}
    cap = BASE_CAP * AI_SHARE
    return {t: cap / len(tk) for t in tk}


def last_price(c, sym):
    try:
        r = c.req("GET", f"{DATA}/v2/stocks/{sym}/trades/latest", params={"feed": "iex"})
        if r.ok:
            return float(r.json()["trade"]["p"])
    except Exception:
        pass
    return None


def place(c, sym, usd, side, log):
    """One market order of |usd| dollars. Returns True when accepted."""
    usd = round(abs(usd), 2)
    try:
        a = c.req("GET", f"/assets/{sym}")
        if not a.ok:
            log.append(f"{sym}: نماد در Alpaca نیست")
            return False
        info = a.json()
        if not info.get("tradable"):
            log.append(f"{sym}: قابل‌معامله نیست")
            return False
        body = {"symbol": sym, "side": side, "type": "market", "time_in_force": "day"}
        if info.get("fractionable"):
            body["notional"] = f"{usd:.2f}"
        else:
            px = last_price(c, sym)
            if not px:
                log.append(f"{sym}: قیمت برای سفارش پیدا نشد")
                return False
            q = math.floor(usd / px)
            if q < 1:
                log.append(f"{sym}: مبلغ کمتر از یک سهم")
                return False
            body["qty"] = str(q)
        r = c.req("POST", "/orders", json=body)
        if r.ok:
            return True
        log.append(f"{sym}: سفارش رد شد ({r.status_code}: {r.text[:80]})")
    except Exception as e:
        log.append(f"{sym}: خطا ({type(e).__name__})")
    return False


def sync_bucket(c, bucket, target, state, log):
    """Moves a bucket from its recorded dollars to `target`. Returns number of orders sent."""
    rec = state.setdefault(bucket, {})
    n = 0
    others = {s for b, d in state.items() if isinstance(d, dict) and b != bucket for s in d}
    for sym in sorted(set(rec) | set(target)):
        delta = target.get(sym, 0.0) - rec.get(sym, 0.0)
        if abs(delta) < MIN_TRADE:
            continue
        if delta < 0 and sym not in target and sym not in others:
            r = c.req("DELETE", f"/positions/{sym}")      # closes the whole position
            ok = r.ok or r.status_code == 404
            if not ok:
                log.append(f"{sym}: بستن ناموفق ({r.status_code})")
        else:
            ok = place(c, sym, delta, "buy" if delta > 0 else "sell", log)
        if ok:
            n += 1
            if sym in target:
                rec[sym] = target[sym]
            else:
                rec.pop(sym, None)
    return n


def run(pre):
    """Returns (telegram_blocks, summary_lines, state_changed, warnings)."""
    today = dt.date.today()
    try:
        c = Client()
    except Exception as e:
        return ["⚠️ " + html.escape(f"Alpaca: {e}")], [], False
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    log, orders, changed = [], 0, False
    try:
        acct = c.get("/account")
    except Exception as e:
        return [], [], False, [f"Alpaca: اتصال یا کلید ناموفق ({type(e).__name__})"]
    existing = []
    if not state.get("plan") and not state.get("ai"):
        try:
            existing = c.get("/positions")
        except Exception:
            existing = []
    if acct.get("trading_blocked") or acct.get("account_blocked"):
        log.append("حساب Alpaca مسدود است")
    elif existing:
        log.append("حساب از قبل سهم دارد و فایل وضعیت خالی است؛ برای جلوگیری از خرید تکراری معامله نشد")
    else:
        plan, cohort = plan_targets()
        if plan and (state.get("plan_cohort") != cohort):
            n = sync_bucket(c, "plan", plan, state, log)
            orders += n
            if n or not plan:
                state["plan_cohort"] = cohort
            changed = changed or n > 0
        if not state.get("ai_done"):
            ai = ai_targets()
            if ai:
                n = sync_bucket(c, "ai", ai, state, log)
                orders += n
                if n:
                    state["ai_done"] = today.isoformat()
                    changed = True
        if orders and not state.get("started"):
            state["started"] = today.isoformat()
        changed = changed or orders > 0
    json.dump(state, open(STATE, "w"), ensure_ascii=False)
    try:
        pos = c.get("/positions")
        acct = c.get("/account")
    except Exception:
        pos = []
    eq, cash = float(acct.get("equity", 0)), float(acct.get("cash", 0))
    last_eq = float(acct.get("last_equity", eq) or eq)
    day_pct = (eq / last_eq - 1) * 100 if last_eq else 0.0
    since_pct = (eq / BASE_CAP - 1) * 100
    head = [f"{'Account':<10}{'Value$':>10}{'Day%':>7}{'Since%':>8}", "-" * 35,
            f"{'Paper':<10}{eq:>10,.0f}{day_pct:>+7.1f}{since_pct:>+8.1f}",
            f"{'Cash':<10}{cash:>10,.0f}"]
    blocks = [f"🏦 <b>حساب آزمایشی Alpaca (پول مجازی)</b> — {today}\n"
              "<i>سبد پیشنهادی (نیمی از سرمایه: ۷۰٪ VT + ۳۰٪ سهم‌های آمریکایی بخش مومنتوم) و سبد ۲۰ سهمی هوش مصنوعی (نیم دیگر) "
              "با سفارش‌های واقعی در حساب Paper ثبت شده‌اند. بخش مومنتوم فقط سهم‌های آمریکایی دارد، چون Alpaca بازار دیگری ندارد. "
              "Since% نسبت به سرمایه‌ی اولیه‌ی ۱۰۰ هزار دلاری.</i>", pre(head)]
    if pos:
        rows = sorted(pos, key=lambda p: -float(p.get("market_value", 0)))[:25]
        t = [f"{'Symbol':<7}{'Value$':>9}{'P&L%':>8}{'Day%':>7}", "-" * 31]
        for p in rows:
            t.append(f"{p['symbol'][:6]:<7}{float(p['market_value']):>9,.0f}"
                     f"{float(p.get('unrealized_plpc', 0)) * 100:>+8.1f}{float(p.get('unrealized_intraday_plpc', 0)) * 100:>+7.1f}")
        blocks.append("📋 <b>سهم‌های حساب</b>\n" + pre(t))
    elif orders:
        blocks.append("⏳ سفارش‌ها ثبت شد و با باز شدن بازار آمریکا اجرا می‌شود؛ موجودی از اجرای بعدی دیده می‌شود.")
    if orders:
        blocks.append(f"🧾 امروز {orders} سفارش جدید ثبت شد.")
    if log:
        blocks.append("⚠️ " + html.escape("؛ ".join(log[:6])))
    blocks.append("<i>این حساب آزمایشی است و پول واقعی در آن نیست. نتیجه‌ی آن دقیق‌تر از سبد کاغذی است، چون قیمت اجرای واقعی را دارد.</i>")
    hl = [f"• حساب Alpaca: {eq:,.0f}$ ({since_pct:+.1f}٪ از شروع)."]
    return blocks, hl, changed
