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


ASSET_CODE = {'طلا (انس)': 'GOLD', 'نقره (انس)': 'SILVER', 'مس (پوند)': 'COPPER',
              'بیت‌کوین': 'BTC', 'نفت WTI (بشکه)': 'WTI'}


def build_table(rows):
    """جدول شبکه‌ای (خانه‌بندی‌شده) با عرض ثابت در <pre>."""
    data = []
    for r in rows:
        code = ASSET_CODE.get(r['label'], r['label'])
        if r['price'] is None:
            price, chg = 'N/A', 'N/A'
        else:
            price = f"{r['unit']}{r['price']:,.2f}"
            chg = f"{'+' if r['chg'] >= 0 else ''}{r['chg']:.2f}%"
        arrow = '▲' if (r['chg'] or 0) > 0 else ('▼' if (r['chg'] or 0) < 0 else '■')
        data.append((code, price, arrow + ' ' + chg))
    head = ('ASSET', 'PRICE', 'CHANGE')
    w = [max(len(x[i]) for x in [head] + data) + 2 for i in range(3)]
    def line(l, m, r_, fill='─'):
        return l + m.join(fill * wi for wi in w) + r_
    def row(cells):
        return '│' + '│'.join(c.center(wi) if i == 0 else (c.center(wi)) for i, (c, wi) in enumerate(zip(cells, w))) + '│'
    out = [line('┌', '┬', '┐'), row(head), line('╞', '╪', '╡', '═')]
    for i, d in enumerate(data):
        out.append(row(d))
        out.append(line('├', '┼', '┤') if i < len(data) - 1 else line('└', '┴', '┘'))
    return '\n'.join(out)


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
    lines = ['<b>🗞 خلاصه‌ی بازار</b>', '<i>داده‌های لحظه‌ی آخر بازار</i>', '',
             '<b>📊 قیمت‌ها</b>', f'<pre>{html.escape(build_table(prices))}</pre>',
             '<i>GOLD=طلا  SILVER=نقره  COPPER=مس  BTC=بیت‌کوین  WTI=نفت</i>', '',
             '<b>🌍 نرخ بهره و اقتصاد جهانی</b>']
    try:
        lines += ['• ' + x for x in macro_bullets()]
    except Exception as e:
        lines.append(f'⚠️ داده‌های کلان در دسترس نبود: {html.escape(str(e))}')
    gold = next((p for p in prices if p['label'].startswith('طلا') and p['chg'] is not None), None)
    copper = next((p for p in prices if p['label'].startswith('مس') and p['chg'] is not None), None)
    if gold and copper:
        if copper['chg'] > 0 and gold['chg'] > 0:
            view = 'طلا و مس هر دو بالا: هم تقاضای امن و هم امید به رشد.'
        elif copper['chg'] > 0:
            view = 'مس بالا و طلا پایین: امید به رشد اقتصادی.'
        elif gold['chg'] > 0:
            view = 'طلا بالا و مس پایین: احتیاط و نگرانی از رشد.'
        else:
            view = 'طلا و مس هر دو پایین: ریسک‌گریزی کمتر از نگرانی رشد.'
        lines += ['', f'<b>🧭 جمع‌بندی:</b> {view}']
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
