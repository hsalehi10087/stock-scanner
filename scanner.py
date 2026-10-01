#!/usr/bin/env python3
"""
Daily RSI / MACD scanner for US, Japan, India, Taiwan, China stocks + metals, energy and FX majors,
plus a fundamental ranking (sales & profit growth) for US, China and Japan.
Output: Telegram message (aligned tables) + CSV files + signal history with performance.

Environment variables:
  TELEGRAM_BOT_TOKEN  bot token (from BotFather)
  TELEGRAM_CHAT_ID    your chat id
  DRY_RUN=1           print only, do not send to Telegram
  MAX_PER_MARKET      max symbols per market per message section (default 15)
  FUND_TOP            top symbols per market in the fundamental ranking (default 15)
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
MAX_PER_MARKET = int(os.environ.get("MAX_PER_MARKET", "15"))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

MARKETS = {
    "US": "🇺🇸 آمریکا",
    "JP": "🇯🇵 ژاپن",
    "IN": "🇮🇳 هند",
    "TW": "🇹🇼 تایوان",
    "CN": "🇨🇳 چین",
    "CM": "🛢 فلزات و انرژی",
    "FX": "💱 جفت‌ارزها",
}

# Commodities (futures) and FX majors - Yahoo Finance symbols with readable names
COMMODITIES = {
    "GC=F": "Gold", "SI=F": "Silver", "HG=F": "Copper", "PL=F": "Platinum",
    "PA=F": "Palladium", "ALI=F": "Aluminum",
    "CL=F": "WTI-Oil", "BZ=F": "Brent-Oil", "NG=F": "NatGas", "HO=F": "Heating-Oil",
}
FOREX = {
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY", "USDCHF=X": "USDCHF",
    "AUDUSD=X": "AUDUSD", "USDCAD=X": "USDCAD", "NZDUSD=X": "NZDUSD", "DX-Y.NYB": "DXY",
}
NAMES = {**COMMODITIES, **FOREX}

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

CHINA = """600519.SS 601318.SS 600036.SS 601398.SS 601288.SS 601939.SS 601988.SS 600900.SS 601857.SS
600028.SS 601166.SS 600276.SS 600030.SS 601012.SS 600309.SS 601888.SS 600887.SS 601899.SS 600031.SS
601668.SS 600585.SS 601088.SS 600050.SS 601728.SS 600941.SS 688981.SS 601633.SS 600104.SS 601601.SS
601628.SS 600016.SS 600000.SS 601328.SS 600048.SS 601919.SS 600690.SS 603288.SS 600809.SS 603259.SS
688111.SS 000858.SZ 300750.SZ 000333.SZ 002594.SZ 000651.SZ 002415.SZ 300059.SZ 000001.SZ 000568.SZ
002475.SZ 300760.SZ 002714.SZ 300124.SZ 002352.SZ 000725.SZ 002230.SZ 300274.SZ 002371.SZ 000063.SZ
300015.SZ 0700.HK 9988.HK 3690.HK 1810.HK 9618.HK 9999.HK 1211.HK 2318.HK 0941.HK 9888.HK 2020.HK
1024.HK 9961.HK 0981.HK BABA PDD JD BIDU NIO LI XPEV TCOM NTES BEKE""".split()


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
    uni = {"US": get_sp500(), "JP": JAPAN, "IN": get_nifty500(), "TW": TAIWAN, "CN": CHINA,
           "CM": list(COMMODITIES), "FX": list(FOREX)}
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
        "close": round(daily[-1], 5 if daily[-1] < 10 else 2),
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
        h.at[i, "last_price"] = round(price, 5)
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


def perf_blocks(h, new_count):
    title = "📈 <b>عملکرد سیگنال‌های قبلی</b>"
    hh = h.copy()
    hh["days_n"] = pd.to_numeric(hh["days"], errors="coerce").fillna(0)
    hh["ret_n"] = pd.to_numeric(hh["return_pct"], errors="coerce").fillna(0)
    seasoned = hh[hh["days_n"] >= 1]
    if seasoned.empty:
        return [f"{title}\nتاریخچه از امروز شروع شد · {new_count} سیگنال جدید ثبت شد. "
                "از اسکن بعدی، بازدهی هر سیگنال اینجا نمایش داده می‌شود."]
    groups = [("Aligned*", seasoned[seasoned["aligned"].astype(str) == "True"])]
    for tf in ("D", "W"):
        for side, s in (("BUY", "Buy"), ("SELL", "Sell")):
            groups.append((f"{s}-{tf}", seasoned[(seasoned["timeframe"] == tf) & (seasoned["side"] == side)]))
    rows = [f"{'Group':<10}{'N':>5}{'Win%':>7}{'Avg%':>8}", "-" * 30]
    for label, sub in groups:
        if sub.empty:
            continue
        win = (sub["ret_n"] > 0).mean() * 100
        rows.append(f"{label:<10}{len(sub):>5}{win:>7.0f}{sub['ret_n'].mean():>+8.2f}")
    blocks = [title + "\n<i>بازده از روز سیگنال تا امروز؛ در فروش، افت قیمت = سود</i>\n" + pre(rows) +
              "\n<i>D=روزانه · W=هفتگی · Aligned*=خرید روزانه هم‌جهت با روند هفتگی · "
              "Win%=درصد سیگنال‌های سودده</i>"]

    def table(sub):
        out = [f"{'Symbol':<12}{'Sig':<7}{'Date':<6}{'Days':>4}{'Ret%':>7}", "-" * 36]
        for r in sub.itertuples():
            sig = ("Buy" if r.side == "BUY" else "Sell") + "-" + r.timeframe
            out.append(f"{NAMES.get(str(r.ticker), str(r.ticker))[:12]:<12}{sig:<7}{str(r.signal_date)[5:]:<6}"
                       f"{int(r.days_n):>4}{r.ret_n:>+7.1f}")
        return pre(out)

    open_ = seasoned[seasoned["status"] == "OPEN"].sort_values("ret_n", ascending=False)
    if len(open_):
        b = "🏆 <b>بهترین سیگنال‌های باز</b>\n" + table(open_.head(5))
        if len(open_) > 5:
            b += "\n📉 <b>ضعیف‌ترین سیگنال‌های باز</b>\n" + table(open_.tail(5).iloc[::-1])
        blocks.append(b)
    blocks.append(f"سیگنال جدید امروز: {new_count} · کل سیگنال‌های ثبت‌شده: {len(h)}")
    return blocks


def git_save(paths, msg):
    """Commit data files back to the repo (only inside GitHub Actions)."""
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
# Telegram message (tables in <pre> blocks for clean alignment)
# ---------------------------------------------------------------------------
def short(ticker):
    if ticker in NAMES:
        return NAMES[ticker]
    for suf in (".NS", ".TW", ".SS", ".SZ", ".HK", ".T"):
        if ticker.endswith(suf):
            return ticker[: -len(suf)]
    return ticker


def num(v):
    try:
        f = float(v)
        return None if f != f else f  # NaN -> None
    except (TypeError, ValueError):
        return None


def fmt_price(p):
    p = num(p)
    if p is None:
        return "-"
    if p >= 10000:
        return f"{p:,.0f}"
    if p >= 100:
        return f"{p:.1f}"
    if p >= 10:
        return f"{p:.2f}"
    return f"{p:.4f}"


def pre(lines):
    return "<pre>" + html.escape("\n".join(lines)) + "</pre>"


def signal_table(sub, rsi_col):
    rows = [f"{'Symbol':<11}{'Price':>9}{'Chg%':>7}{'RSI':>5}", "-" * 32]
    for r in sub.head(MAX_PER_MARKET).itertuples():
        chg, rv = num(r.chg_pct), num(getattr(r, rsi_col))
        rows.append(f"{short(r.ticker)[:11]:<11}{fmt_price(r.close):>9}"
                    f"{(f'{chg:+.1f}' if chg is not None else '-'):>7}"
                    f"{(f'{rv:.0f}' if rv is not None else '-'):>5}")
    return pre(rows)


def section(title, df, rsi_col):
    if df.empty:
        return f"<b>{title}</b>\n—"
    out = [f"<b>{title}</b> ({len(df)})"]
    for m, label in MARKETS.items():
        sub = df[df.market == m]
        if sub.empty:
            continue
        out.append(f"{label} ({len(sub)})")
        out.append(signal_table(sub, rsi_col))
        if len(sub) > MAX_PER_MARKET:
            out.append(f"<i>+{len(sub) - MAX_PER_MARKET} مورد دیگر در فایل CSV</i>")
    return "\n".join(out)


def build_blocks(df, scanned, total, perf_blocks=()):
    today = dt.date.today().strftime("%Y-%m-%d")
    aligned = df[df.aligned].sort_values("daily_rsi")
    d_buy = df[(df.daily_signal == "BUY") & ~df.aligned].sort_values("daily_rsi")
    d_sell = df[df.daily_signal == "SELL"].sort_values("daily_rsi", ascending=False)
    w_buy = df[df.weekly_signal == "BUY"].sort_values("weekly_rsi")
    w_sell = df[df.weekly_signal == "SELL"].sort_values("weekly_rsi", ascending=False)
    return [
        f"📡 <b>اسکن روزانه RSI/MACD</b> — {today}\nبررسی‌شده: {scanned} از {total} نماد",
        section("⭐ خرید روزانه + روند هفتگی مثبت (قوی‌ترین)", aligned, "daily_rsi"),
        section("🟢 سایر سیگنال‌های خرید روزانه", d_buy, "daily_rsi"),
        section("🟢 سیگنال خرید هفتگی", w_buy, "weekly_rsi"),
        section("🔴 سیگنال فروش روزانه", d_sell, "daily_rsi"),
        section("🔴 سیگنال فروش هفتگی", w_sell, "weekly_rsi"),
        *perf_blocks,
        "<i>فهرست کامل و تاریخچه در فایل‌های CSV پیوست. این خروجی صرفاً غربالگری فنی است، نه توصیه‌ی خرید و فروش.</i>",
    ]


def chunk_blocks(blocks, limit=3900):
    chunks, cur = [], ""
    for b in blocks:
        if not b:
            continue
        if len(b) > limit:  # very large block: fall back to line splitting
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.extend(split_message(b, limit))
            continue
        if cur and len(cur) + len(b) + 2 > limit:
            chunks.append(cur)
            cur = ""
        cur += b + "\n\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


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


def send(blocks, csv_bytes, filename, extra_docs=()):
    if isinstance(blocks, str):
        blocks = [blocks]
    if DRY_RUN or not TOKEN or not CHAT_ID:
        for c in chunk_blocks(blocks):
            print(c)
            print("=" * 40)
        print(f"\n[DRY RUN] CSV {filename}: {len(csv_bytes)} bytes")
        return
    for chunk in chunk_blocks(blocks):
        tg("sendMessage", data={"chat_id": CHAT_ID, "text": chunk,
                                "parse_mode": "HTML", "disable_web_page_preview": True})
    for fn, data in [(filename, csv_bytes), *extra_docs]:
        if data:
            tg("sendDocument", data={"chat_id": CHAT_ID},
               files={"document": (fn, data, "text/csv")})


# ---------------------------------------------------------------------------
# Fundamental ranking: latest-quarter YoY sales & profit growth (US, China, Japan)
# ---------------------------------------------------------------------------
FUND_PATH = os.path.join(HERE, "fundamentals.csv")
WATCH_PATH = os.path.join(HERE, "fundamentals_watch.csv")
FUND_MARKETS = ("US", "CN", "JP")
FUND_MAX_AGE_DAYS = 7          # each symbol's fundamentals are refreshed weekly
FUND_TIME_BUDGET = 20 * 60     # seconds per run spent fetching fundamentals
FUND_TOP = int(os.environ.get("FUND_TOP", "15"))
WATCH_COLS = ["market", "ticker", "added_date", "entry_price", "last_date", "last_price",
              "return_pct", "days", "in_top"]


def _pct(v):
    v = num(v)
    return None if v is None else round(v * 100, 1)


def fetch_fundamental(ticker):
    t = yf.Ticker(ticker)
    rev = prof = None
    q, name = "", ""
    try:
        info = t.info or {}
        rev = _pct(info.get("revenueGrowth"))
        prof = _pct(info.get("earningsQuarterlyGrowth"))
        if prof is None:
            prof = _pct(info.get("earningsGrowth"))
        mrq = info.get("mostRecentQuarter")
        if mrq:
            q = dt.datetime.fromtimestamp(int(mrq), dt.timezone.utc).strftime("%Y-%m-%d")
        name = info.get("shortName") or ""
    except Exception as e:
        print("info failed", ticker, str(e)[:120])
    if rev is None or prof is None:  # fallback: compute YoY from quarterly statements
        try:
            qs = t.quarterly_income_stmt
            if qs is not None and qs.shape[1] >= 5:
                cols = sorted(qs.columns, reverse=True)

                def yoy(row):
                    if row not in qs.index:
                        return None
                    a, b = num(qs.at[row, cols[0]]), num(qs.at[row, cols[4]])
                    if a is None or not b:
                        return None
                    return round((a - b) / abs(b) * 100, 1)

                rev = rev if rev is not None else yoy("Total Revenue")
                prof = prof if prof is not None else yoy("Net Income")
                q = q or str(cols[0])[:10]
        except Exception as e:
            print("statement failed", ticker, str(e)[:120])
    return {"ticker": ticker, "name": str(name)[:40], "rev_growth": rev, "profit_growth": prof,
            "quarter_end": q, "fetched_at": dt.date.today().isoformat()}


def update_fundamentals(uni):
    from concurrent.futures import ThreadPoolExecutor
    cache = pd.read_csv(FUND_PATH, dtype={"ticker": str}) if os.path.exists(FUND_PATH) else pd.DataFrame()
    rows = {r["ticker"]: r for r in cache.to_dict("records")} if len(cache) else {}
    today = dt.date.today()

    def age(t):
        try:
            return (today - dt.date.fromisoformat(str(rows[t]["fetched_at"]))).days
        except Exception:
            return 10 ** 6  # never fetched

    targets = [(m, t) for m in FUND_MARKETS for t in uni.get(m, [])]
    stale = sorted([mt for mt in targets if age(mt[1]) >= FUND_MAX_AGE_DAYS], key=lambda mt: -age(mt[1]))
    print(f"fundamentals: {len(stale)} of {len(targets)} need refresh")
    start = time.time()
    with ThreadPoolExecutor(4) as ex:
        for i in range(0, len(stale), 40):
            if time.time() - start > FUND_TIME_BUDGET:
                print("fundamentals: time budget reached, rest continues next run")
                break
            batch = stale[i:i + 40]
            for (m, _), res in zip(batch, ex.map(lambda mt: fetch_fundamental(mt[1]), batch)):
                res["market"] = m
                rows[res["ticker"]] = res
    out = pd.DataFrame(list(rows.values()))
    out.to_csv(FUND_PATH, index=False)
    return out


def rank_fundamentals(fund):
    f = fund[fund["market"].isin(FUND_MARKETS)].copy()
    f["rev_growth"] = pd.to_numeric(f["rev_growth"], errors="coerce")
    f["profit_growth"] = pd.to_numeric(f["profit_growth"], errors="coerce")
    f = f.dropna(subset=["rev_growth", "profit_growth"])
    if f.empty:
        return f
    g = f.groupby("market")
    f["score"] = (g["rev_growth"].rank(pct=True) * 50 + g["profit_growth"].rank(pct=True) * 50).round(1)
    return f.sort_values(["market", "score"], ascending=[True, False])


def update_watch(top, prices):
    """Track price & return of each stock from the day it enters the top list."""
    w = pd.read_csv(WATCH_PATH, dtype=str, keep_default_na=False) if os.path.exists(WATCH_PATH) \
        else pd.DataFrame(columns=WATCH_COLS)
    w = w.reindex(columns=WATCH_COLS).fillna("").astype(object)
    known = set(zip(w["market"], w["ticker"]))
    new = []
    for r in top.itertuples():
        key = (r.market, r.ticker)
        if key not in known and key in prices:
            p, d = prices[key]
            new.append({"market": r.market, "ticker": r.ticker, "added_date": d, "entry_price": p,
                        "last_date": d, "last_price": p, "return_pct": 0.0, "days": 0, "in_top": True})
    if new:
        w = pd.concat([w, pd.DataFrame(new, columns=WATCH_COLS).astype(object)], ignore_index=True)
    top_keys = set(zip(top["market"], top["ticker"]))
    for i in w.index:
        key = (w.at[i, "market"], w.at[i, "ticker"])
        w.at[i, "in_top"] = key in top_keys
        if key in prices and num(w.at[i, "entry_price"]):
            p, d = prices[key]
            w.at[i, "last_price"] = p
            w.at[i, "last_date"] = d
            w.at[i, "return_pct"] = round((p / float(w.at[i, "entry_price"]) - 1) * 100, 2)
            w.at[i, "days"] = (pd.Timestamp(d) - pd.Timestamp(w.at[i, "added_date"])).days
    w.to_csv(WATCH_PATH, index=False)
    return w


def fund_blocks(ranked, watch, prices):
    labels = {"US": "🇺🇸 آمریکا", "CN": "🇨🇳 چین", "JP": "🇯🇵 ژاپن"}
    head = ("📊 <b>رتبه‌بندی بنیادی: رشد فروش و سود</b>\n"
            "<i>آخرین گزارش فصلی نسبت به فصل مشابه سال قبل · "
            "Ret% = بازده از روزی که نماد وارد این فهرست شد</i>")
    if ranked.empty:
        return [head + "\nداده‌ی بنیادی هنوز آماده نیست؛ در اجراهای بعدی تکمیل می‌شود."]
    wmap = {(r.market, r.ticker): r for r in watch.itertuples()}

    def g(v):
        v = num(v)
        if v is None:
            return "-"
        return f"{max(min(v, 999), -999):+.0f}"

    blocks = [head]
    for m in FUND_MARKETS:
        sub = ranked[ranked["market"] == m].head(FUND_TOP)
        if sub.empty:
            continue
        rows = [f"{'Symbol':<8}{'Sales%':>7}{'Prof%':>7}{'Price':>9}{'Ret%':>6}", "-" * 37]
        for r in sub.itertuples():
            p = prices.get((m, r.ticker), (None, None))[0]
            wr = wmap.get((m, r.ticker))
            ret = num(wr.return_pct) if wr is not None else None
            rows.append(f"{short(r.ticker)[:8]:<8}{g(r.rev_growth):>7}{g(r.profit_growth):>7}"
                        f"{fmt_price(p):>9}{(f'{ret:+.1f}' if ret is not None else '-'):>6}")
        n_all = (ranked["market"] == m).sum()
        blocks.append(f"{labels[m]} — {len(sub)} برتر از {n_all}\n" + pre(rows))
    return blocks


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
    perf = []
    hist_csv = b""
    try:
        h, new_count = update_history(df)
        perf = perf_blocks(h, new_count)
        hist_csv = h.sort_values(["status", "signal_date"], ascending=[False, False]) \
                    .to_csv(index=False).encode("utf-8-sig")
    except Exception as e:
        print("history failed:", e)
        perf = [f"⚠️ خطا در به‌روزرسانی تاریخچه: {html.escape(str(e))[:200]}"]

    fblocks, fund_csv = [], b""
    try:
        prices = {(r.market, r.ticker): (float(r.close), r.last_date) for r in df.itertuples()}
        ranked = rank_fundamentals(update_fundamentals(uni))
        top = ranked.groupby("market").head(FUND_TOP) if len(ranked) else ranked
        watch = update_watch(top, prices)
        fblocks = fund_blocks(ranked, watch, prices)
        if len(ranked):
            fund_csv = ranked.to_csv(index=False).encode("utf-8-sig")
    except Exception as e:
        print("fundamentals failed:", e)
        fblocks = [f"⚠️ خطا در رتبه‌بندی بنیادی: {html.escape(str(e))[:200]}"]

    saved = [os.path.basename(p) for p in (HIST_PATH, FUND_PATH, WATCH_PATH) if os.path.exists(p)]
    if not git_save(saved, f"Daily data {dt.date.today()}"):
        perf.append("⚠️ ذخیره‌ی تاریخچه در GitHub ناموفق بود.")
    send(build_blocks(df, len(df), total, perf + fblocks), csv, f"signals-{dt.date.today()}.csv",
         extra_docs=[("signals-history.csv", hist_csv), ("fundamentals-rank.csv", fund_csv)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
