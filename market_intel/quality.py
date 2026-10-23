"""امتیاز کیفیت رشد (۰ تا ۵) برای هر سهم — مشترک بین همه‌ی گزارش‌ها.

۱. رشد پیوسته: فروش فصل آخر نسبت به همان فصل سال قبل ≥۱۰٪، و فروش در دست‌کم ۲ از ۳ فصل اخیر نسبت به فصل قبلش بالا رفته
   (اگر گزارش فصلی نبود، مثل بیشتر سهام ژاپن: رشد فصل آخر ≥۱۰٪ و رشد فروش سالانه در هر دو سال اخیر)
۲. پشتوانه‌ی نقدی سود: جریان نقد عملیاتی سال آخر مثبت و دست‌کم برابر سود خالص
۳. سودآوری: ROE ≥ ۱۵٪ یا سود ناخالص ÷ کل دارایی‌ها ≥ ۳۰٪
۴. مومنتوم نزدیک سقف: بازده ۱۲ ماه (بدون ماه آخر) دست‌کم ۱۰٪ بهتر از شاخص بازار و قیمت حداکثر ۱۵٪ زیر سقف ۵۲ هفته
۵. نظر تحلیلگران رو به بهبود: پیش‌بینی سود امسال بالاتر از ۳۰ روز پیش (یا اگر نبود: سود فصل آخر بالاتر از پیش‌بینی)
نشانه‌های کمکی (بدون امتیاز): افزایش تعداد سهم بیش از ۳٪ در سال (رقیق‌شدن) و PEG.
معیاری که داده‌اش در Yahoo نباشد «نامعلوم» است و امتیاز نمی‌گیرد.
نتیجه‌ها ۷ روز در data/quality/cache_<نام گزارش>.json نگه داشته می‌شوند تا هر روز دوباره دانلود نشوند.
"""
import datetime as dt
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
# هر گزارش فایل نهان خودش را دارد تا گزارش‌هایی که هم‌زمان اجرا می‌شوند هنگام ذخیره با هم تداخل نکنند
CACHE = os.path.join(ROOT, 'data', 'quality',
                     'cache_' + os.path.splitext(os.path.basename(sys.argv[0] or 'x'))[0] + '.json')
TTL_DAYS = 7
INDEX = {'us': 'SPY', 'jp': '1306.T', 'cn': '000300.SS', 'tw': '0050.TW', 'in': '^NSEI'}
NAMES_FA = {'growth': 'رشد پیوسته', 'cash': 'پشتوانه‌ی نقدی', 'profit': 'سودآوری', 'momentum': 'مومنتوم نزدیک سقف',
            'analysts': 'بهبود نظر تحلیلگران'}
_cache, _idx = None, {}


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
        cut = str(dt.date.today() - dt.timedelta(days=60))
        keep = {k: v for k, v in _cache.items() if v.get('date', '') >= cut}
        json.dump(keep, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)


def _row(df, names):
    if df is None or getattr(df, 'empty', True):
        return None
    for n in names:
        if n in df.index:
            s = df.loc[n].dropna()
            if len(s):
                return s.sort_index(ascending=False).astype(float)
    return None


def _mom(h):
    c = h['Close'].dropna()
    if len(c) < 230:
        return None
    a = c[c.index <= c.index[-1] - dt.timedelta(days=30)]
    b = c[c.index <= c.index[-1] - dt.timedelta(days=365)]
    return float(a.iloc[-1] / b.iloc[-1] - 1) if len(a) and len(b) else None


def _index_mom(market):
    import yfinance as yf
    if market not in _idx:
        try:
            _idx[market] = _mom(yf.Ticker(INDEX[market]).history(period='14mo', auto_adjust=True))
        except Exception:
            _idx[market] = None
    return _idx[market]


def score(sym, market='us'):
    c = _load()
    hit = c.get(sym)
    if hit and hit.get('date', '') >= str(dt.date.today() - dt.timedelta(days=TTL_DAYS)):
        return hit
    import yfinance as yf
    tk = yf.Ticker(sym)
    f = {k: None for k in NAMES_FA}
    badges = {}
    try:
        info = tk.get_info() or {}
    except Exception:
        info = {}
    try:
        q = tk.quarterly_income_stmt
        rev_q = _row(q, ['Total Revenue', 'Operating Revenue'])
        if rev_q is not None and len(rev_q) >= 4:
            ups = sum(1 for k in range(3) if rev_q.iloc[k] > rev_q.iloc[k + 1])
            yoy = rev_q.iloc[0] / rev_q.iloc[4] - 1 if len(rev_q) >= 5 and rev_q.iloc[4] > 0 else info.get('revenueGrowth')
            f['growth'] = bool(yoy is not None and yoy >= 0.10 and ups >= 2)
    except Exception:
        pass
    try:
        inc, cf, bs = tk.income_stmt, tk.cashflow, tk.balance_sheet
        if f['growth'] is None:
            # جایگزین وقتی گزارش فصلی در Yahoo نیست (بیشتر سهام ژاپن): رشد فروش فصل آخر نسبت به سال قبل ≥۱۰٪
            # و فروش سالانه در هر دو سال اخیر بالا رفته باشد
            rev_a = _row(inc, ['Total Revenue', 'Operating Revenue'])
            yoy = info.get('revenueGrowth')
            if yoy is not None and rev_a is not None and len(rev_a) >= 3:
                f['growth'] = bool(yoy >= 0.10 and rev_a.iloc[0] > rev_a.iloc[1] > rev_a.iloc[2])
        ni = _row(inc, ['Net Income', 'Net Income Common Stockholders'])
        ocf = _row(cf, ['Operating Cash Flow', 'Cash Flow From Continuing Operating Activities'])
        if ni is not None and ocf is not None:
            f['cash'] = bool(ocf.iloc[0] > 0 and ocf.iloc[0] >= ni.iloc[0])
        gp = _row(inc, ['Gross Profit'])
        ta = _row(bs, ['Total Assets'])
        roe = info.get('returnOnEquity')
        gpa = float(gp.iloc[0] / ta.iloc[0]) if gp is not None and ta is not None and ta.iloc[0] > 0 else None
        if roe is not None or gpa is not None:
            f['profit'] = bool((roe is not None and roe >= 0.15) or (gpa is not None and gpa >= 0.30))
        sh = _row(bs, ['Ordinary Shares Number', 'Share Issued'])
        if sh is not None and len(sh) >= 2 and sh.iloc[1] > 0:
            badges['dilution_pct'] = round(float(sh.iloc[0] / sh.iloc[1] - 1) * 100, 1)
    except Exception:
        pass
    try:
        h = tk.history(period='14mo', auto_adjust=True)
        m, im = _mom(h), _index_mom(market)
        if m is not None and len(h):
            hi = float(h['High'].tail(252).max())
            near = float(h['Close'].iloc[-1]) / hi - 1 >= -0.15
            f['momentum'] = bool(near and m - (im or 0) >= 0.10)
    except Exception:
        pass
    try:
        et = tk.eps_trend
        if et is not None and not et.empty and '0y' in et.index and {'current', '30daysAgo'} <= set(et.columns):
            cur, ago = et.loc['0y', 'current'], et.loc['0y', '30daysAgo']
            if cur == cur and ago == ago:
                f['analysts'] = bool(cur > ago)
        if f['analysts'] is None:
            eh = tk.earnings_history
            if eh is not None and not eh.empty and {'epsActual', 'epsEstimate'} <= set(eh.columns):
                last = eh.dropna(subset=['epsActual', 'epsEstimate']).sort_index().iloc[-1]
                f['analysts'] = bool(last.epsActual > last.epsEstimate)
    except Exception:
        pass
    peg = info.get('trailingPegRatio') or info.get('pegRatio')
    if peg is not None and not (isinstance(peg, float) and math.isnan(peg)):
        badges['peg'] = round(float(peg), 2)
    res = {'date': str(dt.date.today()), 'score': sum(1 for v in f.values() if v),
           'known': sum(1 for v in f.values() if v is not None), 'flags': f, 'badges': badges}
    c[sym] = res
    return res


def label(res):
    """متن کوتاه برای گزارش: ⭐۴/۵ و هشدار رقیق‌شدن."""
    if not res:
        return ''
    t = f"⭐{res['score']}/۵".translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
    if res['known'] < 5:
        t += f" ({5 - res['known']} نامعلوم)".translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
    if (res.get('badges') or {}).get('dilution_pct', 0) > 3:
        t += ' ⚠️رقیق‌شدن'
    return t


def annotate(rows, market, sym_of=lambda r: r['ticker'], limit=30):
    """امتیاز کیفیت را به rows اضافه می‌کند (فقط limit ردیف اول، برای سرعت)."""
    for r in rows[:limit]:
        try:
            q = score(sym_of(r), market)
            r['qs'] = q['score']
            r['qs_known'] = q['known']
            r['qs_label'] = label(q)
            r['qs_flags'] = q['flags']
        except Exception:
            r['qs'], r['qs_label'] = None, ''
    save()
    return rows


def best_line(rows, n=5):
    top = sorted([r for r in rows if r.get('qs') is not None and r['qs'] >= 4], key=lambda r: -r['qs'])[:n]
    if not top:
        return '⭐ امروز سهمی با امتیاز کیفیت ۴ یا ۵ از ۵ در این فهرست نبود.'
    d = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return '⭐ <b>بهترین از نظر کیفیت رشد:</b> ' + '، '.join(f"{r['ticker']} ({str(r['qs']).translate(d)}/۵)" for r in top)


LEGEND = ('<i>⭐ امتیاز کیفیت از ۵: رشد پیوسته، پشتوانه‌ی نقدی سود، سودآوری، مومنتوم نزدیک سقف، بهبود نظر تحلیلگران</i>')
