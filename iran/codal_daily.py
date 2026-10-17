#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گزارش روزانه‌ی کدال: صورت‌های مالی تازه ← رشد فروش و سود خالص ← جدول سهم‌های با رشد سود > ۴۰٪

باید روی کامپیوتری اجرا شود که به کدال دسترسی دارد (IP ایران). از سرورهای GitHub (آمریکا) مسدود است.
هیچ عددی ساخته نمی‌شود: هر چه خوانده نشود، «—» نمایش داده می‌شود و دلیلش در لاگ می‌آید.

اجرا:   python iran/codal_daily.py            (گزارش امروز؛ ارسال به تلگرام اگر توکن تنظیم باشد)
        python iran/codal_daily.py --date 1405/07/25 --min-growth 40 --no-send
متغیرهای محیطی (یا فایل .env کنار اسکریپت): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    sys.exit('pip install requests beautifulsoup4 lxml')

SEARCH = 'https://search.codal.ir/api/search/v2/q'
HEAD = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
BASE_PARAMS = {
    'Length': -1, 'search': 'true', 'Audited': 'true', 'AuditorRef': -1, 'Category': 1, 'Childs': 'true',
    'CompanyState': -1, 'CompanyType': -1, 'Consolidatable': 'true', 'IsNotAudited': 'false', 'Mains': 'true',
    'NotAudited': 'true', 'NotConsolidatable': 'true', 'PublisherType': 1, 'LetterType': 6, 'TracingNo': -1,
    'Publisher': 'false', 'Isic': -1,
}
FA = '۰۱۲۳۴۵۶۷۸۹'


# ---------- ابزار تاریخ و متن ----------
def to_jalali(g):
    gy, gm, gd = g.year, g.month, g.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return f'{jy}/{jm:02d}/{jd:02d}'


def norm(s):
    s = '' if s is None else str(s)
    s = s.replace('ي', 'ی').replace('ك', 'ک').replace('‌', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def ns(s):
    return norm(s).replace(' ', '')


def to_en_digits(s):
    return ''.join(str(FA.index(c)) if c in FA else c for c in s)


def num(s):
    if s is None:
        return None
    x = to_en_digits(norm(s)).replace(',', '').replace('٬', '').replace(' ', '')
    if x in ('', '-', '--'):
        return None
    neg = False
    if x.startswith('(') and x.endswith(')'):
        neg, x = True, x[1:-1]
    if x.startswith('-'):
        neg, x = True, x[1:]
    if not re.fullmatch(r'\d+(\.\d+)?', x):
        return None
    v = float(x)
    return -v if neg else v


def growth(cur, prev):
    """رشد درصدی؛ اگر دوره‌ی قبل صفر یا منفی بود، عددی ساخته نمی‌شود."""
    if cur is None or prev is None or prev <= 0:
        return None
    return round((cur / prev - 1) * 100, 1)


# ---------- دریافت فهرست گزارش‌ها ----------
def fetch_letters(day_fa, max_pages=60):
    out = []
    for p in range(1, max_pages + 1):
        for attempt in range(3):
            r = requests.get(SEARCH, params={**BASE_PARAMS, 'PageNumber': p}, headers=HEAD, timeout=(20, 60))
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        letters = r.json().get('Letters', [])
        if not letters:
            break
        out += [l for l in letters if str(l.get('PublishDateTime', '')).startswith(to_fa_date(day_fa))]
        last = str(letters[-1].get('PublishDateTime', ''))
        if not last.startswith(to_fa_date(day_fa)):
            break
    return out


def to_fa_date(s):
    return ''.join(FA[int(c)] if c.isdigit() else c for c in s)


def is_subsidiary(title):
    """گزارش شرکت تابعه: عنوان با «(شرکت ...)» تمام می‌شود."""
    return bool(re.search(r'\(\s*شرکت[^)]*\)\s*$', norm(title)))


def is_correction(title):
    return 'اصلاحیه' in norm(title)


def period_of(title):
    m = re.search(r'(\d+) ماهه منتهی به (\S+)', to_en_digits(norm(title)).replace('۰', '0'))
    t = norm(title)
    m = re.search(r'دوره (\S+) ماهه منتهی به (\S+)', t) or re.search(r'سال مالی منتهی به (\S+)', t)
    return m.group(0) if m else ''


# ---------- استخراج از Excel ----------
def parse_income(html):
    soup = BeautifulSoup(html, 'lxml')
    unit = (re.search(r'مبالغ به (میلیون|میلیارد|هزار)? ?ریال', norm(soup.get_text(' '))) or [None])[0]
    for tb in soup.find_all('table'):
        txt = ns(tb.get_text(' '))
        if not txt.startswith('شرح') or 'درصدتغییر' not in txt:
            continue
        rows = [[norm(c.get_text(' ')) for c in tr.find_all(['td', 'th'], recursive=False)] for tr in tb.find_all('tr')]
        np_rows = [r for r in rows if len(r) >= 3 and re.fullmatch(r'سود\(زیان\)خالص', ns(r[0])) and num(r[1]) is not None]
        if not np_rows:
            continue
        rev_rows = [r for r in rows if len(r) >= 3 and re.match(r'(درآمدهایعملیاتی|فروشخالص|درآمدعملیاتی)', ns(r[0]))
                    and num(r[1]) is not None]
        np_ = np_rows[0]
        res = {'unit': unit, 'np_cur': num(np_[1]), 'np_prev': num(np_[2]), 'codal_pct': np_[-1]}
        res['np_growth'] = growth(res['np_cur'], res['np_prev'])
        # کنترل: عدد محاسبه‌شده باید با ستون «درصد تغییر» خود کدال بخواند؛ وگرنه «تأییدنشده» می‌شود
        pct = num(np_[-1])
        res['verified'] = res['np_growth'] is None or (pct is not None and abs(res['np_growth'] - pct) <= max(1.0, 0.01 * abs(pct)))
        if rev_rows:
            res['rev_cur'], res['rev_prev'] = num(rev_rows[0][1]), num(rev_rows[0][2])
            res['rev_growth'] = growth(res['rev_cur'], res['rev_prev'])
        return res
    return None


def fmt(v, suffix=''):
    return '—' if v is None else (f'{v:+,.1f}{suffix}')


def build_report(day_fa, min_growth, rows, stats):
    hits = sorted([r for r in rows if r.get('np_growth') is not None and r['np_growth'] > min_growth
                   and r.get('verified', True)], key=lambda r: -r['np_growth'])
    unverified = [r for r in rows if r.get('verified') is False]
    turn = [r for r in rows if r.get('np_growth') is None and r.get('np_cur') and r['np_cur'] > 0
            and r.get('np_prev') is not None and r['np_prev'] <= 0]
    lines = [f'📑 گزارش کدال — {day_fa}', f'رشد سود خالص بیش از {min_growth}٪ (مقایسه با دوره مشابه سال قبل)', '']
    if hits:
        lines.append('نماد | رشد سود | رشد فروش | دوره')
        for r in hits:
            lines.append(f"{r['symbol']} | {r['np_growth']:+,.1f}٪ | {fmt(r.get('rev_growth'), '٪')} | {r['period']}"
                         + (' (اصلاحیه)' if r['correction'] else ''))
    else:
        lines.append('امروز سهمی با این شرط پیدا نشد.')
    if turn:
        lines += ['', 'سود پس از زیان دوره‌ی قبل (درصد قابل محاسبه نیست):']
        for r in turn:
            lines.append(f"{r['symbol']} | فروش {fmt(r.get('rev_growth'), '٪')} | {r['period']}")
    if unverified:
        lines += ['', 'نیاز به بررسی دستی (عدد با ستون درصد تغییر کدال نمی‌خواند): '
                  + '، '.join(r['symbol'] for r in unverified)]
    lines += ['', f"پوشش:{stats['total']} صورت مالی امروز؛ {stats['parsed']} شرکت خوانده شد؛ "
                  f"{stats['skipped_sub']} گزارش شرکت تابعه، {stats['skipped_other']} صندوق/غیرقابل‌خواندن کنار گذاشته شد.",
              'منبع: صورت‌های مالی منتشرشده در کدال. صرفاً اطلاع‌رسانی است.']
    return '\n'.join(lines)


def send_telegram(text):
    token, chat = os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print('توکن/چت تلگرام تنظیم نیست؛ فقط چاپ شد.')
        return False
    ok = True
    for cid in [c.strip() for c in chat.split(',') if c.strip()]:
        r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                          data={'chat_id': cid, 'text': text}, timeout=30)
        ok &= r.ok
        print('telegram', cid, r.status_code)
    return ok


def load_env():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ.setdefault(k, v)


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', help='تاریخ شمسی YYYY/MM/DD (پیش‌فرض: امروز)')
    ap.add_argument('--min-growth', type=float, default=40.0)
    ap.add_argument('--no-send', action='store_true')
    a = ap.parse_args()
    day = a.date or to_jalali(dt.date.today())
    letters = fetch_letters(day)
    fs = [l for l in letters if 'صورت' in norm(l.get('Title')) and 'مالی' in norm(l.get('Title')) and l.get('ExcelUrl')]
    stats = {'total': len(fs), 'parsed': 0, 'skipped_sub': 0, 'skipped_other': 0}
    best = {}
    for l in fs:
        title = norm(l['Title'])
        if is_subsidiary(title):
            stats['skipped_sub'] += 1
            continue
        key = (l.get('Symbol'), period_of(title))
        # اصلاحیه بر نسخه‌ی قبلی ارجحیت دارد؛ در غیر این صورت جدیدترین
        cur = best.get(key)
        if cur is None or (is_correction(title), l['PublishDateTime']) > (is_correction(cur['Title']), cur['PublishDateTime']):
            best[key] = l
    rows = []
    for (sym, per), l in best.items():
        if norm(l.get('CompanyName')).startswith('صندوق'):
            stats['skipped_other'] += 1
            continue
        try:
            r = requests.get(l['ExcelUrl'], timeout=(20, 120))
            r.raise_for_status()
            res = parse_income(r.content.decode('utf-8', errors='replace'))
        except Exception as e:  # noqa: BLE001
            print('خطا', sym, str(e)[:100])
            res = None
        if not res:
            stats['skipped_other'] += 1
            continue
        stats['parsed'] += 1
        rows.append({'symbol': sym, 'company': l.get('CompanyName'), 'period': per, 'title': norm(l['Title']),
                     'correction': is_correction(l['Title']), 'tracing': l.get('TracingNo'), **res})
    os.makedirs(os.path.join('data', 'iran'), exist_ok=True)
    out = os.path.join('data', 'iran', f"codal_daily_{day.replace('/', '-')}.json")
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    text = build_report(day, a.min_growth, rows, stats)
    print(text)
    if not a.no_send:
        send_telegram(text)


if __name__ == '__main__':
    main()
