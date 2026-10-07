"""
🤖 A 20-stock AI basket (paper trading from the first run, equal weight, buy and hold) with a model estimate of
the chance that each stock grows 10x in 5 years.

The estimate is a simple model, NOT a forecast: price follows a random walk (lognormal) with the stock's own
volatility over the last year and an assumed average yearly return of 15% (a normal market-like return) or 30%
(a very optimistic case). It ignores sudden jumps, bankruptcies and the fact that hot stocks mean-revert, so treat
it as a rough scale of how unlikely a 10x is, even for very volatile stocks.
State: ai_basket.csv (entry prices and the estimates, written once at the start).
"""
import datetime as dt
import html
import math
import os

import numpy as np
import pandas as pd

import method_test as mt

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "ai_basket.csv")
YEARS = 5
TARGET = 10.0
BASKET = [  # (ticker, layer)
    ("ALAB", "اتصال و قطعات"), ("CRDO", "اتصال و قطعات"), ("LITE", "اتصال و قطعات"), ("COHR", "اتصال و قطعات"),
    ("NVTS", "اتصال و قطعات"), ("ARM", "چیپ"),
    ("NBIS", "ابر و دیتاسنتر"), ("CRWV", "ابر و دیتاسنتر"), ("APLD", "ابر و دیتاسنتر"), ("IREN", "ابر و دیتاسنتر"),
    ("PLTR", "نرم‌افزار و کاربرد"), ("APP", "نرم‌افزار و کاربرد"), ("SOUN", "نرم‌افزار و کاربرد"),
    ("TEM", "نرم‌افزار و کاربرد"), ("RXRX", "نرم‌افزار و کاربرد"),
    ("IONQ", "کوانتوم (حاشیه‌ی AI)"), ("RGTI", "کوانتوم (حاشیه‌ی AI)"), ("QBTS", "کوانتوم (حاشیه‌ی AI)"),
    ("OKLO", "انرژی و روباتیک"), ("SERV", "انرژی و روباتیک"),
]
COLS = ["ticker", "layer", "entry_date", "entry_price", "sigma", "p10_15", "p10_30", "p_loss50"]


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def p_reach(sigma, annual_ret, mult, years=YEARS):
    """P(price at the end >= mult x start) for a lognormal walk with volatility sigma and mean yearly return annual_ret."""
    if sigma <= 0:
        return 0.0
    mu = math.log(1 + annual_ret) - 0.5 * sigma * sigma
    return 1 - ncdf((math.log(mult) - mu * years) / (sigma * math.sqrt(years)))


def p_loss(sigma, annual_ret, frac=0.5, years=YEARS):
    """P(price at the end <= frac x start)."""
    if sigma <= 0:
        return 0.0
    mu = math.log(1 + annual_ret) - 0.5 * sigma * sigma
    return ncdf((math.log(frac) - mu * years) / (sigma * math.sqrt(years)))


def clean(s):
    s = s.copy()
    ix = pd.to_datetime(s.index)
    s.index = (ix.tz_localize(None) if getattr(ix, "tz", None) is not None else ix).normalize()
    return s[~s.index.duplicated(keep="last")].astype(float).sort_index().dropna()


def f1(v, fmt="{:+.1f}"):
    return mt.f1(v, fmt)


def run(download_all, pre, force=False):
    """Returns (telegram_blocks, summary_lines, state_changed)."""
    today = dt.date.today()
    tickers = [t for t, _ in BASKET]
    data = download_all(tickers + ["QQQ", "VT"])
    px = {t: clean(data[t]) for t in tickers if t in data and len(data[t]) > 20}
    layer = dict(BASKET)
    if len(px) < 10:
        return [], [], False
    changed = False
    if os.path.exists(STATE):
        st = pd.read_csv(STATE, dtype={"ticker": str})
    else:
        rows = []
        for t, s in px.items():
            r = np.log(s).diff().dropna().iloc[-252:]
            sg = float(r.std() * math.sqrt(252)) if len(r) >= 100 else float("nan")
            rows.append({"ticker": t, "layer": layer[t], "entry_date": s.index[-1].date().isoformat(),
                         "entry_price": float(s.iloc[-1]), "sigma": sg,
                         "p10_15": p_reach(sg, 0.15, TARGET) if sg == sg else float("nan"),
                         "p10_30": p_reach(sg, 0.30, TARGET) if sg == sg else float("nan"),
                         "p_loss50": p_loss(sg, 0.15) if sg == sg else float("nan")})
        st = pd.DataFrame(rows, columns=COLS)
        st.to_csv(STATE, index=False)
        changed = True
    st = st[st["ticker"].isin(px)].reset_index(drop=True)
    st["now"] = [float(px[t].iloc[-1]) for t in st["ticker"]]
    st["prev"] = [float(px[t].iloc[-2]) if len(px[t]) > 1 else float("nan") for t in st["ticker"]]
    st["ret"] = (st["now"] / st["entry_price"] - 1) * 100
    st["day"] = (st["now"] / st["prev"] - 1) * 100
    n = len(st)
    port = float(st["ret"].mean())
    port_day = float(((st["now"] / st["entry_price"]).mean() / ((st["prev"] / st["entry_price"]).mean()) - 1) * 100)
    start = st["entry_date"].min()

    def bench(sym):
        s = clean(data[sym]) if sym in data else None
        if s is None or len(s) < 2:
            return None, None
        base = float(s.asof(pd.Timestamp(start)))
        return (float(s.iloc[-1]) / base - 1) * 100, (float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100

    qq, qq_d = bench("QQQ")
    vt, vt_d = bench("VT")
    t1 = [f"{'Portfolio':<14}{'Day%':>7}{'Since%':>9}", "-" * 30,
          f"{'AI basket (' + str(n) + ')':<14}{f1(port_day):>7}{f1(port):>9}",
          f"{'QQQ (Nasdaq)':<14}{f1(qq_d):>7}{f1(qq):>9}",
          f"{'VT (world)':<14}{f1(vt_d):>7}{f1(vt):>9}"]
    t2 = [f"{'Sym':<6}{'Entry':<6}{'Ret%':>7}{'Day%':>6}", "-" * 25]
    t3 = [f"{'Sym':<6}{'10x@15':>7}{'10x@30':>7}{'-50%':>6}", "-" * 26]
    for _, r in st.sort_values("ret", ascending=False).iterrows():
        t2.append(f"{r['ticker']:<6}{str(r['entry_date'])[5:]:<6}{f1(r['ret']):>7}{f1(r['day']):>6}")
        if r["p10_15"] == r["p10_15"]:
            t3.append(f"{r['ticker']:<6}{r['p10_15'] * 100:>6.1f}%{r['p10_30'] * 100:>6.1f}%{r['p_loss50'] * 100:>5.0f}%")
    ok = st["p10_15"].notna()
    any15 = 1 - float(np.prod(1 - st.loc[ok, "p10_15"]))
    any30 = 1 - float(np.prod(1 - st.loc[ok, "p10_30"]))
    avg_loss = float(st.loc[ok, "p_loss50"].mean())
    blocks = [
        f"🤖 <b>سبد هوش مصنوعی (۲۰ سهم)</b> — {today}\n"
        f"<i>سبد کاغذی با وزن مساوی از {start} (آخرین قیمت پایانی روز شروع)، بدون خرید و فروش بعدی. فهرست را من انتخاب کرده‌ام، نه یک آزمون. "
        "ستون P10x دو عدد دارد: احتمال ۱۰ برابر شدن قیمت در ۵ سال، اگر میانگین بازده سالانه ۱۵٪ باشد / اگر ۳۰٪ باشد (بسیار خوش‌بینانه). "
        "این عددها از یک مدل ساده با نوسان یک سال اخیر هر سهم می‌آیند و پیش‌بینی نیستند.</i>",
        f"📊 <b>بازده سبد</b> — از {start[5:]} ({(today - dt.date.fromisoformat(start)).days} روز)\n" + pre(t1),
        "📋 <b>سهم‌ها</b> (مرتب بر اساس بازده از شروع)\nEntry=تاریخ ورود · Ret%=بازده از ورود · Day%=امروز\n" + pre(t2),
        "🎲 <b>شانس ۱۰ برابر شدن در ۵ سال</b>\n10x@15=اگر بازده سالانه ۱۵٪ · 10x@30=اگر ۳۰٪ · -50%=احتمال افت بیش از نصف\n" + pre(t3),
    ]
    if changed or force or today.weekday() == 5:
        by = {}
        for _, r in st.iterrows():
            by.setdefault(r["layer"], []).append(r["ticker"])
        blocks.append("🧩 <b>لایه‌ها</b>\n" + "\n".join(f"{k}: " + "، ".join(v) for k, v in by.items()))
        blocks.append(
            "🎲 <b>این احتمال‌ها یعنی چه؟</b>\n"
            f"• هر سهم تنها حدود {st['p10_15'].min() * 100:.0f} تا {st['p10_15'].max() * 100:.0f}٪ شانس ۱۰ برابر شدن در ۵ سال دارد "
            f"(با فرض ۳۰٪ بازده سالانه: {st['p10_30'].min() * 100:.0f} تا {st['p10_30'].max() * 100:.0f}٪).\n"
            f"• شانس اینکه حداقل یکی از {int(ok.sum())} سهم ۱۰ برابر شود، اگر مستقل از هم بودند، حدود {any15 * 100:.0f}٪ تا {any30 * 100:.0f}٪ است؛ "
            "ولی این سهم‌ها هم‌جهت‌اند (همه به یک موضوع وابسته‌اند)، پس شانس واقعی کمتر است.\n"
            f"• در همین مدل، به‌طور میانگین حدود {avg_loss * 100:.0f}٪ احتمال دارد هر سهم بیش از نصف ارزشش را در ۵ سال از دست بدهد. "
            "سهم‌های ورشکسته و ریزش‌های ناگهانی در مدل نیستند، پس ریسک واقعی بیشتر است.")
    blocks.append("<i>این سبد آزمایشی است و توصیه‌ی خرید یا فروش نیست. چنین سبدهایی معمولاً یکی‌دوتا برنده‌ی بزرگ و چند سهم ضعیف دارند و ممکن است سال‌ها از بازار عقب بمانند.</i>")
    hl = [f"• سبد هوش مصنوعی از {start}: {f1(port)}٪ (QQQ {f1(qq)}٪)."]
    return blocks, hl, changed
