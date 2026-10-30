"""شناسایی الگوهای نموداری میان‌مدت/بلندمدت از روی سری قیمت پایانی (روزانه ← هفتگی).

از scipy.signal.find_peaks برای قله/دره و از pandas-ta-classic برای میانگین‌ها و RSI استفاده می‌کند.
خروجی: dict با فهرست الگوها (bullish/bearish) و یک امتیاز تکنیکال بلندمدت بین -3 تا +3.
هشدار: اعتبار آماری الگوهای نموداری باید روی تاریخچه بک‌تست شود؛ این ماژول «برچسب» می‌دهد، «پیش‌بینی» نمی‌کند.
"""
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

TOL = 0.04          # دو قله/دره «هم‌سطح» اگر اختلافشان کمتر از ۴٪ باشد
MIN_DEPTH = 0.08    # عمق حداقلی الگو (۸٪)


def weekly(close: pd.Series) -> pd.Series:
    c = close.dropna()
    if not isinstance(c.index, pd.DatetimeIndex):
        return c
    return c.resample('W').last().dropna()


def pivots(w: pd.Series, prominence=0.06):
    """قله‌ها و دره‌های اصلی؛ prominence نسبی به قیمت."""
    v = w.values.astype(float)
    if len(v) < 20:
        return [], []
    p = prominence * np.nanmedian(v)
    hi, _ = find_peaks(v, prominence=p)
    lo, _ = find_peaks(-v, prominence=p)
    return list(hi), list(lo)


def _near(a, b, tol=TOL):
    return abs(a - b) / max(a, b) <= tol


def detect(close: pd.Series) -> dict:
    """close: قیمت پایانی تعدیل‌شده (حداقل ~۶۰ هفته). برمی‌گرداند {'patterns': [...], 'score': x, 'trend': ...}."""
    w = weekly(close)
    out = {'patterns': [], 'score': 0.0, 'trend': 'unknown', 'weeks': int(len(w))}
    if len(w) < 60:
        return out
    v = w.values.astype(float)
    last = v[-1]
    hi, lo = pivots(w)
    score = 0.0

    # --- روند بلندمدت: قیمت نسبت به میانگین ۴۰ هفته‌ای و شیب آن
    ma = w.rolling(40).mean()
    slope = (ma.iloc[-1] / ma.iloc[-9] - 1) if ma.notna().iloc[-9:].all() else 0.0
    if last > ma.iloc[-1] and slope > 0.01:
        out['trend'] = 'up'; score += 1
    elif last < ma.iloc[-1] and slope < -0.01:
        out['trend'] = 'down'; score -= 1
    else:
        out['trend'] = 'range'

    def add(name, kind, pts):
        out['patterns'].append({'name': name, 'kind': kind})
        return pts

    # --- کف دوقلو: دو دره هم‌سطح با یک قله میانی ≥۸٪ بالاتر، و شکست قله میانی
    if len(lo) >= 2:
        a, b = lo[-2], lo[-1]
        mid = [h for h in hi if a < h < b]
        if mid and _near(v[a], v[b]) and 8 <= b - a <= 80 and last >= min(v[a], v[b]) * 0.97:
            neck = v[mid].max()
            if neck / max(v[a], v[b]) - 1 >= MIN_DEPTH and len(v) - b <= 26:
                broke = last > neck
                score += add('کف دوقلو' + (' (شکست خط گردن)' if broke else ' (در انتظار شکست)'), 'bullish', 1.5 if broke else 0.5)
    # --- سقف دوقلو
    if len(hi) >= 2:
        a, b = hi[-2], hi[-1]
        mid = [l for l in lo if a < l < b]
        if mid and _near(v[a], v[b]) and 8 <= b - a <= 80 and last <= max(v[a], v[b]) * 1.03:
            neck = v[mid].min()
            if 1 - neck / min(v[a], v[b]) >= MIN_DEPTH and len(v) - b <= 26:
                broke = last < neck
                score += add('سقف دوقلو' + (' (شکست حمایت)' if broke else ' (هشدار)'), 'bearish', -1.5 if broke else -0.5)
    # --- سرووشانه (و معکوس)
    if len(hi) >= 3:
        l, h, r = hi[-3], hi[-2], hi[-1]
        if v[h] > v[l] * 1.05 and v[h] > v[r] * 1.05 and _near(v[l], v[r], 0.08) and len(v) - r <= 26:
            troughs = [x for x in lo if l < x < r]
            if troughs:
                neck = v[troughs].min()
                score += add('سرووشانه' + (' (شکست)' if last < neck else ''), 'bearish', -2 if last < neck else -1)
    if len(lo) >= 3:
        l, h, r = lo[-3], lo[-2], lo[-1]
        if v[h] < v[l] * 0.95 and v[h] < v[r] * 0.95 and _near(v[l], v[r], 0.08) and len(v) - r <= 26:
            peaks = [x for x in hi if l < x < r]
            if peaks:
                neck = v[peaks].max()
                score += add('سرووشانه معکوس' + (' (شکست)' if last > neck else ''), 'bullish', 2 if last > neck else 1)
    # --- فنجان و دسته: لبه چپ = سقف ۲ سال اخیر، افت ۱۵–۵۰٪، بازگشت U شکل نزدیک سقف، دسته کم‌عمق
    if len(v) >= 60:
        lo_i = max(0, len(v) - 110)
        i = lo_i + int(np.argmax(v[lo_i:len(v) - 8]))
        seg = v[i:]
        if 26 <= len(seg) <= 110:
            depth = 1 - seg.min() / v[i]
            bpos = int(np.argmin(seg)) / len(seg)
            handle = 1 - last / v[-12:].max()
            if 0.15 <= depth <= 0.5 and 0.25 <= bpos <= 0.75 and last >= v[i] * 0.92 and handle <= 0.15:
                score += add('فنجان‌ودسته' + (' (شکست سقف)' if last > v[i] else ' (نزدیک سقف)'), 'bullish', 1.5 if last > v[i] else 1)
    # --- مثلث صعودی: سقف‌های هم‌سطح + کف‌های بالارونده، و نزدیک بالای مثلث
    if len(hi) >= 2 and len(lo) >= 2:
        h1, h2 = hi[-2], hi[-1]
        l1, l2 = lo[-2], lo[-1]
        if _near(v[h1], v[h2], 0.03) and v[l2] > v[l1] * 1.03 and len(v) - max(h2, l2) <= 12 and last >= max(v[h1], v[h2]) * 0.95:
            score += add('مثلث صعودی', 'bullish', 1)
    # --- شکست سقف ۵۲ هفته‌ای / ۱۰۴ هفته‌ای
    if len(v) > 105 and last >= v[-105:-1].max():
        score += add('شکست سقف ۲ ساله', 'bullish', 1)
    elif len(v) > 53 and last >= v[-53:-1].max():
        score += add('شکست سقف ۵۲ هفته', 'bullish', 0.7)
    # --- نزدیکی به کف ۵۲ هفته‌ای + روند نزولی
    if len(v) > 53 and last <= v[-53:].min() * 1.03:
        score += add('نزدیک کف ۵۲ هفته', 'bearish', -1)

    out['score'] = float(np.clip(score, -3, 3))
    return out


def label(res: dict) -> str:
    if not res['patterns']:
        return {'up': 'روند صعودی', 'down': 'روند نزولی', 'range': 'خنثی'}.get(res['trend'], '-')
    return '، '.join(p['name'] for p in res['patterns'][:3])
