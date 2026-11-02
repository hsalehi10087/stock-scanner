"""ارزش ذاتی تقریبی هر سهم و نسبت قیمت به ارزش ذاتی (P/IV) — مشترک بین گزارش‌ها.

روش (DCF ساده‌ی دو مرحله‌ای روی هر سهم):
  • پایه: جریان نقد آزاد هر سهم (FCF ÷ تعداد سهم). اگر منفی یا نامعلوم بود: سود پیش‌بینی‌شده‌ی هر سهم (forward EPS).
  • رشد ۵ سال اول: میانگین رشد سود و رشد فروش اخیر (Yahoo)، محدود به ۰ تا ۲۵٪.
  • سال‌های ۶ تا ۱۰: رشد به‌تدریج تا ۳٪ پایین می‌آید؛ بعد از آن رشد دائمی ۳٪.
  • نرخ تنزیل ۱۰٪ (بازده موردانتظار سهام).
  • نقد خالص (نقد منهای بدهی) هر سهم اضافه می‌شود.
P/IV < ۰٫۸ ارزان، ۰٫۸ تا ۱٫۲ حدود ارزش، > ۱٫۲ گران. اگر پایه‌ی مثبتی نبود یا ارز گزارش مالی با ارز قیمت فرق داشت: نامعلوم.
تخمین است، نه ارزش‌گذاری کامل. نتیجه ۷ روز در data/quality/iv_cache.json نگه داشته می‌شود.
"""
import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'data', 'quality', 'iv_cache.json')
TTL_DAYS = 7
R, G_TERM, G_MAX = 0.10, 0.03, 0.25
_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(CACHE, encoding='utf-8'))
        except Exception:
            _cache = {}
    return _cache


def save():
    if _cache is not None:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        cut = str(dt.date.today() - dt.timedelta(days=30))
        json.dump({k: v for k, v in list(_cache.items()) if v.get('date', '') >= cut},
                  open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)


def dcf(base, g1):
    """ارزش فعلی جریان‌های ۱۰ ساله + ارزش پایانی، برای پایه‌ی یک واحدی `base`."""
    v, cf, g = 0.0, base, g1
    for y in range(1, 11):
        if y > 5:
            g = g1 + (G_TERM - g1) * (y - 5) / 5
        cf *= 1 + g
        v += cf / (1 + R) ** y
    return v + cf * (1 + G_TERM) / (R - G_TERM) / (1 + R) ** 10


def from_info(info, price=None):
    """محاسبه از دیکشنری info یاهو. خروجی dict یا None."""
    price = price or info.get('currentPrice') or info.get('regularMarketPrice')
    sh = info.get('sharesOutstanding') or info.get('impliedSharesOutstanding')
    if not price or not sh:
        return None
    fc, pc = info.get('financialCurrency'), info.get('currency')
    if fc and pc and fc != pc:
        return None
    fcf = info.get('freeCashflow')
    base, src = None, None
    if fcf and fcf > 0:
        base, src = fcf / sh, 'FCF'
    elif (info.get('forwardEps') or 0) > 0:
        base, src = info['forwardEps'], 'EPS'
    if not base:
        return None
    gs = [x for x in (info.get('earningsGrowth'), info.get('revenueGrowth')) if isinstance(x, (int, float))]
    g1 = min(max(sum(gs) / len(gs) if gs else 0.05, 0.0), G_MAX)
    net_cash = ((info.get('totalCash') or 0) - (info.get('totalDebt') or 0)) / sh
    iv = dcf(base, g1) + net_cash
    if iv <= 0:
        return None
    return {'iv': round(iv, 2), 'ratio': round(price / iv, 2), 'base': src, 'g1': round(g1, 3),
            'date': str(dt.date.today())}


def value(sym, price=None):
    c = _load()
    hit = c.get(sym)
    if hit and hit.get('date', '') >= str(dt.date.today() - dt.timedelta(days=TTL_DAYS)):
        res = dict(hit)
    else:
        import yfinance as yf
        try:
            info = yf.Ticker(sym).get_info() or {}
        except Exception:
            return None
        if not info:
            return None
        res = from_info(info) or {'iv': None, 'date': str(dt.date.today())}
        c[sym] = res
    if res.get('iv') and price:                      # نسبت با قیمت لحظه‌ای
        res['ratio'] = round(price / res['iv'], 2)
    return res if res.get('iv') else None


def label(res):
    """متن بولد HTML برای تلگرام."""
    d = str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫')
    if not res:
        return '<b>قیمت/ارزش ذاتی: نامعلوم</b>'
    r = res['ratio']
    tag = 'ارزان' if r < 0.8 else ('حدود ارزش' if r <= 1.2 else 'گران')
    return f"<b>قیمت/ارزش ذاتی: {f'{r:.2f}'.translate(d)} ({tag})</b>"


LEGEND = ('<i>قیمت/ارزش ذاتی = قیمت ÷ ارزش تخمینی با DCF ساده (جریان نقد آزاد یا سود پیش‌بینی‌شده، رشد اخیر تا سقف ۲۵٪، '
          'تنزیل ۱۰٪). زیر ۰٫۸ ارزان، ۰٫۸ تا ۱٫۲ حدود ارزش، بالای ۱٫۲ گران. تخمین است، نه ارزش‌گذاری کامل.</i>')
