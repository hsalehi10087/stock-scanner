"""بورس چین (شانگهای + شنژن): سهم‌هایی که در یک هفته‌ی اخیر (۵ روز معاملاتی) بیش از ۸٪ رشد کرده‌اند
و سود خالص فصلی‌شان نسبت به همان فصل سال قبل بیش از ۱۰٪ رشد داشته.

منابع:
  - فهرست سهام: سایت‌های رسمی SSE (query.sse.com.cn) و SZSE (szse.cn، فایل Excel)
  - قیمت و صورت‌های مالی فصلی: Yahoo (yfinance، نمادهای .SS و .SZ)
خروجی: پیام تلگرام و CSV در data/cn_gainers/YYYY-MM-DD.csv
"""
import datetime as dt
import html
import io
import os
import random
import sys

import pandas as pd
import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'market_summary'))
import gainers  # noqa: E402
import jp_growth  # noqa: E402
import summary as S  # noqa: E402
from report import fa  # noqa: E402

ROOT = os.path.dirname(HERE)
HIST_DIR = os.path.join(ROOT, 'data', 'cn_gainers')
PRICE_TH = 8.0  # رشد هفتگی (۵ روز معاملاتی)
GROWTH_TH = 10.0
MIN_PRICE_CNY = 1.0
MIN_VOLUME = 100_000
jp_growth.MIN_PREV_JPY = 10_000_000  # حداقل سود فصل قبل: ۱۰ میلیون یوآن
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
DIAG = []


def sse_list():
    out = {}
    for stock_type in ('1', '8'):  # ۱ = بازار اصلی A، ۸ = STAR
        params = {'STOCK_TYPE': stock_type, 'REG_PROVINCE': '', 'CSRC_CODE': '', 'STOCK_CODE': '',
                  'sqlId': 'COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L', 'COMPANY_STATUS': '2,4,5,7,8',
                  'type': 'inParams', 'isPagination': 'true', 'pageHelp.cacheSize': '1',
                  'pageHelp.beginPage': '1', 'pageHelp.pageSize': '10000', 'pageHelp.pageNo': '1',
                  'pageHelp.endPage': '1'}
        import time
        r = None
        for k in range(4):
            try:
                r = requests.get('https://query.sse.com.cn/sseQuery/commonQuery.do', params=params, timeout=60,
                                 headers={'User-Agent': UA, 'Referer': 'https://www.sse.com.cn/'})
                DIAG.append(f'SSE type={stock_type} try{k + 1} {r.status_code} len={len(r.text)}')
                if r.status_code == 200:
                    break
            except Exception as e:
                DIAG.append(f'SSE type={stock_type} try{k + 1} ERR {str(e)[:80]}')
            time.sleep(4 * (k + 1))
        r.raise_for_status()
        for row in r.json().get('result', []):
            code = str(row.get('A_STOCK_CODE') or row.get('COMPANY_CODE') or '').strip()
            name = row.get('COMPANY_ABBR') or row.get('SEC_NAME_CN') or row.get('FULL_NAME') or ''
            if code.isdigit() and len(code) == 6:
                out[f'{code}.SS'] = name
    return out


SZSE_HEADERS = {'User-Agent': UA, 'Referer': 'https://www.szse.cn/market/product/stock/list/index.html'}


def _szse_get(url, params, tries=4):
    import time
    last = None
    for k in range(tries):
        try:
            r = requests.get(url, params=params, timeout=60, headers=SZSE_HEADERS)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            DIAG.append(f'SZSE retry {k + 1}: {str(e)[:100]}')
            time.sleep(3 * (k + 1))
    raise last


def _szse_xlsx():
    params = {'SHOWTYPE': 'xlsx', 'CATALOGID': '1110', 'TABKEY': 'tab1', 'random': str(random.random())}
    r = _szse_get('https://www.szse.cn/api/report/ShowReport', params)
    DIAG.append(f'SZSE xlsx {r.status_code} len={len(r.content)}')
    df = pd.read_excel(io.BytesIO(r.content), dtype=str, engine='openpyxl')
    code_col = next(c for c in df.columns if 'A股代码' in str(c))
    name_col = next((c for c in df.columns if 'A股简称' in str(c)), None) or next(c for c in df.columns if '简称' in str(c))
    return {f'{str(c).strip().zfill(6)}.SZ': str(n).strip() for c, n in zip(df[code_col], df[name_col])
            if str(c).strip().isdigit()}


def _szse_json():
    import re
    import time
    out, page, pages = {}, 1, 1
    while page <= pages:
        params = {'SHOWTYPE': 'JSON', 'CATALOGID': '1110', 'TABKEY': 'tab1', 'PAGENO': str(page),
                  'random': str(random.random())}
        r = _szse_get('https://www.szse.cn/api/report/ShowReport/data', params)
        block = r.json()[0]
        pages = int(block.get('metadata', {}).get('pagecount', 1) or 1)
        for row in block.get('data', []):
            code = re.sub(r'<[^>]+>', '', str(row.get('agdm', ''))).strip()
            name = re.sub(r'<[^>]+>', '', str(row.get('agjc', ''))).strip()
            if code.isdigit() and len(code) == 6:
                out[f'{code}.SZ'] = name
        page += 1
        time.sleep(0.3)
    DIAG.append(f'SZSE json pages={pages} rows={len(out)}')
    return out


def szse_list():
    try:
        return _szse_xlsx()
    except Exception as e:
        DIAG.append(f'SZSE xlsx failed: {str(e)[:120]} -> trying JSON')
        return _szse_json()


def weekly_changes(symbols, chunk=200):
    """تغییر قیمت ۵ روز معاملاتی اخیر: آخرین بسته‌شدن نسبت به ۵ روز معاملاتی قبل."""
    res = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        try:
            df = yf.download(part, period='1mo', interval='1d', group_by='ticker',
                             threads=True, progress=False, auto_adjust=False)
        except Exception as e:
            DIAG.append(f'ERR batch {i}: {str(e)[:120]}')
            continue
        for s in part:
            try:
                close = df[s]['Close'].dropna()
                vol = df[s]['Volume'].dropna()
                if len(close) < 6:
                    continue
                last, base = float(close.iloc[-1]), float(close.iloc[-6])
                res[s] = {'price': last, 'chg': (last / base - 1) * 100,
                          'volume': float(vol.tail(5).mean()) if len(vol) else 0.0,
                          'date': str(close.index[-1].date()), 'from': str(close.index[-6].date())}
            except Exception:
                continue
    return res


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1
    names = {}
    for fn, cache_name in ((sse_list, 'universe_sse.csv'), (szse_list, 'universe_szse.csv')):
        cache = os.path.join(HIST_DIR, cache_name)
        try:
            got = fn()
            if len(got) > 500:
                os.makedirs(HIST_DIR, exist_ok=True)
                pd.DataFrame({'ticker': list(got), 'name': list(got.values())}).to_csv(cache, index=False, encoding='utf-8')
            names.update(got)
        except Exception as e:
            DIAG.append(f'ERR {fn.__name__}: {str(e)[:200]}')
            if os.path.exists(cache):
                df = pd.read_csv(cache, dtype=str)
                names.update(dict(zip(df['ticker'], df['name'])))
                DIAG.append(f'used cached {cache_name}: {len(df)} rows')
            else:
                DIAG.append(f'no cache for {cache_name}')
    DIAG.append(f'tickers={len(names)}')
    if not names:
        raise RuntimeError('فهرست سهام چین دریافت نشد')
    prices = weekly_changes(sorted(names))
    cands = [(s, d) for s, d in prices.items()
             if d['chg'] > PRICE_TH and d['price'] >= MIN_PRICE_CNY and d['volume'] >= MIN_VOLUME]
    DIAG.append(f'priced={len(prices)} price_gainers={len(cands)}')
    rows, with_data = [], 0
    for s, d in cands:
        g = jp_growth.net_income_growth(s)
        if g is not None:
            with_data += 1
        if g and g[0] > GROWTH_TH:
            rows.append({'ticker': s, 'name': names[s], 'price_chg': d['chg'], 'ni_growth': g[0],
                         'ni_cur_m_cny': g[1] / 1e6, 'ni_prev_m_cny': g[2] / 1e6, 'date': d['date']})
    DIAG.append(f'qualified={len(rows)} (growth computed for {with_data} of {len(cands)})')
    rows.sort(key=lambda r: -r['ni_growth'])
    date = rows[0]['date'] if rows else (cands[0][1]['date'] if cands else str(dt.date.today()))
    os.makedirs(HIST_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(HIST_DIR, f'{date}.csv'), index=False, encoding='utf-8')

    week_from = cands[0][1]['from'] if cands else ''
    lines = [f'<b>🇨🇳 بورس چین: رشد هفتگی قیمت بیش از ۸٪ + رشد سود خالص بیش از ۱۰٪</b> — {date}',
             f'<i>{len(rows)} سهم از {len(cands)} سهم با رشد هفتگی بیش از ۸٪ (از {len(prices)} سهم بررسی‌شده)</i>',
             f'<i>بازه‌ی قیمت: {week_from} تا {date} (۵ روز معاملاتی)</i>', '']
    for r in rows[:30]:
        nm = fa(r['name']) or r['name']
        lines.append(f"• <b>{r['ticker']}</b> ({html.escape(nm)}): قیمت هفتگی +{r['price_chg']:.1f}٪ | سود +{r['ni_growth']:.1f}٪")
    if not rows:
        lines.append('امروز سهمی با هر دو شرط پیدا نشد.')
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
