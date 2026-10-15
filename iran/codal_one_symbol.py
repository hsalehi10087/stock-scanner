"""اثبات دریافت داده‌ی واقعی کدال برای یک نماد (پیش‌فرض: فولاد).

باید روی سروری اجرا شود که به کدال دسترسی دارد (داخل ایران). از سرورهای گیت‌هاب (آمریکا) مسدود است.
مراحل و خروجی‌ها (data/iran/<symbol>/):
  1) جست‌وجو در search.codal.ir/api/search/v2/q  → letters.csv  (JSON با هدر Accept؛ اگر XML آمد، تجزیه با regex)
  2) پیدا کردن آخرین «صورت‌های مالی» دارای Excel  → statement_raw.html (فایل Excel کدال در واقع HTML است)
  3) استخراج اقلام کلیدی صورت سود و زیان و ترازنامه با برچسب جدول (جداگانه/تلفیقی) → statement_items.csv
  4) validation.json: وضعیت هر مرحله با تفکیک «لینک پیدا شد / داده دریافت شد / فایل پردازش شد»
هیچ عددی ساخته نمی‌شود؛ هر چه پیدا نشود، خالی و با دلیل ثبت می‌شود.
"""
import html as htmllib
import json
import os
import re
import sys
import time

import pandas as pd
import requests

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else 'فولاد'
OUT = os.path.join('data', 'iran', SYMBOL)
HEAD = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
SEARCH = 'https://search.codal.ir/api/search/v2/q'
KEY_ITEMS = ['درآمدهای عملیاتی', 'سود (زیان) ناخالص', 'سود (زیان) عملیاتی', 'سود (زیان) خالص',
             'سود (زیان) پایه هر سهم', 'جمع دارایی‌ها', 'جمع بدهی‌ها', 'جمع حقوق مالکانه', 'جمع حقوق صاحبان سهام',
             'نقد حاصل از عملیات', 'جریان خالص ورود (خروج) نقد حاصل از فعالیت‌های عملیاتی']
V = {'symbol': SYMBOL, 'steps': {}}


def step(name, **kw):
    V['steps'][name] = kw
    print(name, kw)


def get(url, params=None, tries=4):
    for k in range(tries):
        r = requests.get(url, params=params, headers=HEAD, timeout=(20, 60))
        if r.status_code == 429:
            time.sleep(30 * (k + 1))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()


def parse_letters(r):
    ctype = r.headers.get('content-type', '')
    if 'json' in ctype:
        return r.json().get('Letters', []), 'json'
    items = re.findall(r'<CodalLetterHeaderDto[^>]*>(.*?)</CodalLetterHeaderDto>', r.text, re.S)
    out = []
    for it in items:
        out.append({k: htmllib.unescape(v) for k, v in re.findall(r'<(\w+)>(.*?)</\1>', it, re.S)})
    return out, 'xml'


def cell_text(c):
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()


def main():
    os.makedirs(OUT, exist_ok=True)
    # 1) جست‌وجو
    try:
        r = get(SEARCH, {'Symbol': SYMBOL, 'PageNumber': 1, 'Length': -1, 'search': 'true'})
        letters, fmt = parse_letters(r)
        pd.DataFrame(letters).to_csv(os.path.join(OUT, 'letters.csv'), index=False, encoding='utf-8-sig')
        step('1_search', status='data_received' if letters else 'empty', format=fmt, http=r.status_code, letters=len(letters))
    except Exception as e:
        step('1_search', status='failed', error=str(e)[:200])
        return
    # 2) آخرین صورت مالی میان‌دوره‌ای/سالانه با Excel
    fs = [l for l in letters if 'صورت' in str(l.get('Title', '')) and 'مالی' in str(l.get('Title', ''))
          and str(l.get('HasExcel', '')).lower() == 'true' and l.get('ExcelUrl')]
    if not fs:
        step('2_find_statement', status='not_found', reason='هیچ نامه‌ی «صورت‌های مالی» با Excel در نتایج نبود')
        return
    fs.sort(key=lambda l: str(l.get('PublishDateTime') or l.get('SentDateTime') or ''), reverse=True)
    target = fs[0]
    step('2_find_statement', status='link_found', title=target.get('Title'), tracing=target.get('TracingNo'),
         published=target.get('PublishDateTime'), excel_url=target.get('ExcelUrl'),
         is_correction='اصلاحیه' in str(target.get('Title', '')))
    # 3) دریافت فایل
    try:
        x = get(target['ExcelUrl'])
        raw = os.path.join(OUT, 'statement_raw.html')
        open(raw, 'wb').write(x.content)
        step('3_download', status='file_received', bytes=len(x.content), content_type=x.headers.get('content-type'))
    except Exception as e:
        step('3_download', status='failed', error=str(e)[:200])
        return
    # 4) استخراج اقلام کلیدی
    text = x.content.decode('utf-8', errors='replace')
    tables = re.findall(r'<table.*?</table>', text, re.S | re.I)
    rows = []
    for ti, t in enumerate(tables):
        head = cell_text(t[:2000])
        kind = 'تلفیقی' if 'تلفیقی' in head else ('جداگانه' if ('جداگانه' in head or 'شرکت اصلی' in head) else 'نامشخص')
        for tr in re.findall(r'<tr.*?</tr>', t, re.S | re.I):
            cells = [cell_text(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S | re.I)]
            if cells and any(cells[0].startswith(k) for k in KEY_ITEMS):
                rows.append({'table': ti, 'table_kind': kind, 'item': cells[0], 'values': ' | '.join(cells[1:6])})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, 'statement_items.csv'), index=False, encoding='utf-8-sig')
    step('4_parse', status='file_processed' if rows else 'parsed_but_no_items', tables=len(tables), key_rows=len(rows))


if __name__ == '__main__':
    try:
        main()
    finally:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, 'validation.json'), 'w', encoding='utf-8') as f:
            json.dump(V, f, ensure_ascii=False, indent=1)
