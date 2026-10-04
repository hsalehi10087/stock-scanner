"""Suggested stop-loss for the strongest buys, in units of each stock's normal daily move (ATR)."""
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
K = 3      # stop = price - K x "normal daily move" (14-day average of the absolute close-to-close change)


def _study():
    """(hold, stop) result rows for D-BUY from the ATR experiment (backtest_atr.json), if it has been run."""
    path = os.path.join(HERE, "backtest_atr.json")
    if not os.path.exists(path):
        return None
    try:
        rows = json.load(open(path, encoding="utf-8"))["rows"]
        get = lambda rule: next(r for r in rows if r["set"] == "D-BUY" and r["rule"] == rule)
        return get("Hold60"), get(f"S{K} only"), get("S3/T6")
    except Exception:
        return None


def block(df, pre, short, fmt_price, top=12):
    if "unit" not in df.columns:
        return []
    s = df[df.aligned & df.unit.notna() & (df.unit > 0)].copy()
    if s.empty:
        return []
    s["stop"] = s.close - K * s.unit
    s = s[s.stop > 0].sort_values("daily_rsi").head(top)
    if s.empty:
        return []
    t = [f"{'Symbol':<8}{'Mk':<3}{'Price':>9}{'Stop':>9}{'Risk%':>6}", "-" * 35]
    for r in s.itertuples():
        t.append(f"{short(r.ticker)[:8]:<8}{r.market:<3}{fmt_price(r.close):>9}{fmt_price(r.stop):>9}"
                 f"{K * r.unit / r.close * 100:>6.1f}")
    txt = ("🛡 <b>حد ضرر پیشنهادی برای قوی‌ترین خریدها</b>\n"
           f"<i>Stop = قیمت منهای {K} برابر نوسان روزانه‌ی معمولِ همان سهم (از قیمت‌های پایانی)؛ "
           "Risk% = فاصله‌ی حد ضرر تا قیمت فعلی. فقط برای خریدهای روزانه‌ی هم‌جهت با روند هفتگی (⭐).</i>\n"
           "<pre>" + html.escape("\n".join(t)) + "</pre>")
    st = _study()
    if st:
        hold, stop, tgt = st
        txt += (f"\nچرا این عدد؟ در آزمون دوساله، بدون حد ضرر بدترین ۵٪ معامله‌ها {hold['p5']:.0f}٪ زیان داشتند؛ "
                f"با حد ضرر {K} برابری به {stop['p5']:.0f}٪ رسید. بهایش این بود که میانگین بازده سه‌ماهه از "
                f"{hold['avg']:+.1f}٪ به {stop['avg']:+.1f}٪ کم شد. یعنی حد ضرر سود نمی‌سازد؛ فقط جلوی زیان‌های خیلی بزرگ را می‌گیرد. "
                f"هدف قیمتی هم نگذاشتیم، چون در آزمون میانگین بازده را به {tgt['avg']:+.1f}٪ رساند و سودهای بزرگ را زود قطع می‌کرد.")
    else:
        txt += "\nحد ضرر سود نمی‌سازد؛ فقط جلوی زیان‌های خیلی بزرگ را می‌گیرد. هدف قیمتی نگذاشتیم، چون سودهای بزرگ را زود قطع می‌کند."
    return [txt + "\n<i>توصیه‌ی خرید یا فروش نیست.</i>"]
