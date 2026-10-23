"""بورس تایوان (TWSE + TPEx): سهم‌هایی که در یک هفته‌ی اخیر (۵ روز معاملاتی) بیش از ۱۰٪ رشد کرده‌اند
و سود خالص فصلی‌شان نسبت به همان فصل سال قبل بیش از ۱۰٪ رشد داشته.
(سقف رشد روزانه در تایوان ۱۰٪ است، پس شرط قیمت هفتگی است.)

منابع:
  - فهرست سهام: OpenAPI رسمی TWSE (openapi.twse.com.tw) و TPEx (tpex.org.tw/openapi)
  - قیمت و صورت‌های مالی فصلی: Yahoo (yfinance، نمادهای .TW و .TWO)
خروجی: پیام تلگرام و CSV در data/tw_gainers/YYYY-MM-DD.csv
"""
import datetime as dt
import html
import os
import sys
import time

import pandas as pd
import re

import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'market_summary'))
import cn_growth  # noqa: E402
import jp_growth  # noqa: E402
import summary as S  # noqa: E402
from report import fa  # noqa: E402

ROOT = os.path.dirname(HERE)
HIST_DIR = os.path.join(ROOT, 'data', 'tw_gainers')
PRICE_TH = 10.0  # رشد هفتگی
GROWTH_TH = 10.0
MIN_PRICE_TWD = 5.0
MIN_VOLUME = 100_000
jp_growth.MIN_PREV_JPY = 50_000_000  # حداقل سود فصل قبل: ۵۰ میلیون دلار تایوان
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
      'Accept': 'application/json'}
DIAG = cn_growth.DIAG  # یک فهرست تشخیص مشترک


import quality as Q  # noqa: E402


def _get_json(url, tries=4):
    last = None
    for k in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            DIAG.append(f'{url.split("/")[2]} try{k + 1} {r.status_code} len={len(r.text)}')
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(3 * (k + 1))
    raise last


CJK = re.compile(r'[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]')


def en_name(sym):
    """نام انگلیسی شرکت از Yahoo، بدون هیچ حرف چینی؛ اگر نبود رشته‌ی خالی."""
    try:
        info = yf.Ticker(sym).get_info()
        n = info.get('shortName') or info.get('longName') or ''
    except Exception:
        n = ''
    n = CJK.sub('', str(n)).strip(' -,')
    return n


def twse_list():
    data = _get_json('https://openapi.twse.com.tw/v1/opendata/t187ap03_L')
    out = {}
    for row in data:
        code = str(row.get('公司代號', '')).strip()
        name = str(row.get('公司簡稱') or row.get('公司名稱') or '').strip()
        if code.isdigit() and len(code) == 4:
            out[f'{code}.TW'] = name
    return out


def tpex_list():
    data = _get_json('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes')
    out = {}
    for row in data:
        code = str(row.get('SecuritiesCompanyCode', '')).strip()
        name = str(row.get('CompanyName', '')).strip()
        if code.isdigit() and len(code) == 4:
            out[f'{code}.TWO'] = name
    return out


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1
    names = {}
    for fn, cache_name in ((twse_list, 'universe_twse.csv'), (tpex_list, 'universe_tpex.csv')):
        cache = os.path.join(HIST_DIR, cache_name)
        try:
            got = fn()
            DIAG.append(f'{fn.__name__}: {len(got)}')
            if len(got) > 300:
                os.makedirs(HIST_DIR, exist_ok=True)
                pd.DataFrame({'ticker': list(got), 'name': list(got.values())}).to_csv(cache, index=False, encoding='utf-8')
            names.update(got)
        except Exception as e:
            DIAG.append(f'ERR {fn.__name__}: {str(e)[:200]}')
            if os.path.exists(cache):
                df = pd.read_csv(cache, dtype=str)
                names.update(dict(zip(df['ticker'], df['name'])))
                DIAG.append(f'used cached {cache_name}: {len(df)} rows')
    DIAG.append(f'tickers={len(names)}')
    if not names:
        raise RuntimeError('فهرست سهام تایوان دریافت نشد')
    prices = cn_growth.weekly_changes(sorted(names))
    cands = [(s, d) for s, d in prices.items()
             if d['chg'] > PRICE_TH and d['price'] >= MIN_PRICE_TWD and d['volume'] >= MIN_VOLUME]
    DIAG.append(f'priced={len(prices)} price_gainers={len(cands)}')
    rows, with_data = [], 0
    for s, d in cands:
        g = jp_growth.net_income_growth(s)
        if g is not None:
            with_data += 1
        if g and g[0] > GROWTH_TH:
            rows.append({'ticker': s, 'name': names[s], 'price_chg': d['chg'], 'ni_growth': g[0],
                         'ni_cur_m_twd': g[1] / 1e6, 'ni_prev_m_twd': g[2] / 1e6, 'date': d['date']})
    DIAG.append(f'qualified={len(rows)} (growth computed for {with_data} of {len(cands)})')
    rows.sort(key=lambda r: -r['ni_growth'])
    Q.annotate(rows, 'tw')
    date = rows[0]['date'] if rows else (cands[0][1]['date'] if cands else str(dt.date.today()))
    week_from = cands[0][1]['from'] if cands else ''
    os.makedirs(HIST_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(HIST_DIR, f'{date}.csv'), index=False, encoding='utf-8')

    lines = [f'<b>🇹🇼 بورس تایوان: رشد هفتگی قیمت بیش از ۱۰٪ + رشد سود خالص بیش از ۱۰٪</b> — {date}',
             f'<i>{len(rows)} سهم از {len(cands)} سهم با رشد هفتگی بیش از ۱۰٪ (از {len(prices)} سهم بررسی‌شده)</i>',
             f'<i>بازه‌ی قیمت: {week_from} تا {date} (۵ روز معاملاتی)</i>', '']
    for r in rows[:30]:
        nm = en_name(r['ticker'])
        label = f" ({html.escape(nm)})" if nm else ''
        lines.append(f"• <b>{r['ticker']}</b>{label}: قیمت هفتگی +{r['price_chg']:.1f}٪ | سود +{r['ni_growth']:.1f}٪ {r.get('qs_label', '')}")
    if not rows:
        lines.append('سهمی با هر دو شرط پیدا نشد.')
    else:
        lines += ['', Q.best_line(rows), Q.LEGEND]
    ok = True
    for cid in chat_ids:
        for ch in S.chunks(lines):
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    try:
        code = main()
    except Exception as e:
        DIAG.append(f'ERROR: {e}')
        code = 3
    os.makedirs(HIST_DIR, exist_ok=True)
    with open(os.path.join(HIST_DIR, 'diagnostics.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(DIAG) + '\n')
    sys.exit(code)
