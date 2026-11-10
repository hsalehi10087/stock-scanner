"""بررسی عددهای رسمی سهام آمریکا از گزارش‌های SEC (XBRL)، با ابزار trader-analyst (sec_facts.py).

برای هر نماد آمریکایی: فروش و سود خالص هر فصل همان‌طور که شرکت به SEC گزارش داده، رشد هر فصل نسبت به همان فصل
سال قبل، تعداد فصل‌های پیاپی رشد سود، حاشیه‌ها، و نشانه‌ی «سود از اقلام غیرعملیاتی» (سود خالص بیشتر از سود عملیاتی).
نتیجه ۷ روز در data/quality/sec_cache.json نگه داشته می‌شود. داده‌ی Yahoo فقط وقتی SEC چیزی نداشت به کار می‌رود.
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sec_facts as F  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'data', 'quality', 'sec_cache.json')
TTL_DAYS = 7
# SEC می‌خواهد هر برنامه نام و راه تماس بدهد؛ آدرس عمومی GitHub صاحب مخزن (نه ایمیل شخصی)
UA = os.getenv('SEC_USER_AGENT') or 'Hossein Stock Scanner hsalehi10087@users.noreply.github.com'
_cache, _fetcher, _ciks = None, None, None


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
        json.dump({k: v for k, v in _cache.items() if v.get('date', '') >= cut}, open(CACHE, 'w', encoding='utf-8'),
                  ensure_ascii=False)


def summarize(result):
    """خروجی analyse() → خلاصه‌ی لازم برای فیلتر و گزارش."""
    rows = result['rows']
    if not rows:
        return None
    cur = rows[0]
    streak = 0
    for r in rows:                                   # فصل‌های پیاپی (از تازه‌ترین) با رشد سود نسبت به سال قبل
        g = r.get('net_income_yoy')
        if g is not None and g > 0 and (r.get('net_income') or 0) > 0:
            streak += 1
        else:
            break
    rev_streak = 0
    for r in rows:
        g = r.get('revenue_yoy')
        if g is not None and g > 0:
            rev_streak += 1
        else:
            break
    oi, ni = cur.get('operating_income'), cur.get('net_income')
    one_off = bool(oi is not None and ni is not None and ni > 0 and ni > oi * 1.1 and oi > 0)
    prev = rows[1] if len(rows) > 1 else {}
    gm, pgm = cur.get('operating_margin'), prev.get('operating_margin')
    stale = (dt.date.today() - dt.date.fromisoformat(cur['end'])).days > 150   # گزارش تازه هنوز در داده‌ی SEC نیامده
    return {'date': str(dt.date.today()), 'period_end': cur['end'], 'stale': stale, 'derived': bool(cur.get('derived')),
            'revenue_yoy': cur.get('revenue_yoy'), 'net_income_yoy': cur.get('net_income_yoy'),
            'eps_yoy': cur.get('eps_yoy'), 'profit_streak_yoy': streak, 'revenue_streak_yoy': rev_streak,
            'operating_margin': gm, 'margin_up': bool(gm is not None and pgm is not None and gm > pgm),
            'net_margin': cur.get('net_margin'), 'one_off': one_off,
            'revenue_ttm': result['ttm'].get('revenue'), 'net_income_ttm': result['ttm'].get('net_income')}


def check(ticker):
    """None اگر سهم آمریکایی نیست یا SEC داده ندارد."""
    global _fetcher, _ciks
    if '.' in ticker and not ticker.endswith(('.A', '.B')):
        return None
    c = _load()
    hit = c.get(ticker)
    if hit and hit.get('date', '') >= str(dt.date.today() - dt.timedelta(days=TTL_DAYS)):
        return hit if hit.get('period_end') else None
    try:
        if _fetcher is None:
            _fetcher = F.Fetcher(ua=UA, offline=os.getenv('SEC_OFFLINE_DIR'))
            _ciks = F.ticker_ciks(_fetcher)
        cik = _ciks.get(ticker.upper().replace('-', '.'))
        if not cik:
            c[ticker] = {'date': str(dt.date.today())}
            return None
        res = F.analyse(_fetcher.json(F.FACTS_URL % cik[0], f'companyfacts-CIK{cik[0]}.json'), quarters=8)
        out = summarize(res)
    except Exception as e:
        print('SEC', ticker, e, file=sys.stderr)
        return None
    c[ticker] = out or {'date': str(dt.date.today())}
    return out


def fa(x):
    return str(x).translate(str.maketrans('0123456789.-', '۰۱۲۳۴۵۶۷۸۹٫−'))


def label(s):
    """یک خط فارسی برای گزارش."""
    if not s:
        return ''
    def p(v):
        return '—' if v is None else fa(f'{v:+.0f}') + '٪'
    t = (f"📑 گزارش رسمی SEC (فصل منتهی به {fa(s['period_end'].replace('-', '/'))}): فروش {p(s['revenue_yoy'])}، "
         f"سود خالص {p(s['net_income_yoy'])} نسبت به سال قبل")
    if s['profit_streak_yoy'] >= 2:
        t += f" | {fa(s['profit_streak_yoy'])} فصل پیاپی رشد سود"
    if s['one_off']:
        t += ' | ⚠️ سود خالص بیشتر از سود عملیاتی (اقلام غیرعملیاتی)'
    if s['derived']:
        t += ' (فصل چهارم محاسبه‌شده از گزارش سالانه)'
    return t
