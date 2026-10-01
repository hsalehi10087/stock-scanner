#!/usr/bin/env python3
"""
اسکنر روزانه RSI / MACD برای بازارهای آمریکا، ژاپن، هند و تایوان
خروجی: پیام تلگرام + فایل CSV کامل + تاریخچه‌ی عملکرد سیگنال‌ها

متغیرهای محیطی:
  TELEGRAM_BOT_TOKEN  توکن ربات (از BotFather)
  TELEGRAM_CHAT_ID    شناسه‌ی چت شما
  DRY_RUN=1           فقط چاپ در خروجی، بدون ارسال به تلگرام
  MAX_PER_MARKET      حداکثر نماد هر بازار در هر بخش پیام (پیش‌فرض ۲۵)
"""
import datetime as dt
import html
import io
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))


def _read_config():
    """Settings from config.txt (KEY=VALUE); environment variables take priority."""
    cfg = {}
    path = os.path.join(HERE, "config.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


_CFG = _read_config()
TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or _CFG.get("TELEGRAM_BOT_TOKEN", "")).strip()
CHAT_ID = (os.environ.get("TELEGRAM_CHAT_ID") or _CFG.get("TELEGRAM_CHAT_ID", "")).strip()
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MAX_PER_MARKET = int(os.environ.get("MAX_PER_MARKET", "25"))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

MARKETS = {
    "US": "🇺🇸 آمریکا",
    "JP": "🇯🇵 ژاپن",
    "IN": "🇮🇳 هند",
    "TW": "🇹🇼 تایوان",
}

# ---------------------------------------------------------------------------
# Symbol lists
# ---------------------------------------------------------------------------
US_FALLBACK = """AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA BRK-B JPM V MA UNH XOM LLY JNJ PG HD
COST ABBV MRK CVX KO PEP WMT BAC ORCL CRM AMD NFLX ADBE CSCO INTC QCOM TXN AMAT MU LRCX KLAC
PLTR DIS MCD NKE PFE TMO ABT DHR GE CAT BA RTX LMT HON UPS GS MS WFC C AXP BLK SCHW PANW CRWD
NOW INTU UBER""".split()

JAPAN = [c + ".T" for c in """7203 6758 9984 8306 6861 9983 8035 6501 4063 7974 9432 9433 9434
8316 8411 8058 8031 8001 8053 8002 6098 4568 4502 4519 4503 6367 6954 6981 6902 7267 7201 7269
7270 6594 6702 6701 6752 6503 7011 7012 7013 6857 6146 6920 7741 4543 7733 4661 2914 2502 2503
3382 8267 9020 9022 9101 9104 9107 5401 5108 4901 7751 6273 6762 6971 8766 8725 8630 8591 8604
8801 8802 1925 1928 4452 4911 6301 6326 6988 3407 4188 5020 1605 9501 9503 4689 4755 6723 6526
7832 9766 9697 7735""".split()]

INDIA_FALLBACK = [s + ".NS" for s in """RELIANCE TCS HDFCBANK ICICIBANK INFY HINDUNILVR ITC SBIN
BHARTIARTL KOTAKBANK LT AXISBANK BAJFINANCE ASIANPAINT MARUTI HCLTECH SUNPHARMA TITAN ULTRACEMCO
WIPRO NESTLEIND ONGC NTPC POWERGRID M&M TATASTEEL JSWSTEEL ADANIENT ADANIPORTS COALINDIA
BAJAJFINSV TECHM HINDALCO GRASIM DRREDDY CIPLA DIVISLAB BRITANNIA EICHERMOT HEROMOTOCO BAJAJ-AUTO
APOLLOHOSP TATACONSUM SBILIFE HDFCLIFE INDUSINDBK BPCL SHRIRAMFIN TRENT BEL HAL DMART PIDILITIND
SIEMENS DLF VEDL TATAPOWER GODREJCP DABUR HAVELLS LTIM PERSISTENT IRCTC BANKBARODA PNB CANBK IOC
GAIL AMBUJACEM""".split()]

TAIWAN = [c + ".TW" for c in """2330 2317 2454 2308 2382 2881 2882 2412 2891 3711 2303 2886 2884
1216 2002 1301 1303 2357 3008 2345 3231 2379 3034 2885 2892 2880 5880 2883 2887 2890 1101 2207
2912 2603 2609 2615 3045 4904 2395 6669 3037 2327 4938 2301 1326 6505 1590 2408 3661 3443 2376
2356 3017 2383""".split()]


def get_sp500():
    """Full S&P 500 list from Wikipedia; fallback list on error."""
    try:
        r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                         headers=UA, timeout=30)
        table = pd.read_html(io.StringIO(r.text))[0]
        syms = [str(s).replace(".", "-") for s in table["Symbol"]]
        if len(syms) > 400:
            return syms
    except Exception as e:
        print("S&P 500 list failed, using fallback:", e)
    return US_FALLBACK


def get_nifty500():
    """Full Nifty 500 list from NSE; fallback list on error."""
    try:
        r = requests.get("https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
                         headers=UA, timeout=30)
        df = pd.read_csv(io.StringIO(r.text))
        syms = [str(s).strip() + ".NS" for s in df["Symbol"]]
        if len(syms) > 300:
            return syms
    except Exception as e:
        print("Nifty 500 list failed, using fallback:", e)
    return INDIA_FALLBACK


def read_extra():
    """Custom symbols from extra_tickers.txt - one per line: TICKER,MARKET"""
    extra = {m: [] for m in MARKETS}
    path = os.path.join(HERE, "extra_tickers.txt")
    if not os.path.exists(path):
        return extra
    for line in open(path, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line or "," not in line:
            continue
        t, m = [x.strip() for x in line.split(",", 1)]
        m = m.upper()
        if m in extra and t:
            extra[m].append(t)
    return extra


def build_universe():
    uni = {"US": get_sp500(), "JP": JAPAN, "IN": get_nifty500(), "TW": TAIWAN}
    for m, lst in read_extra().items():
        uni[m] = list(dict.fromkeys(uni[m] + lst))  # de-duplicate
    return uni


# ---------------------------------------------------------------------------
# Indicators (standard formulas; same logic as the website's Signals tab)
# ---------------------------------------------------------------------------
def ema(values, period):
    if len(values) < period:
        return np.array([])
    k = 2 / (period + 1)
    out = [values[:period].mean()]  # seed with SMA
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return np.array(out)


def macd(close, fast=12, slow=26, signal=9):
    if len(close) < slow + signal:
        return None
    ef, es = ema(close, fast), ema(close, slow)
    line = ef[len(ef) - len(es):] - es
    sig = ema(line, signal)
    if len(sig) == 0:
        return None
    hist = line[len(line) - len(sig):] - sig
    return {"macd": line[-1], "signal": sig[-1], "hist": hist[-1],
            "prev_hist": hist[-2] if len(hist) > 1 else None}


def rsi(close, period=14):
    if len(close) < period + 1:
        return None
    d = np.diff(close)
    gains, losses = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = gains[:period].mean(), losses[:period].mean()
    for g, l in zip(gains[period:], losses[period:]):
        ag = (ag * (period - 1) + g) / period
        al = (al * (period - 1) + l) / period
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def classify(m, r):
    """Signal code and Persian label"""
    if m is None or r is None:
        return "NA", "داده ناکافی"
    bull = m["hist"] > 0
    ph = m["prev_hist"]
    cross_up = ph is not None and ph <= 0 < m["hist"]
    cross_dn = ph is not None and ph >= 0 > m["hist"]
    if cross_up and r < 70:
        return "BUY", "تقاطع صعودی MACD"
    if bull and r < 30:
        return "BUY", "اشباع فروش"
    if cross_dn:
        return "SELL", "تقاطع نزولی MACD"
    if r > 70 and not bull:
        return "SELL", "اشباع خرید"
    if bull:
        return "UP", "روند مثبت"
    return "NEUTRAL", "خنثی/منفی"


# ---------------------------------------------------------------------------
# Data download
# ---------------------------------------------------------------------------
def extract_close(data, ticker, single):
    try:
        if isinstance(data.columns, pd.MultiIndex):
            lv0 = data.columns.get_level_values(0)
            if ticker in lv0:
                s = data[ticker]["Close"]
            elif "Close" in lv0:
                s = data["Close"]
                if isinstance(s, pd.DataFrame):
                    s = s[ticker] if ticker in s.columns else s.iloc[:, 0]
            else:
                return None
        else:
            s = data["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s = s.dropna()
        return s if len(s) else None
    except Exception:
        return None


def download_all(tickers, chunk=100):
    out = {}
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        data = None
        for attempt in range(3):
            try:
                data = yf.download(part, period="2y", interval="1d", group_by="ticker",
                                   auto_adjust=True, threads=True, progress=False)
                break
            except Exception as e:
                print(f"download retry {attempt + 1}: {e}")
                time.sleep(5 * (attempt + 1))
        if data is None or data.empty:
            continue
        for t in part:
            s = extract_close(data, t, len(part) == 1)
            if s is not None:
                out[t] = s
        time.sleep(1)
    return out


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def analyze(market, ticker, s):
    s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(s.index, "tz", None) else pd.to_datetime(s.index)
    if s.index[-1] < pd.Timestamp.now() - pd.Timedelta(days=7):
        return None  # stale data - probably suspended or delisted
    daily = s.values.astype(float)
    weekly = s.resample("W-FRI").last().dropna().values.astype(float)
    md, rd = macd(daily), rsi(daily)
    mw, rw = macd(weekly), rsi(weekly)
    d_code, d_label = classify(md, rd)
    w_code, w_label = classify(mw, rw)
    chg = (daily[-1] / daily[-2] - 1) * 100 if len(daily) > 1 else None
    return {
        "market": market, "ticker": ticker,
        "last_date": s.index[-1].strftime("%Y-%m-%d"),
        "close": round(daily[-1], 2),
        "chg_pct": round(chg, 2) if chg is not None else None,
        "daily_signal": d_code, "daily_reason": d_label,
        "daily_rsi": round(rd, 1) if rd is not None else None,
        "daily_hist": round(md["hist"], 4) if md else None,
        "weekly_signal": w_code, "weekly_reason": w_label,
        "weekly_rsi": round(rw, 1) if rw is not None else None,
        "weekly_hist": round(mw["hist"], 4) if mw else None,
        "aligned": d_code == "BUY" and w_code in ("BUY", "UP"),
    }


# ---------------------------------------------------------------------------
# Signal history & performance tracking (signals_history.csv in the repo)
# ---------------------------------------------------------------------------
HIST_PATH = os.path.join(HERE, "signals_history.csv")
HIST_COLS = ["signal_date", "market", "ticker", "timeframe", "side", "reason", "aligned",
             "entry_price", "last_date", "last_price", "return_pct", "max_return", "min_return",
             "days", "status", "close_date", "close_reason"]
HOLD_DAYS = {"D": 60, "W": 180}   # tracking period in calendar days, then the signal is closed


def load_history():
    if os.path.exists(HIST_PATH):
        h = pd.read_csv(HIST_PATH, dtype=str, keep_default_na=False)
        for c in HIST_COLS:
            if c not in h.columns:
                h[c] = ""
        return h[HIST_COLS].astype(object)
    return pd.DataFrame(columns=HIST_COLS).astype(object)


def side_return(side, entry, price):
    return (price / entry - 1) * 100 if side == "BUY" else (1 - price / entry) * 100


def _close(h, i, date, reason):
    h.at[i, "status"] = "CLOSED"
    h.at[i, "close_date"] = date
    h.at[i, "close_reason"] = reason


def update_history(cur):
    """Mark open signals to market, close expired/reversed ones, add today's new signals."""
    h = load_history()
    prices = {(r.market, r.ticker): (float(r.close), r.last_date) for r in cur.itertuples()}

    # 1) update every open signal with today's price
    for i in h.index[h["status"] == "OPEN"]:
        key = (h.at[i, "market"], str(h.at[i, "ticker"]))
        if key not in prices:
            continue
        price, d = prices[key]
        ret = side_return(h.at[i, "side"], float(h.at[i, "entry_price"]), price)
        h.at[i, "last_price"] = round(price, 4)
        h.at[i, "last_date"] = d
        h.at[i, "return_pct"] = round(ret, 2)
        h.at[i, "max_return"] = round(max(float(h.at[i, "max_return"] or 0), ret), 2)
        h.at[i, "min_return"] = round(min(float(h.at[i, "min_return"] or 0), ret), 2)
        days = (pd.Timestamp(d) - pd.Timestamp(h.at[i, "signal_date"])).days
        h.at[i, "days"] = days
        if days >= HOLD_DAYS.get(h.at[i, "timeframe"], 60):
            _close(h, i, d, "پایان دوره‌ی پیگیری")

    # 2) new signals; an opposite signal closes the open one on the same symbol/timeframe
    new = []
    for r in cur.itertuples():
        for tf, sig, reason in (("D", r.daily_signal, r.daily_reason),
                                ("W", r.weekly_signal, r.weekly_reason)):
            if sig not in ("BUY", "SELL"):
                continue
            same = (h["market"] == r.market) & (h["ticker"].astype(str) == r.ticker) & (h["timeframe"] == tf)
            opposite = "SELL" if sig == "BUY" else "BUY"
            for i in h.index[same & (h["status"] == "OPEN") & (h["side"] == opposite)]:
                _close(h, i, r.last_date, "سیگنال مخالف")
            if (same & (h["status"] == "OPEN") & (h["side"] == sig)).any():
                continue  # already tracking this signal
            if (same & (h["side"] == sig) & (h["signal_date"] == r.last_date)).any():
                continue  # same-day re-run
            new.append({
                "signal_date": r.last_date, "market": r.market, "ticker": r.ticker,
                "timeframe": tf, "side": sig, "reason": reason,
                "aligned": bool(r.aligned) if tf == "D" else False,
                "entry_price": r.close, "last_date": r.last_date, "last_price": r.close,
                "return_pct": 0.0, "max_return": 0.0, "min_return": 0.0, "days": 0,
                "status": "OPEN", "close_date": "", "close_reason": "",
            })
    if new:
        h = pd.concat([h, pd.DataFrame(new, columns=HIST_COLS).astype(object)], ignore_index=True)
    h.to_csv(HIST_PATH, index=False)
    return h, len(new)


def perf_section(h, new_count):
    side_fa = {"BUY": "خرید", "SELL": "فروش"}
    tf_fa = {"D": "روزانه", "W": "هفتگی"}
    lines = ["📈 <b>عملکرد سیگنال‌های قبلی</b>",
             "<i>بازده از روز سیگنال تا امروز؛ در سیگنال فروش، افت قیمت = سود</i>"]
    hh = h.copy()
    hh["days_n"] = pd.to_numeric(hh["days"], errors="coerce").fillna(0)
    hh["ret_n"] = pd.to_numeric(hh["return_pct"], errors="coerce").fillna(0)
    seasoned = hh[hh["days_n"] >= 1]
    if seasoned.empty:
        lines.append(f"تاریخچه از امروز شروع شد · {new_count} سیگنال جدید ثبت شد. "
                     "از اسکن بعدی، بازدهی هر سیگنال اینجا نمایش داده می‌شود.")
        return "\n".join(lines)
    groups = [("⭐ هم‌راستا", seasoned[seasoned["aligned"].astype(str) == "True"])]
    for tf in ("D", "W"):
        for side in ("BUY", "SELL"):
            groups.append((f"{side_fa[side]} {tf_fa[tf]}",
                           seasoned[(seasoned["timeframe"] == tf) & (seasoned["side"] == side)]))
    for label, sub in groups:
        if sub.empty:
            continue
        win = (sub["ret_n"] > 0).mean() * 100
        lines.append(f"• {label}: {len(sub)} سیگنال · موفق {win:.0f}% · میانگین {sub['ret_n'].mean():+.2f}%")

    def row(r):
        return (f"{html.escape(str(r.ticker))} {side_fa[r.side]} {tf_fa[r.timeframe]} "
                f"از {r.signal_date} ({int(r.days_n)} روز): <b>{r.ret_n:+.1f}%</b>")

    open_ = seasoned[seasoned["status"] == "OPEN"].sort_values("ret_n", ascending=False)
    if len(open_):
        lines += ["", "🏆 <b>بهترین سیگنال‌های باز</b>"]
        lines += [row(r) for r in open_.head(5).itertuples()]
        if len(open_) > 5:
            lines.append("📉 <b>ضعیف‌ترین سیگنال‌های باز</b>")
            lines += [row(r) for r in open_.tail(5).iloc[::-1].itertuples()]
    lines.append(f"\nسیگنال جدید امروز: {new_count} · کل سیگنال‌های ثبت‌شده: {len(h)}")
    return "\n".join(lines)


def git_save(paths, msg):
    """Commit the history file back to the repo (only inside GitHub Actions)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return True

    def run(*cmd):
        r = subprocess.run(cmd, capture_output=True, text=True)
        print("$", " ".join(cmd), "->", r.returncode, r.stdout[-300:], r.stderr[-300:])
        return r.returncode == 0

    run("git", "config", "user.name", "scanner-bot")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", *paths)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return True  # nothing to commit
    if not run("git", "commit", "-m", msg):
        return False
    for _ in range(3):
        if run("git", "push"):
            return True
        run("git", "pull", "--rebase")
    return False


# ---------------------------------------------------------------------------
# Telegram message
# ---------------------------------------------------------------------------
def fmt_list(df):
    lines = []
    for m, label in MARKETS.items():
        sub = df[df.market == m]
        if sub.empty:
            continue
        items = [f"{html.escape(r.ticker)} ({r.daily_rsi if r.daily_rsi is not None else '—'})"
                 for r in sub.head(MAX_PER_MARKET).itertuples()]
        more = f" … +{len(sub) - MAX_PER_MARKET}" if len(sub) > MAX_PER_MARKET else ""
        lines.append(f"<b>{label}</b> ({len(sub)}): " + "، ".join(items) + more)
    return "\n".join(lines) if lines else "—"


def build_message(df, scanned, total, perf=""):
    today = dt.date.today().strftime("%Y-%m-%d")
    aligned = df[df.aligned].sort_values("daily_rsi")
    d_buy = df[(df.daily_signal == "BUY") & ~df.aligned].sort_values("daily_rsi")
    d_sell = df[df.daily_signal == "SELL"].sort_values("daily_rsi", ascending=False)
    w_buy = df[df.weekly_signal == "BUY"].sort_values("weekly_rsi")
    w_sell = df[df.weekly_signal == "SELL"].sort_values("weekly_rsi", ascending=False)
    parts = [
        f"📡 <b>اسکن روزانه RSI/MACD</b> — {today}",
        f"بررسی‌شده: {scanned} از {total} نماد · عدد داخل پرانتز = RSI",
        "",
        "⭐ <b>خرید روزانه + روند هفتگی مثبت (قوی‌ترین)</b>", fmt_list(aligned), "",
        "🟢 <b>سایر سیگنال‌های خرید روزانه</b>", fmt_list(d_buy), "",
        "🟢 <b>سیگنال خرید هفتگی</b>", fmt_list(w_buy), "",
        "🔴 <b>سیگنال فروش روزانه</b>", fmt_list(d_sell), "",
        "🔴 <b>سیگنال فروش هفتگی</b>", fmt_list(w_sell), "",
        perf, "",
        "<i>فهرست کامل در فایل CSV پیوست. این خروجی صرفاً غربالگری فنی است، نه توصیه‌ی خرید و فروش.</i>",
    ]
    return "\n".join(parts)


def split_message(text, limit=3900):
    chunks, cur = [], ""
    for line in text.split("\n"):
        pieces = [line[i:i + limit] for i in range(0, len(line), limit)] or [""]
        for piece in pieces:
            if len(cur) + len(piece) + 1 > limit and cur:
                chunks.append(cur)
                cur = ""
            cur += piece + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


def tg(method, **kw):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    r = requests.post(url, timeout=60, **kw)
    if not r.ok:
        print("Telegram error:", r.status_code, r.text[:300])
    return r.ok


def send(text, csv_bytes, filename, extra_docs=()):
    if DRY_RUN or not TOKEN or not CHAT_ID:
        print(text)
        print(f"\n[DRY RUN] CSV {filename}: {len(csv_bytes)} bytes")
        return
    for chunk in split_message(text):
        tg("sendMessage", data={"chat_id": CHAT_ID, "text": chunk,
                                "parse_mode": "HTML", "disable_web_page_preview": True})
    for fn, data in [(filename, csv_bytes), *extra_docs]:
        if data:
            tg("sendDocument", data={"chat_id": CHAT_ID},
               files={"document": (fn, data, "text/csv")})


# ---------------------------------------------------------------------------
def main():
    uni = build_universe()
    total = sum(len(v) for v in uni.values())
    print("Universe:", {m: len(v) for m, v in uni.items()}, "total", total)
    rows = []
    for market, tickers in uni.items():
        series = download_all(tickers)
        print(f"{market}: downloaded {len(series)}/{len(tickers)}")
        for t, s in series.items():
            try:
                res = analyze(market, t, s)
                if res:
                    rows.append(res)
            except Exception as e:
                print("analyze failed", t, e)
    if not rows:
        send("⚠️ اسکنر امروز هیچ داده‌ای دریافت نکرد (احتمالاً اختلال موقت منبع داده).",
             b"", "empty.csv")
        return 1
    df = pd.DataFrame(rows)
    csv = df.sort_values(["market", "daily_signal", "ticker"]).to_csv(index=False).encode("utf-8-sig")
    perf = ""
    hist_csv = b""
    try:
        h, new_count = update_history(df)
        perf = perf_section(h, new_count)
        if not git_save([os.path.basename(HIST_PATH)], f"Signal history {dt.date.today()}"):
            perf += "\n⚠️ ذخیره‌ی تاریخچه در GitHub ناموفق بود."
        hist_csv = h.sort_values(["status", "signal_date"], ascending=[False, False]) \
                    .to_csv(index=False).encode("utf-8-sig")
    except Exception as e:
        print("history failed:", e)
        perf = f"⚠️ خطا در به‌روزرسانی تاریخچه: {html.escape(str(e))[:200]}"
    send(build_message(df, len(df), total, perf), csv, f"signals-{dt.date.today()}.csv",
         extra_docs=[("signals-history.csv", hist_csv)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
