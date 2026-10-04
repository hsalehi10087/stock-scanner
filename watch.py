"""
Personal watchlist: a compact status table of YOUR stocks every day, plus alerts when something notable
happens (new buy/sell signal, big move, extreme RSI, earnings within a week).
Edit watchlist.txt to change the list. One line per stock: SYMBOL,MARKET[,ENTRY_PRICE]
"""
import datetime as dt
import html
import os
from types import SimpleNamespace

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "watchlist.txt")
DEFAULT = "AVGO,US\nNBIS,US\nSOUN,US\nIONQ,US\nALAB,US\nICICIBANK.NS,IN\nLT.NS,IN\n"
STATE = {"BUY": "B", "SELL": "S", "UP": "+", "NEUTRAL": "-", "NA": "?"}


def read():
    text = open(PATH, encoding="utf-8").read() if os.path.exists(PATH) else DEFAULT
    items = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line or "," not in line:
            continue
        parts = [p.strip() for p in line.split(",")]
        entry = None
        if len(parts) > 2:
            try:
                entry = float(parts[2])
            except ValueError:
                entry = None
        items.append((parts[1].upper(), parts[0], entry))
    return items


def days_to_earnings(ticker):
    try:
        cal = yf.Ticker(ticker).calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if not dates:
            return None
        today = dt.date.today()
        future = [d for d in (x.date() if hasattr(x, "date") else x for x in dates) if d >= today]
        return (min(future) - today).days if future else None
    except Exception:
        return None


def build(df, download_all, analyze, pre, short, fmt_price):
    """Returns (message_blocks, alert_lines_for_summary)."""
    items = read()
    if not items:
        return [], []
    have = {(r.market, r.ticker): r for r in df.itertuples()}
    missing = [t for m, t, _ in items if (m, t) not in have]
    extra = {}
    if missing:
        series = download_all(missing)
        for m, t, _ in items:
            if (m, t) not in have and t in series:
                res = analyze(m, t, series[t])
                if res:
                    extra[(m, t)] = SimpleNamespace(**res)

    today = dt.date.today().strftime("%Y-%m-%d")
    table = [f"{'Symbol':<9}{'Price':>9}{'Day%':>6}{'RSI':>4} D W", "-" * 33]
    alerts, summary_lines = [], []
    for m, t, entry in items:
        r = have.get((m, t)) or extra.get((m, t))
        if r is None:
            table.append(f"{short(t)[:9]:<9}{'no data':>9}")
            continue
        chg = r.chg_pct if r.chg_pct == r.chg_pct else None
        rsi_d = r.daily_rsi if r.daily_rsi == r.daily_rsi else None
        table.append(f"{short(t)[:9]:<9}{fmt_price(r.close):>9}"
                     f"{(f'{chg:+.1f}' if chg is not None else '-'):>6}"
                     f"{(f'{rsi_d:.0f}' if rsi_d is not None else '-'):>4} "
                     f"{STATE.get(r.daily_signal, '?')} {STATE.get(r.weekly_signal, '?')}")
        flags = []
        if r.daily_signal in ("BUY", "SELL"):
            flags.append(("سیگنال خرید روزانه" if r.daily_signal == "BUY" else "سیگنال فروش روزانه")
                         + f" ({r.daily_reason})")
        if r.weekly_signal in ("BUY", "SELL"):
            flags.append(("سیگنال خرید هفتگی" if r.weekly_signal == "BUY" else "سیگنال فروش هفتگی")
                         + f" ({r.weekly_reason})")
        if chg is not None and abs(chg) >= 5:
            flags.append(f"امروز {chg:+.1f}٪ تغییر کرد")
        if rsi_d is not None and rsi_d >= 75:
            flags.append(f"خیلی سریع بالا رفته (RSI {rsi_d:.0f}) و ممکن است کمی عقب بنشیند")
        if rsi_d is not None and rsi_d <= 25:
            flags.append(f"خیلی سریع پایین آمده (RSI {rsi_d:.0f}) و ممکن است کمی برگردد")
        d = days_to_earnings(t)
        if d is not None and 0 <= d <= 7:
            flags.append("گزارش مالی " + ("امروز" if d == 0 else f"تا {d} روز دیگر") + " منتشر می‌شود")
        if entry:
            pnl = (r.close / entry - 1) * 100
            unit = getattr(r, "unit", None)
            atr = (unit / r.close * 100) if unit and unit == unit and r.close else None
            if atr and r.close <= entry * (1 - 5 * atr / 100):
                flags.append(f"قیمت از حد ضرر ۵ برابر نوسان زیر قیمت خرید شما پایین‌تر آمده ({pnl:+.1f}٪)")
        if flags:
            alerts.append(f"• <b>{html.escape(short(t))}:</b> " + "؛ ".join(flags) + ".")
            summary_lines.append(f"• {html.escape(short(t))}: " + "؛ ".join(flags[:2]) + ".")

    blocks = [f"👀 <b>سهم‌های شما</b> — {today}\n"
              "<i>Day% تغییر امروز · RSI شدت صعود/نزول (بالای ۷۰ زیاد، زیر ۳۰ کم) · "
              "D و W وضعیت روزانه و هفتگی: B خرید، S فروش، + روند مثبت، - خنثی یا منفی</i>",
              pre(table)]
    blocks.append("<b>هشدارها</b>\n" + "\n".join(alerts) if alerts else "امروز برای سهم‌های شما هشداری نبود.")
    blocks.append("<i>فهرست را می‌شود عوض کرد: از Claude بخواهید سهمی را اضافه یا حذف کند.</i>")
    return blocks, summary_lines or ["• امروز برای سهم‌های شما هشدار خاصی نبود."]
