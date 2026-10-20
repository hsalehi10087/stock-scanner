"""اسکن روزانه‌ی سهام آمریکا (NASDAQ + NYSE/AMEX): سهم‌هایی که امروز بیش از ۱۰٪ رشد کرده‌اند.

منابع (بدون کلید): فهرست نمادها از nasdaqtrader.com، قیمت‌ها از Yahoo (yfinance).
خروجی: جدول تصویری + خلاصه به تلگرام، و فایل تاریخچه‌ی CSV در data/gainers/YYYY-MM-DD.csv
"""
import io
import os
import re
import sys

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'market_summary'))
import summary as S  # noqa: E402
import signal_tracker as T  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_DIR = os.path.join(ROOT, 'data', 'gainers')
THRESHOLD = 10.0
MIN_PRICE = 1.0
MIN_VOLUME = 100_000
UA = {'User-Agent': 'Mozilla/5.0 (compatible; gainers-scan/1.0)'}


def universe():
    out = {}
    for url, sym_col in [('https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt', 'Symbol'),
                         ('https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt', 'ACT Symbol')]:
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep='|', dtype=str)
        df = df[(df['Test Issue'] == 'N') & (df['ETF'] == 'N')]
        for sym, name in zip(df[sym_col], df['Security Name']):
            if isinstance(sym, str) and re.fullmatch(r'[A-Z]{1,5}', sym):
                out.setdefault(sym, name)
    return out


def daily_changes(symbols, chunk=200):
    res = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        try:
            df = yf.download(part, period='5d', interval='1d', group_by='ticker',
                             threads=True, progress=False, auto_adjust=False)
        except Exception as e:
            print(f'⚠️ دسته {i}: {e}', file=sys.stderr)
            continue
        for s in part:
            try:
                close = df[s]['Close'].dropna()
                vol = df[s]['Volume'].dropna()
                if len(close) < 2:
                    continue
                last, prev = float(close.iloc[-1]), float(close.iloc[-2])
                res[s] = {'price': last, 'chg': (last / prev - 1) * 100,
                          'volume': float(vol.iloc[-1]) if len(vol) else 0.0,
                          'date': str(close.index[-1].date())}
            except Exception:
                continue
    return res


def fa_text(s):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


def render_png(rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cells = []
    for r in rows:
        name = (r['name'] or '')
        name = name.split(' - ')[0].split(' Common')[0][:34]
        cells.append([r['ticker'], name[:28], f"${float(r['price']):,.2f}", f"+{float(r['chg']):.1f}%",
                      f"{int(r.get('count', 1))}x", f"{float(r.get('ret', 0)):+.1f}%"])
    heads = ['TICKER', 'COMPANY', 'PRICE', 'CHANGE', 'SIGNALS', 'SINCE 1ST']
    fig, ax = plt.subplots(figsize=(11.5, 0.45 * (len(cells) + 1) + 0.4))
    ax.axis('off')
    t = ax.table(cellText=cells, colLabels=heads, loc='center', cellLoc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(11)
    t.scale(1, 1.5)
    widths = {0: 0.12, 1: 0.36, 2: 0.14, 3: 0.14, 4: 0.11, 5: 0.14}
    for (i, j), cell in t.get_celld().items():
        cell.set_width(widths[j])
        cell.set_edgecolor('#9ca3af')
        txt = cell.get_text()
        txt.set_fontweight('bold')
        if i == 0:
            cell.set_facecolor('#1f2937')
            txt.set_color('white')
        else:
            cell.set_facecolor('#f3f4f6' if i % 2 else 'white')
            if j == 3:
                txt.set_color('#15803d')
            if j == 5:
                txt.set_color('#15803d' if not txt.get_text().startswith('-') else '#b91c1c')
    fig.savefig(path, dpi=160, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1

    names = universe()
    print(f'نمادهای بررسی‌شده: {len(names)}')
    prices = daily_changes(sorted(names))
    checked = len(prices)
    rows = []
    for s, d in prices.items():
        if d['chg'] > THRESHOLD and d['price'] >= MIN_PRICE and d['volume'] >= MIN_VOLUME:
            rows.append({'ticker': s, 'name': names.get(s, ''), 'price': d['price'],
                         'chg': d['chg'], 'volume': d['volume'], 'date': d['date']})
    rows.sort(key=lambda r: -r['chg'])
    date = rows[0]['date'] if rows else (next(iter(prices.values()))['date'] if prices else 'نامشخص')

    os.makedirs(HIST_DIR, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(HIST_DIR, f'{date}.csv'), index=False, encoding='utf-8')

    # پیگیری: چند بار سیگنال شده و بازده از اولین سیگنال
    state = T.load('gainers')
    if state is None:
        state = T.bootstrap('gainers', HIST_DIR, price_col='price')
    for r in rows:
        T.add(state, r['ticker'], date, date, r['price'])
    T.save('gainers', state)
    trk = {x['ticker']: x for x in T.returns(state, {s: d['price'] for s, d in prices.items()})}
    for r in rows:
        r['count'] = trk.get(r['ticker'], {}).get('count', 1)
        r['ret'] = trk.get(r['ticker'], {}).get('ret', 0.0)
    since = min((v['first_date'] for v in state.values()), default=date)
    track_msg = T.summary_text('رشد قیمت بیش از ۱۰٪', list(trk.values()), since, 'بار')

    head = [f'<b>🚀 سهام آمریکا با رشد بیش از ۱۰٪</b> — {date}',
            f'<i>{len(rows)} سهم از {checked} سهم بررسی‌شده</i>']
    if rows:
        png = os.path.join(__import__('tempfile').mkdtemp(), 'gainers.png')
        render_png(rows[:25], png)
        more = f'\nبقیه در فایل تاریخچه‌ی ریپو ثبت شده است.' if len(rows) > 25 else ''
        ok = True
        for cid in chat_ids:
            with open(png, 'rb') as f:
                ok &= S.tg_post(token, cid, 'sendPhoto', data={'chat_id': cid, 'caption': '\n'.join(head) + more,
                                                              'parse_mode': 'HTML'}, files={'photo': f})
    else:
        ok = True
        for cid in chat_ids:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'parse_mode': 'HTML',
                                                            'text': '\n'.join(head) + '\nامروز سهمی بیش از ۱۰٪ رشد نکرد.'})
    if track_msg:
        for cid in chat_ids:
            for part in S.chunks(track_msg.split('\n')):
                ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'parse_mode': 'HTML', 'text': part})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
