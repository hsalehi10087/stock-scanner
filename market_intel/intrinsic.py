"""ارزش ذاتی تقریبی هر سهم و نسبت قیمت به ارزش ذاتی (P/IV) — مشترک بین گزارش‌ها.

روش (DCF ساده‌ی دو مرحله‌ای روی هر سهم):
  • پایه: جریان نقد آزاد هر سهم (FCF ÷ تعداد سهم). اگر منفی یا نامعلوم بود: سود پیش‌بینی‌شده‌ی هر سهم (forward EPS).
  • رشد ۵ سال اول: میانگین رشد سود و رشد فروش اخیر (Yahoo)، محدود به ۰ تا ۲۵٪.
  • سال‌های ۶ تا ۱۰: رشد به‌تدریج تا ۳٪ پایین می‌آید؛ بعد از آن رشد دائمی ۳٪.
  • نرخ تنزیل ۱۰٪ (بازده موردانتظار سهام).
  • نقد خالص (نقد منهای بدهی) هر سهم اضافه می‌شود.
P/IV < ۰٫۸ ارزان، ۰٫۸ تا ۱٫۲ حدود ارزش، > ۱٫۲ گران.
پشتیبان‌ها وقتی عدد Yahoo نیست: صورت جریان نقد سالانه‌ی Yahoo، سود گذشته، عددهای رسمی SEC (ابزار trader-analyst)،
و تبدیل ارز وقتی ارز گزارش مالی با ارز قیمت فرق دارد. اگر شرکت زیان‌ده است، دلیل و نسبت قیمت به فروش نشان داده می‌شود.
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


def _fx(fc, pc):
    """نرخ تبدیل ارز گزارش مالی به ارز قیمت (مثلاً TWD→USD برای ADR)."""
    if not fc or not pc or fc == pc:
        return 1.0
    import yfinance as yf
    for sym, inv in ((f'{fc}{pc}=X', False), (f'{pc}{fc}=X', True)):
        try:
            h = yf.Ticker(sym).history(period='5d')
            if len(h):
                r = float(h['Close'].iloc[-1])
                return 1 / r if inv else r
        except Exception:
            pass
    return None


def _stmt_fcf(sym):
    """جریان نقد آزاد سالانه از صورت جریان نقد Yahoo (وقتی info آن را ندارد؛ برای سهام غیرآمریکایی مفید)."""
    try:
        import yfinance as yf
        cf = yf.Ticker(sym).cashflow
        if cf is None or cf.empty:
            return None
        if 'Free Cash Flow' in cf.index:
            v = cf.loc['Free Cash Flow'].dropna()
        elif 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index:
            v = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']).dropna()
        else:
            return None
        return float(v.iloc[0]) if len(v) else None
    except Exception:
        return None


def from_info(info, price=None, sym=None, sec=None, fx=None, stmt_fcf=None):
    """محاسبه از info یاهو، با پشتیبان: صورت جریان نقد Yahoo، سود گذشته، و عددهای رسمی SEC.
    خروجی dict؛ اگر ارزش‌گذاری DCF ممکن نبود، iv=None با دلیل (reason) و در صورت امکان P/S."""
    price = price or info.get('currentPrice') or info.get('regularMarketPrice')
    sh = info.get('sharesOutstanding') or info.get('impliedSharesOutstanding')
    today = str(dt.date.today())
    if not price or not sh:
        return {'iv': None, 'reason': 'nodata', 'date': today}
    k = fx if fx is not None else _fx(info.get('financialCurrency'), info.get('currency'))
    if k is None:
        return {'iv': None, 'reason': 'fx', 'date': today}
    fcf = info.get('freeCashflow')
    if not fcf and sym:
        fcf = stmt_fcf if stmt_fcf is not None else _stmt_fcf(sym)
    base, src = None, None
    if fcf and fcf > 0:
        base, src = fcf * k / sh, 'FCF'
    elif (info.get('forwardEps') or 0) > 0:
        base, src = info['forwardEps'], 'EPS'          # forwardEps یاهو به ارز قیمت است
    elif (info.get('trailingEps') or 0) > 0:
        base, src = info['trailingEps'], 'EPS گذشته'
    elif sec and ((sec.get('eps_ttm') or 0) > 0 or (sec.get('net_income_ttm') or 0) > 0):
        base = sec.get('eps_ttm') if (sec.get('eps_ttm') or 0) > 0 else sec['net_income_ttm'] / sh
        src = 'SEC'
    rev = info.get('totalRevenue') or (sec or {}).get('revenue_ttm')
    ps = round(price * sh / (rev * k), 1) if rev and rev > 0 else None
    if not base:
        return {'iv': None, 'reason': 'loss', 'ps': ps, 'date': today}
    gs = [x for x in (info.get('earningsGrowth'), info.get('revenueGrowth')) if isinstance(x, (int, float))]
    if not gs and sec:
        gs = [x / 100 for x in (sec.get('net_income_yoy'), sec.get('revenue_yoy')) if isinstance(x, (int, float))]
    g1 = min(max(sum(gs) / len(gs) if gs else 0.05, 0.0), G_MAX)
    net_cash = ((info.get('totalCash') or 0) - (info.get('totalDebt') or 0)) * k / sh
    iv = dcf(base, g1) + net_cash
    if iv <= 0:
        return {'iv': None, 'reason': 'debt', 'ps': ps, 'date': today}
    return {'iv': round(iv, 2), 'ratio': round(price / iv, 2), 'base': src, 'g1': round(g1, 3), 'ps': ps,
            'date': today}


def value(sym, price=None):
    """ارزش ذاتی؛ اگر DCF ممکن نیست dict با iv=None و reason برمی‌گردد (برای نمایش دلیل به‌جای خالی)."""
    c = _load()
    hit = c.get(sym)
    fresh = hit and hit.get('date', '') >= str(dt.date.today() - dt.timedelta(days=TTL_DAYS))
    if fresh and (hit.get('iv') or hit.get('reason')):      # خانه‌های خالی نسخه‌ی قبلی دوباره حساب می‌شوند
        res = dict(hit)
    else:
        import yfinance as yf
        info = {}
        for _ in range(2):
            try:
                info = yf.Ticker(sym).get_info() or {}
            except Exception:
                info = {}
            if info.get('sharesOutstanding') or info.get('impliedSharesOutstanding'):
                break
        sec = None
        if '.' not in sym or sym.endswith(('.A', '.B')):
            try:
                import sec_check as SC
                sec = SC.check(sym)
            except Exception:
                sec = None
        res = from_info(info, sym=sym, sec=sec) if info else {'iv': None, 'reason': 'nodata',
                                                                'date': str(dt.date.today())}
        if res.get('reason') != 'nodata':
            c[sym] = res
    if res.get('iv') and price:                      # نسبت با قیمت لحظه‌ای
        res['ratio'] = round(price / res['iv'], 2)
    return res


def label(res):
    """متن بولد HTML برای تلگرام."""
    d = str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫')
    if not res or not res.get('iv'):
        why = {'loss': 'زیان‌ده یا جریان نقد منفی؛ DCF معنا ندارد', 'debt': 'بدهی بیشتر از ارزش جریان نقد',
               'fx': 'نرخ ارز پیدا نشد', 'nodata': 'داده در دسترس نبود'}.get((res or {}).get('reason'), 'نامعلوم')
        ps = (res or {}).get('ps')
        return f"<b>قیمت/ارزش ذاتی: {why}</b>" + (f" | قیمت به فروش {f'{ps:.1f}'.translate(d)}" if ps else '')
    r = res['ratio']
    tag = 'ارزان' if r < 0.8 else ('حدود ارزش' if r <= 1.2 else 'گران')
    return f"<b>قیمت/ارزش ذاتی: {f'{r:.2f}'.translate(d)} ({tag})</b>"


LEGEND = ('<i>قیمت/ارزش ذاتی = قیمت ÷ ارزش تخمینی با DCF ساده (جریان نقد آزاد یا سود پیش‌بینی‌شده، رشد اخیر تا سقف ۲۵٪، '
          'تنزیل ۱۰٪). زیر ۰٫۸ ارزان، ۰٫۸ تا ۱٫۲ حدود ارزش، بالای ۱٫۲ گران. تخمین است، نه ارزش‌گذاری کامل.</i>')
