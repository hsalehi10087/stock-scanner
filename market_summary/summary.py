"""خلاصه‌ی بازار روزانه (فارسی): قیمت‌ها + نرخ بهره و اقتصاد جهانی.

منابع (بدون کلید):
  - قیمت‌ها: Yahoo Finance (کتابخانه yfinance)
  - نرخ‌ها و شاخص‌های کلان: FRED (فایل CSV عمومی)
"""
import html
import io
import os
import sys

import pandas as pd
import requests
import yfinance as yf

PRICE_TICKERS = [
    # (برچسب فارسی, نماد Yahoo, واحد)
    ('طلا (انس)', 'GC=F', '$'),
    ('نقره (انس)', 'SI=F', '$'),
    ('مس (پوند)', 'HG=F', '$'),
    ('بیت‌کوین', 'BTC-USD', '$'),
    ('نفت WTI (بشکه)', 'CL=F', '$'),
]

FRED_SERIES = {
    'DGS10': 'بازده اوراق ۱۰ ساله آمریکا',
    'DGS2': 'بازده اوراق ۲ ساله آمریکا',
    'FEDFUNDS': 'نرخ بهره مؤثر فدرال رزرو',
    'VIXCLS': 'شاخص ترس (VIX)',
    'DTWEXBGS': 'شاخص قدرت دلار (گسترده)',
}


def fetch_prices():
    rows = []
    for label, sym, unit in PRICE_TICKERS:
        try:
            hist = yf.Ticker(sym).history(period='10d', interval='1d')['Close'].dropna()
            last, prev = float(hist.iloc[-1]), float(hist.iloc[-2])
            rows.append({'label': label, 'price': last, 'chg': (last / prev - 1) * 100, 'unit': unit})
        except Exception as e:
            print(f'⚠️ {sym}: {e}', file=sys.stderr)
            rows.append({'label': label, 'price': None, 'chg': None, 'unit': unit})
    return rows


def fetch_fred(series_id):
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), na_values=['.'])
    df.columns = ['date', 'value']
    df = df.dropna()
    return df.tail(30)


def fred_last_two(series_id):
    df = fetch_fred(series_id)
    return float(df['value'].iloc[-1]), float(df['value'].iloc[-2])


def build_table(rows):
    """جدول با خطوط کادر برای نمایش در <pre> تلگرام."""
    w1 = max(len(r['label']) for r in rows) + 1
    header = f"{'دارایی':<{w1}}│{'قیمت':>12}│{'تغییر':>9}"
    sep = '─' * w1 + '┼' + '─' * 12 + '┼' + '─' * 9
    lines = ['┌' + '─' * w1 + '┬' + '─' * 12 + '┬' + '─' * 9 + '┐', '│' + header.replace('│', '│') + '│', '├' + sep.replace('┼', '┼') + '┤']
    for r in rows:
        if r['price'] is None:
            price, chg = 'ندارد', '-'
        else:
            price = f"{r['unit']}{r['price']:,.2f}"
            chg = f"{r['chg']:+.2f}%"
        arrow = '▲' if (r['chg'] or 0) > 0 else ('▼' if (r['chg'] or 0) < 0 else '•')
        lines.append(f"│{r['label']:<{w1}}│{price:>12}│{arrow}{chg:>8}│")
    lines.append('└' + '─' * w1 + '┴' + '─' * 12 + '┴' + '─' * 9 + '┘')
    return '\n'.join(lines)


def macro_bullets():
    b = []
    y10, y10p = fred_last_two('DGS10')
    y2, _ = fred_last_two('DGS2')
    ff, ffp = fred_last_two('FEDFUNDS')
    vix, _ = fred_last_two('VIXCLS')
    dxy, dxyp = fred_last_two('DTWEXBGS')

    spread = y10 - y2
    trend10 = 'افزایش' if y10 - y10p > 0.03 else ('کاهش' if y10 - y10p < -0.03 else 'تقریباً ثابت')
    b.append(f"بازده ۱۰ ساله آمریکا: <b>{y10:.2f}٪</b> ({trend10} نسبت به روز قبل)")
    b.append(f"نرخ بهره‌ی مؤثر فدرال: <b>{ff:.2f}٪</b>" + (' (بدون تغییر در آخرین داده)' if abs(ff - ffp) < 0.01 else f' (تغییر از {ffp:.2f}٪)'))
    if spread < 0:
        b.append(f"منحنی بازده وارونه است (۱۰ساله − ۲ساله = {spread:.2f})؛ معمولاً نشانه‌ی نگرانی از رکود است.")
    else:
        b.append(f"منحنی بازده عادی است (۱۰ساله − ۲ساله = {spread:.2f}).")
    b.append(f"شاخص ترس VIX: <b>{vix:.1f}</b>" + (' — نگرانی بالا' if vix >= 20 else ' — نگرانی پایین'))
    dtrend = 'تقویت' if dxy > dxyp else 'تضعیف'
    b.append(f"شاخص دلار: {dtrend} دلار نسبت به روز قبل (عدد {dxy:.1f})")
    return b


def build_message(prices):
    lines = ['<b>🗞 خلاصه‌ی بازار</b>', '', f'<pre>{html.escape(build_table(prices))}</pre>', '',
             '<b>🌍 نرخ بهره و اقتصاد جهانی</b>']
    try:
        lines += ['• ' + x for x in macro_bullets()]
    except Exception as e:
        lines.append(f'⚠️ داده‌های کلان در دسترس نبود: {e}')
    gold = next((p for p in prices if p['label'].startswith('طلا') and p['chg'] is not None), None)
    copper = next((p for p in prices if p['label'].startswith('مس') and p['chg'] is not None), None)
    if gold and copper:
        if copper['chg'] > 0 and gold['chg'] > 0:
            lines.append('• طلا و مس هر دو بالا رفته‌اند: هم تقاضای امن هم انتظار رشد اقتصادی.')
        elif copper['chg'] > 0:
            lines.append('• مس بالا و طلا پایین است: نشانه‌ی امیدواری به رشد اقتصادی.')
        elif gold['chg'] > 0:
            lines.append('• طلا بالا و مس پایین است: نشانه‌ی احتیاط و نگرانی از رشد.')
    return lines


def chunks(lines, limit=3800):
    out, cur = [], ''
    for ln in lines:
        if len(cur) + len(ln) + 1 > limit:
            out.append(cur)
            cur = ''
        cur += ln + '\n'
    if cur.strip():
        out.append(cur)
    return out


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1
    prices = fetch_prices()
    lines = build_message(prices)
    ok = True
    for cid in chat_ids:
        for ch in chunks(lines):
            r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                              data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'}, timeout=20)
            if r.status_code != 200 or '"ok":true' not in r.text:
                print(f'❌ {cid}: {r.status_code} {r.text[:200]}', file=sys.stderr)
                ok = False
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
