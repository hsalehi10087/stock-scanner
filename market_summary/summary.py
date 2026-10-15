"""خلاصه‌ی بازار روزانه (فارسی): قیمت‌ها + نرخ بهره و اقتصاد جهانی.

منابع (بدون کلید):
  - قیمت‌ها: Yahoo Finance (کتابخانه yfinance)
  - نرخ‌ها و شاخص‌های کلان: FRED (فایل CSV عمومی)
"""
import html
import io
import os
import sys
import tempfile

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


def table_cells(rows):
    out = []
    for r in rows:
        code = ASSET_CODE.get(r['label'], r['label'])
        if r['price'] is None:
            out.append((code, 'N/A', 'N/A', None))
            continue
        chg = r['chg']
        arrow = '▲' if chg > 0 else ('▼' if chg < 0 else '■')
        out.append((code, f"{r['unit']}{r['price']:,.2f}", f"{arrow} {'+' if chg >= 0 else ''}{chg:.2f}%", chg))
    return out


def render_table_png(rows, path):
    """جدول واقعی با خطوط شبکه و متن بولد (تلگرام داخل <pre> بولد نمی‌کند، پس عکس می‌فرستیم)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data = table_cells(rows)
    cells = [[c, p, ch] for c, p, ch, _ in data]
    fig, ax = plt.subplots(figsize=(6.4, 0.65 * (len(cells) + 1)))
    ax.axis('off')
    t = ax.table(cellText=cells, colLabels=['ASSET', 'PRICE', 'CHANGE'], loc='center', cellLoc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(15)
    t.scale(1, 1.9)
    for (i, j), cell in t.get_celld().items():
        cell.set_edgecolor('#9ca3af')
        cell.set_linewidth(1)
        txt = cell.get_text()
        txt.set_fontweight('bold')
        if i == 0:
            cell.set_facecolor('#1f2937')
            txt.set_color('white')
        else:
            cell.set_facecolor('#f3f4f6' if i % 2 else 'white')
            chg = data[i - 1][3]
            if j == 2 and chg is not None:
                txt.set_color('#15803d' if chg > 0 else ('#b91c1c' if chg < 0 else '#374151'))
    fig.savefig(path, dpi=170, bbox_inches='tight', facecolor='white')
    plt.close(fig)


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


def build_verdict(prices):
    gold = next((p for p in prices if p['label'].startswith('طلا') and p['chg'] is not None), None)
    copper = next((p for p in prices if p['label'].startswith('مس') and p['chg'] is not None), None)
    if not (gold and copper):
        return None
    if copper['chg'] > 0 and gold['chg'] > 0:
        view = 'طلا و مس هر دو بالا رفتند: هم بازار امن‌ترین دارایی را می‌خرد، هم به رشد اقتصاد امید دارد.'
    elif copper['chg'] > 0:
        view = 'مس بالا و طلا پایین: بازار به رشد اقتصاد امید دارد.'
    elif gold['chg'] > 0:
        view = 'طلا بالا و مس پایین: بازار به امن‌ترین دارایی پناه برده و به رشد اقتصاد اطمینان ندارد.'
    else:
        view = 'طلا و مس هر دو پایین: بازار کالاها در فشار فروش است.'
    return f'<b>🧭 جمع‌بندی:</b> {view}'


def build_text(prices):
    lines = ['<b>🌍 نرخ بهره و اقتصاد جهانی</b>']
    try:
        lines += ['• ' + x for x in macro_bullets()]
    except Exception as e:
        lines.append(f'⚠️ داده‌های کلان در دسترس نبود: {html.escape(str(e))}')
    v = build_verdict(prices)
    if v:
        lines += ['', v]
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


def tg_post(token, cid, method, **kw):
    r = requests.post(f'https://api.telegram.org/bot{token}/{method}', timeout=60, **kw)
    if r.status_code != 200 or '"ok":true' not in r.text:
        print(f'❌ {cid} {method}: {r.status_code} {r.text[:200]}', file=sys.stderr)
        return False
    return True


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1
    prices = fetch_prices()
    png = os.path.join(tempfile.mkdtemp(), 'market_table.png')
    render_table_png(prices, png)
    caption = ('<b>🗞 خلاصه‌ی بازار</b>\n'
               '<i>داده‌های لحظه‌ی آخر بازار</i>\n'
               '<b>📊 قیمت‌ها</b>\n'
               '<i>GOLD=طلا  SILVER=نقره  COPPER=مس  BTC=بیت‌کوین  WTI=نفت</i>')
    text_chunks = chunks(build_text(prices))
    ok = True
    for cid in chat_ids:
        with open(png, 'rb') as f:
            ok &= tg_post(token, cid, 'sendPhoto', data={'chat_id': cid, 'caption': caption, 'parse_mode': 'HTML'},
                          files={'photo': f})
        for ch in text_chunks:
            ok &= tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
