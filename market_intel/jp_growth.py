"""بورس توکیو: سهم‌هایی که امروز بیش از ۱۰٪ رشد کرده‌اند و سود خالص فصلی‌شان نسبت به سال قبل بیش از ۱۰٪ رشد داشته.

منابع (بدون کلید): فهرست شرکت‌ها از JPX، قیمت و صورت‌های مالی فصلی از Yahoo (yfinance، نماد .T).
خروجی: جدول متنی به تلگرام، و CSV در data/jp_gainers/YYYY-MM-DD.csv
"""
import datetime as dt
import io
import os
import sys
import tempfile

import pandas as pd
import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'market_summary'))
import gainers  # noqa: E402
import summary as S  # noqa: E402
from report import fa  # noqa: E402
import quality as Q  # noqa: E402

ROOT = os.path.dirname(HERE)
HIST_DIR = os.path.join(ROOT, 'data', 'jp_gainers')
PRICE_TH = 10.0
GROWTH_TH = 10.0
MIN_PRICE_JPY = 100
MIN_VOLUME = 100_000
MIN_PREV_JPY = 100_000_000
JPX_URL = 'https://www.jpx.co.jp/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_e.xlsx'
UA = {'User-Agent': 'Mozilla/5.0'}
DIAG = []


def tse_list():
    r = requests.get(JPX_URL, headers=UA, timeout=60)
    DIAG.append(f'JPX {r.status_code} len={len(r.content)}')
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), dtype=str, engine='openpyxl')
    code_col = [c for c in df.columns if 'code' in str(c).lower()][0]
    name_col = [c for c in df.columns if 'name' in str(c).lower() and 'english' in str(c).lower()][0]
    out = {}
    for code, name in zip(df[code_col], df[name_col]):
        code = str(code).strip()
        if code.isdigit() or (len(code) == 4 and code[:3].isdigit()):
            out[f'{code}.T'] = name
    return out


def net_income_growth(sym):
    """رشد سود خالص فصل آخر نسبت به همان فصل سال قبل، یا None."""
    try:
        q = yf.Ticker(sym).quarterly_income_stmt
    except Exception:
        return None
    if q is None or q.empty:
        return None
    row = None
    for label in ('Net Income', 'Net Income Common Stockholders', 'Net Income Including Noncontrolling Interests'):
        if label in q.index:
            row = q.loc[label].dropna()
            break
    if row is None or len(row) < 5:
        return None
    row = row.sort_index(ascending=False)
    cur_date, cur = row.index[0], float(row.iloc[0])
    target = cur_date - pd.Timedelta(days=365)
    prev_candidates = [(abs((d - target).days), d, float(v)) for d, v in row.items() if abs((d - target).days) <= 25]
    if not prev_candidates:
        return None
    _, prev_date, prev = min(prev_candidates)
    if prev < MIN_PREV_JPY or cur <= prev:
        return None
    return (cur - prev) / prev * 100, cur, prev, str(cur_date.date())


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1
    names = tse_list()
    prices = gainers.daily_changes(sorted(names))
    cands = [(s, d) for s, d in prices.items()
             if d['chg'] > PRICE_TH and d['price'] >= MIN_PRICE_JPY and d['volume'] >= MIN_VOLUME]
    DIAG.append(f'tickers={len(names)} priced={len(prices)} price_gainers={len(cands)}')
    rows = []
    for s, d in cands:
        g = net_income_growth(s)
        if g and g[0] > GROWTH_TH:
            rows.append({'ticker': s.replace('.T', ''), 'name': names[s], 'price_chg': d['chg'],
                         'ni_growth': g[0], 'ni_cur_m': g[1] / 1e6, 'ni_prev_m': g[2] / 1e6,
                         'date': d['date']})
    rows.sort(key=lambda r: -r['price_chg'])
    Q.annotate(rows, 'jp', sym_of=lambda r: r['ticker'] + '.T')
    date = rows[0]['date'] if rows else (cands[0][1]['date'] if cands else str(dt.date.today()))
    os.makedirs(HIST_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(HIST_DIR, f'{date}.csv'), index=False, encoding='utf-8')
    with open(os.path.join(HIST_DIR, 'diagnostics.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(DIAG) + '\n')

    lines = [f'<b>🇯🇵 بورس توکیو: رشد قیمت بیش از ۱۰٪ + رشد سود خالص بیش از ۱۰٪</b> — {date}',
             f'<i>{len(rows)} سهم از {len(cands)} سهم با رشد قیمت بیش از ۱۰٪</i>', '']
    for r in rows[:30]:
        nm = fa(r['name']) or r['name']
        lines.append(f"• <b>{r['ticker']}</b> ({html_escape(nm)}): قیمت +{r['price_chg']:.1f}٪ | سود +{r['ni_growth']:.1f}٪ {r.get('qs_label', '')}")
    if not rows:
        lines.append('امروز سهمی با هر دو شرط پیدا نشد.')
    else:
        lines += ['', Q.best_line(rows), Q.LEGEND]
    text_chunks = S.chunks(lines)
    ok = True
    for cid in chat_ids:
        for ch in text_chunks:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


def html_escape(s):
    import html
    return html.escape(s)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        os.makedirs(HIST_DIR, exist_ok=True)
        with open(os.path.join(HIST_DIR, 'diagnostics.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(DIAG) + f'\nERROR: {e}\n')
        raise
