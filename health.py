"""Data-health checks: how much of the market data arrived, how fresh it is, whether the AI helper worked."""
import datetime as dt

NAMES = {"US": "آمریکا", "JP": "ژاپن", "IN": "هند", "TW": "تایوان", "CN": "چین", "CM": "فلزات و انرژی", "FX": "جفت‌ارز"}


def coverage_warnings(uni, df, today=None):
    """Plain-Persian warning lines (no bullets) when today's price data is incomplete or stale."""
    today = today or dt.date.today()
    total_u = sum(len(v) for v in uni.values())
    used = len(df)
    pct = used / total_u * 100 if total_u else 100
    out = []
    if pct < 85:
        out.append(f"فقط {pct:.0f}٪ از نمادها امروز داده داشتند ({used:,} از {total_u:,}). منبع داده (Yahoo) احتمالاً "
                   "دچار اختلال بوده و فهرست‌های امروز ممکن است ناقص باشند.")
    else:
        for m, tickers in uni.items():
            n = len(tickers)
            got = int((df["market"] == m).sum())
            if n >= 5 and got / n < 0.85:
                out.append(f"بازار {NAMES.get(m, m)}: فقط {got / n * 100:.0f}٪ نمادها داده داشتند؛ نتیجه‌های این بازار ناقص است.")
    for m in uni:
        sub = df[df["market"] == m]
        if len(sub):
            try:
                newest = max(dt.date.fromisoformat(str(x)) for x in sub["last_date"])
            except Exception:
                continue
            if (today - newest).days > 5:
                out.append(f"بازار {NAMES.get(m, m)}: آخرین قیمت دریافت‌شده مربوط به {newest} است "
                           "(بازار تعطیل بوده یا منبع داده مشکل دارد).")
    return out


def ai_warning():
    """Warning when the Gemini helper (translation / writing) was missing or failed today."""
    try:
        import ai
    except Exception:
        return []
    if not ai.available():
        return ["کلید Gemini تنظیم نشده؛ ترجمه و تحلیل نوشتاری با روش ساده ساخته شد."]
    st = getattr(ai, "STATS", {})
    if st.get("fail", 0) > 0 and st.get("ok", 0) == 0:
        return ["Gemini امروز جواب نداد؛ ترجمه و تحلیل نوشتاری با روش ساده ساخته شد."]
    if st.get("fail", 0) > 0:
        return [f"Gemini در {st['fail']} درخواست جواب نداد؛ بخشی از ترجمه‌ها ممکن است ساده‌تر باشد."]
    return []
