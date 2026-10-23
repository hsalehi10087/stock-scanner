"""سهم‌هایی که سود خالص فصلی‌شان نسبت به همان فصل سال قبل بیش از ۱۰٪ رشد کرده (منبع: SEC XBRL Frames).

منابع (بدون کلید): data.sec.gov/api/xbrl/frames و sec.gov/files/company_tickers.json
قانون: سود فصل آخرِ گزارش‌شده > سود همان فصل سال قبل × ۱.۱ و سود قبلی مثبت باشد.
خروجی: جدول تصویری + خلاصه به تلگرام، و فایل تاریخچه‌ی CSV در data/fundamentals/YYYY-MM-DD.csv
"""
import datetime as dt
import os
import re
import sys
import tempfile
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'market_summary'))
import summary as S  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signal_tracker as T  # noqa: E402
import quality as Q  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_DIR = os.path.join(ROOT, 'data', 'fundamentals')
THRESHOLD = 10.0
MIN_PREV_USD = 1_000_000  # سود فصل قبل حداقل ۱ میلیون دلار؛ وگرنه درصد بی‌معناست
EXCLUDE = re.compile(r'acquisition|\bspac\b|\betf\b|\btrust\b|\bfund\b|\bblank check\b', re.I)
UA = {'User-Agent': 'stock-scanner-research mahdi.salehi.sichani@gmail.com'}


DIAG = []


def get_json(url):
    r = requests.get(url, headers=UA, timeout=60)
    DIAG.append(f'{r.status_code} {url[-60:]} len={len(r.text)}')
    r.raise_for_status()
    return r.json()


def cik_map():
    js = get_json('https://www.sec.gov/files/company_tickers.json')
    return {str(v['cik_str']).zfill(10): (v['ticker'], v['title'])
            for v in js.values() if re.fullmatch(r'[A-Z]{1,5}', v.get('ticker', ''))}


def frame(period):
    try:
        js = get_json(f'https://data.sec.gov/api/xbrl/frames/us-gaap/NetIncomeLoss/USD/{period}.json')
    except Exception as e:
        DIAG.append(f'ERR {period}: {str(e)[:200]}')
        return None
    return {str(d['cik']).zfill(10): float(d['val']) for d in js.get('data', [])}


def latest_quarter(today):
    """آخرین فصل تقویمی که داده‌ی آن کامل‌تر از حد معقول است."""
    for back in range(0, 4):
        q_total = (today.month - 1) // 3 + 1 - back
        y = today.year + (q_total - 1) // 4
        q = (q_total - 1) % 4 + 1
        period = f'CY{y}Q{q}'
        data = frame(period)
        time.sleep(0.2)
        if data and len(data) > 500:
            return period, y, q
    return None, None, None


def write_diag(extra=''):
    os.makedirs(HIST_DIR, exist_ok=True)
    with open(os.path.join(HIST_DIR, 'diagnostics.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(DIAG[-60:]) + '\n' + extra)


def main():
    try:
        return _main()
    finally:
        write_diag()


def _main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1

    today = dt.date.today()
    period, y, q = latest_quarter(today)
    if not period:
        print('❌ داده‌ی فصلی SEC پیدا نشد', file=sys.stderr)
        return 2
    prev_period = f'CY{y - 1}Q{q}'
    cur = frame(period)
    time.sleep(0.2)
    prev = frame(prev_period)
    tickers = cik_map()

    rows, checked = [], 0
    for cik, cur_val in cur.items():
        if cik not in tickers or cik not in prev:
            continue
        checked += 1
        prev_val = prev[cik]
        if prev_val < MIN_PREV_USD or cur_val <= prev_val:
            continue
        growth = (cur_val - prev_val) / prev_val * 100
        if growth > THRESHOLD:
            t, title = tickers[cik]
            if EXCLUDE.search(title):
                continue
            rows.append({'ticker': t, 'name': title, 'cur_ni_musd': cur_val / 1e6,
                         'prev_ni_musd': prev_val / 1e6, 'growth': growth, 'period': period})
    rows.sort(key=lambda r: -r['growth'])
    Q.annotate(rows, 'us', limit=60)

    os.makedirs(HIST_DIR, exist_ok=True)
    stamp = today.isoformat()
    pd.DataFrame(rows).to_csv(os.path.join(HIST_DIR, f'{stamp}.csv'), index=False, encoding='utf-8')

    # پیگیری: چند فصل سیگنال شده و بازده از اولین سیگنال
    track_msg = ''
    try:
        state = T.load('fundamentals')
        if state is None:
            state = T.bootstrap('fundamentals', HIST_DIR, event_col='period')
        cur_px = T.last_prices(set(state) | {r['ticker'] for r in rows})
        for r in rows:
            T.add(state, r['ticker'], stamp, r['period'], cur_px.get(r['ticker']),
                  {'qs': r.get('qs'), 'qs_flags': r.get('qs_flags')} if r.get('qs') is not None else None)
        T.save('fundamentals', state)
        trk = {x['ticker']: x for x in T.returns(state, cur_px)}
        for r in rows:
            r['count'] = trk.get(r['ticker'], {}).get('count', 1)
            r['ret'] = trk.get(r['ticker'], {}).get('ret', 0.0)
        since = min((v['first_date'] for v in state.values()), default=stamp)
        track_msg = T.summary_text('رشد سود بیش از ۱۰٪', list(trk.values()), since, 'فصل')
        track_msg = '\n'.join([Q.best_line(rows), Q.LEGEND, '', track_msg])
        DIAG.append(f'tracker: {len(state)} tracked, {len(trk)} priced')
    except Exception as e:
        DIAG.append(f'tracker error: {e!r}')

    head = [f'<b>📈 سهام آمریکا با رشد بیش از ۱۰٪ سود خالص</b> — {period}',
            f'<i>{len(rows)} شرکت از {checked} شرکت با داده‌ی مقایسه‌پذیر ({period} در برابر {prev_period})</i>',
            '<i>سود خالص فصل آخر گزارش‌شده نسبت به همان فصل سال قبل</i>']
    if not rows:
        ok = True
        for cid in chat_ids:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'parse_mode': 'HTML',
                                                            'text': '\n'.join(head) + '\nشرکتی با رشد بیش از ۱۰٪ نبود.'})
        return 0 if ok else 2

    png = os.path.join(tempfile.mkdtemp(), 'fund_growth.png')
    render_png(rows[:25], png)
    more = '\nفهرست کامل در تاریخچه‌ی ریپو (data/fundamentals) ثبت شد.' if len(rows) > 25 else ''
    ok = True
    for cid in chat_ids:
        with open(png, 'rb') as f:
            ok &= S.tg_post(token, cid, 'sendPhoto', data={'chat_id': cid, 'caption': '\n'.join(head) + more,
                                                          'parse_mode': 'HTML'}, files={'photo': f})
    if track_msg:
        for cid in chat_ids:
            for part in S.chunks(track_msg.split('\n')):
                ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'parse_mode': 'HTML', 'text': part})
    return 0 if ok else 2


def render_png(rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cells = [[r['ticker'], r['name'].split(' Common')[0][:28], f"{r['prev_ni_musd']:,.1f}",
              f"{r['cur_ni_musd']:,.1f}", f"+{r['growth']:.1f}%", f"{int(r.get('count', 1))}Q",
              f"{float(r.get('ret', 0)):+.1f}%", f"{r['qs']}/5" if r.get('qs') is not None else '-'] for r in rows]
    heads = ['TICKER', 'COMPANY', 'PREV Q (M$)', 'LATEST Q (M$)', 'GROWTH', 'SIGNALS', 'SINCE 1ST', 'QUALITY']
    fig, ax = plt.subplots(figsize=(13.5, 0.45 * (len(cells) + 1) + 0.4))
    ax.axis('off')
    t = ax.table(cellText=cells, colLabels=heads, loc='center', cellLoc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(10)
    t.scale(1, 1.5)
    widths = {0: 0.09, 1: 0.27, 2: 0.12, 3: 0.13, 4: 0.12, 5: 0.09, 6: 0.1, 7: 0.09}
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
            if j == 4:
                txt.set_color('#15803d')
            if j == 6:
                txt.set_color('#15803d' if not txt.get_text().startswith('-') else '#b91c1c')
    fig.savefig(path, dpi=160, bbox_inches='tight', facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    sys.exit(main())
