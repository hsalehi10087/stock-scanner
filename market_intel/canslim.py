"""CAN SLIM روزانه برای بورس‌های آمریکا، ژاپن، چین و تایوان + فهرست پیگیری و هشدار شروع رشد.

معیارها (روش ویلیام اونیل، با داده‌ی رایگان Yahoo):
  C  سود هر سهم (EPS) فصل آخر نسبت به همان فصل سال قبل ≥ ۲۵٪
  A  رشد EPS سالانه‌ی آخر ≥ ۲۵٪ و سال قبل از آن هم رشد مثبت
  N  قیمت حداکثر ۱۵٪ زیر سقف ۵۲ هفته
  S  حجم خرید بیشتر از فروش در ۵۰ روز اخیر (نسبت حجم روزهای مثبت به منفی ≥ ۱)
  L  قدرت نسبی (RS) در ۲۰٪ برتر همان بازار
  I  مالکیت نهادی ≥ ۲۰٪ (فقط وقتی داده موجود است؛ برای آسیا معمولاً نیست)
  M  روند شاخص بازار (بالای میانگین ۵۰ و ۲۰۰ روزه) — فقط گزارش می‌شود
  به‌علاوه: قیمت > میانگین ۵۰ روزه > میانگین ۲۰۰ روزه (روند صعودی)

هشدار «شروع رشد»: بسته‌شدن بالاتر از سقف ۳۰ روز قبل با حجم ≥ ۱.۴ برابر میانگین ۵۰ روزه.
هشدار حد ضرر: ۸٪ زیر قیمت شکست.

فایل‌ها (data/canslim):
  YYYY-MM-DD.csv   سهم‌های واجد شرایط همان روز با جزئیات معیارها
  watchlist.csv    فهرست پیگیری: قیمت هنگام ورود، سقف مقاومت، وضعیت
  alerts.csv       تاریخچه‌ی هشدارها
  last_message.txt متن آخرین گزارش، diagnostics.txt تشخیص
"""
import datetime as dt
import html
import os
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'market_summary'))
import cn_growth  # noqa: E402
import gainers  # noqa: E402
import jp_growth  # noqa: E402
import summary as S  # noqa: E402
import tw_growth  # noqa: E402
from report import fa  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'data', 'canslim')

MARKETS = {
    'US': {'flag': '🇺🇸', 'index': '^GSPC', 'min_price': 10.0, 'cur': '$'},
    'JP': {'flag': '🇯🇵', 'index': '^N225', 'min_price': 300.0, 'cur': '¥'},
    'CN': {'flag': '🇨🇳', 'index': '000001.SS', 'min_price': 5.0, 'cur': '¥'},
    'TW': {'flag': '🇹🇼', 'index': '^TWII', 'min_price': 20.0, 'cur': 'NT$'},
}
MIN_AVG_VOL = 100_000
C_TH = 25.0
A_TH = 25.0
RS_MIN = 80.0
NEAR_HIGH = 0.85
BREAKOUT_VOL = 1.4
BASE_DAYS = 30
STOP = 0.92
INST_MIN = 0.20
DIAG = []
WATCH_COLS = ['market', 'ticker', 'name', 'added', 'price_at_add', 'pivot', 'status',
              'breakout_date', 'breakout_price', 'last_price', 'last_date', 'change_since_add']


# ---------- فهرست سهام (با نسخه‌ی ذخیره‌شده در صورت خطا) ----------
def cached(name, fn, extra=()):
    path = os.path.join(OUT, f'universe_{name}.csv')
    try:
        d = fn()
        if len(d) > 300:
            os.makedirs(OUT, exist_ok=True)
            pd.DataFrame({'ticker': list(d), 'name': list(d.values())}).to_csv(path, index=False, encoding='utf-8')
        DIAG.append(f'universe {name}: {len(d)} (live)')
        return d
    except Exception as e:
        DIAG.append(f'universe {name}: live failed ({str(e)[:80]})')
    for p in (path, *extra):
        if os.path.exists(p):
            df = pd.read_csv(p, dtype=str)
            DIAG.append(f'universe {name}: {len(df)} (cache {os.path.basename(p)})')
            return dict(zip(df['ticker'], df['name']))
    return {}


def universe(m):
    if m == 'US':
        return cached('us', gainers.universe)
    if m == 'JP':
        return cached('jp', jp_growth.tse_list)
    if m == 'CN':
        d = cached('sse', cn_growth.sse_list, (os.path.join(ROOT, 'data', 'cn_gainers', 'universe_sse.csv'),))
        d.update(cached('szse', cn_growth.szse_list, (os.path.join(ROOT, 'data', 'cn_gainers', 'universe_szse.csv'),)))
        return d
    if m == 'TW':
        d = cached('twse', tw_growth.twse_list, (os.path.join(ROOT, 'data', 'tw_gainers', 'universe_twse.csv'),))
        d.update(cached('tpex', tw_growth.tpex_list, (os.path.join(ROOT, 'data', 'tw_gainers', 'universe_tpex.csv'),)))
        return d
    return {}


# ---------- آمار قیمت یک‌ساله ----------
def _stats(c, v):
    c = c.dropna()
    if len(c) < 130:
        return None
    v = v.reindex(c.index).fillna(0)

    def ret(n):
        n = min(n, len(c) - 1)
        return float(c.iloc[-1] / c.iloc[-n - 1] - 1)

    diff = c.diff()
    v50, d50 = v.tail(50), diff.tail(50)
    upv, dnv = float(v50[d50 > 0].sum()), float(v50[d50 < 0].sum())
    return {
        'price': float(c.iloc[-1]),
        'r3': ret(63), 'r6': ret(126), 'r9': ret(189), 'r12': ret(251),
        'ma50': float(c.tail(50).mean()),
        'ma200': float(c.tail(200).mean()),
        'hi52': float(c.max()),
        'av50': float(v.iloc[-51:-1].mean()),
        'lastv': float(v.iloc[-1]),
        'base_hi': float(c.iloc[-BASE_DAYS - 1:-1].max()),
        'ud': upv / dnv if dnv > 0 else 9.9,
        'date': str(c.index[-1].date()),
    }


def price_stats(symbols, chunk=150):
    out = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        try:
            df = yf.download(part, period='1y', interval='1d', group_by='ticker',
                             threads=True, progress=False, auto_adjust=False)
        except Exception as e:
            DIAG.append(f'batch {i} failed: {str(e)[:80]}')
            continue
        for s in part:
            try:
                sub = df[s] if isinstance(df.columns, pd.MultiIndex) else df
                st = _stats(sub['Close'], sub['Volume'])
                if st:
                    out[s] = st
            except Exception:
                continue
    return out


def market_direction(index_sym):
    try:
        c = yf.download(index_sym, period='1y', interval='1d', progress=False, auto_adjust=False)['Close']
        c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
        c = c.dropna()
        last, ma50, ma200 = float(c.iloc[-1]), float(c.tail(50).mean()), float(c.tail(200).mean())
        if last > ma50 and last > ma200:
            return 'up', 'روند صعودی ✅'
        if last > ma200:
            return 'pressure', 'تحت فشار ⚠️'
        return 'down', 'اصلاح/نزولی ❌'
    except Exception as e:
        DIAG.append(f'M {index_sym}: {str(e)[:80]}')
        return 'unknown', 'نامشخص'


def add_rs(stats):
    if not stats:
        return
    keys = list(stats)
    w = np.array([0.4 * stats[k]['r3'] + 0.2 * stats[k]['r6'] + 0.2 * stats[k]['r9'] + 0.2 * stats[k]['r12']
                  for k in keys])
    ranks = pd.Series(w).rank(pct=True).values * 100
    for k, r in zip(keys, ranks):
        stats[k]['rs'] = float(r)


# ---------- صورت‌های مالی (C, A, I) ----------
def _eps_row(df):
    if df is None or df.empty:
        return None
    for lab in ('Diluted EPS', 'Basic EPS', 'Net Income', 'Net Income Common Stockholders'):
        if lab in df.index:
            row = df.loc[lab].dropna()
            if len(row):
                return row.sort_index(ascending=False)
    return None


def fundamentals(sym, market):
    res = {'C': False, 'A': False, 'I': None, 'c_growth': None, 'a_growth': None, 'inst': None,
           'why_c': 'no_quarterly', 'why_a': 'no_annual', 'nq': 0}
    t = yf.Ticker(sym)
    try:
        row = _eps_row(t.quarterly_income_stmt)
        res['nq'] = 0 if row is None else len(row)
        if row is not None and len(row) >= 5:
            res['why_c'] = 'no_prev_year_q'
            cur_d, cur = row.index[0], float(row.iloc[0])
            target = cur_d - pd.Timedelta(days=365)
            near = [(abs((d - target).days), float(v)) for d, v in row.items() if abs((d - target).days) <= 25]
            if near:
                prev = min(near)[1]
                if prev > 0:
                    g = (cur - prev) / prev * 100
                    res['c_growth'], res['C'] = g, g >= C_TH
                    res['why_c'] = 'ok' if res['C'] else 'c_low'
                else:
                    res['why_c'] = 'prev_not_positive'
        elif row is not None:
            res['why_c'] = f'only_{len(row)}_quarters'
    except Exception as e:
        DIAG.append(f'C {sym}: {str(e)[:60]}')
    try:
        row = _eps_row(t.income_stmt)
        if row is not None and len(row) >= 3:
            y0, y1, y2 = float(row.iloc[0]), float(row.iloc[1]), float(row.iloc[2])
            res['why_a'] = 'prev_not_positive'
            if y1 > 0 and y2 > 0:
                g1 = (y0 - y1) / y1 * 100
                res['a_growth'], res['A'] = g1, g1 >= A_TH and y1 > y2
                res['why_a'] = 'ok' if res['A'] else 'a_low'
        elif row is not None:
            res['why_a'] = f'only_{len(row)}_years'
    except Exception as e:
        DIAG.append(f'A {sym}: {str(e)[:60]}')
    if market == 'US':
        try:
            hp = t.get_info().get('heldPercentInstitutions')
            if hp is not None:
                res['inst'], res['I'] = float(hp), float(hp) >= INST_MIN
        except Exception:
            pass
    return res


# ---------- فهرست پیگیری و هشدارها ----------
def load_watch():
    p = os.path.join(OUT, 'watchlist.csv')
    if os.path.exists(p):
        df = pd.read_csv(p, dtype={'ticker': str})
        for c in WATCH_COLS:
            if c not in df.columns:
                df[c] = None
        return df[WATCH_COLS]
    return pd.DataFrame(columns=WATCH_COLS)


def append_alerts(rows):
    if not rows:
        return
    p = os.path.join(OUT, 'alerts.csv')
    df = pd.DataFrame(rows)
    df.to_csv(p, mode='a', header=not os.path.exists(p), index=False, encoding='utf-8')


def money(cur, x):
    return f'{cur}{x:,.2f}'


def main():
    markets = [m.strip().upper() for m in os.getenv('MARKETS', 'US,JP,CN,TW').split(',') if m.strip()]
    dry = os.getenv('DRY_RUN', 'false').lower() == 'true'
    today = dt.date.today().isoformat()
    os.makedirs(OUT, exist_ok=True)

    all_stats, names_all, mdir, qualified = {}, {}, {}, []
    for m in markets:
        cfg = MARKETS[m]
        t0 = time.time()
        names = universe(m)
        stats = price_stats(sorted(names))
        add_rs(stats)
        mdir[m] = market_direction(cfg['index'])
        cands = [s for s, st in stats.items()
                 if st['price'] >= cfg['min_price'] and st['av50'] >= MIN_AVG_VOL
                 and st.get('rs', 0) >= RS_MIN and st['price'] >= NEAR_HIGH * st['hi52']
                 and st['price'] > st['ma50'] > st['ma200'] and st['ud'] >= 1.0]
        n_ok = 0
        from collections import Counter
        why_c, why_a, nq = Counter(), Counter(), Counter()
        for s in cands:
            f = fundamentals(s, m)
            why_c[f['why_c']] += 1
            why_a[f['why_a']] += 1
            nq[f['nq']] += 1
            time.sleep(0.2)
            if f['C'] and f['A'] and f['I'] is not False:
                st = stats[s]
                n_ok += 1
                qualified.append({'market': m, 'ticker': s, 'name': names.get(s, ''), 'price': st['price'],
                                  'c_growth': f['c_growth'], 'a_growth': f['a_growth'], 'rs': st['rs'],
                                  'pct_of_high': st['price'] / st['hi52'] * 100, 'ud': st['ud'],
                                  'inst': f['inst'], 'pivot': st['base_hi'], 'date': st['date']})
        DIAG.append(f'{m}: universe={len(names)} priced={len(stats)} tech_cands={len(cands)} '
                    f'canslim={n_ok} M={mdir[m][0]} ({time.time() - t0:.0f}s)')
        DIAG.append(f'  {m} C reasons: {dict(why_c)}')
        DIAG.append(f'  {m} A reasons: {dict(why_a)}')
        DIAG.append(f'  {m} quarters available: {dict(sorted(nq.items()))}')
        for s, st in stats.items():
            all_stats[(m, s)] = st
        names_all.update({(m, s): n for s, n in names.items()})

    qdf = pd.DataFrame(qualified)
    qdf.to_csv(os.path.join(OUT, f'{today}.csv'), index=False, encoding='utf-8')

    # فهرست پیگیری: افزودن سهم‌های جدید
    watch = load_watch()
    keys = set(zip(watch['market'], watch['ticker']))
    new_rows = []
    for q in qualified:
        if (q['market'], q['ticker']) not in keys:
            new_rows.append({'market': q['market'], 'ticker': q['ticker'], 'name': q['name'], 'added': today,
                             'price_at_add': q['price'], 'pivot': q['pivot'], 'status': 'watch',
                             'breakout_date': None, 'breakout_price': None, 'last_price': q['price'],
                             'last_date': q['date'], 'change_since_add': 0.0})
    if new_rows:
        watch = pd.concat([watch, pd.DataFrame(new_rows)], ignore_index=True)

    # بررسی شکست مقاومت و حد ضرر
    alerts, breakouts, stops = [], [], []
    for i, w in watch.iterrows():
        st = all_stats.get((w['market'], str(w['ticker'])))
        if not st:
            continue
        watch.at[i, 'last_price'] = st['price']
        watch.at[i, 'last_date'] = st['date']
        watch.at[i, 'change_since_add'] = (st['price'] / float(w['price_at_add']) - 1) * 100
        if w['status'] == 'watch':
            watch.at[i, 'pivot'] = st['base_hi']
            vol_ratio = st['lastv'] / st['av50'] if st['av50'] else 0
            if st['price'] > st['base_hi'] and vol_ratio >= BREAKOUT_VOL:
                watch.at[i, 'status'] = 'breakout'
                watch.at[i, 'breakout_date'] = st['date']
                watch.at[i, 'breakout_price'] = st['price']
                rec = {'date': st['date'], 'market': w['market'], 'ticker': w['ticker'], 'name': w['name'],
                       'type': 'breakout', 'price': st['price'], 'pivot': st['base_hi'], 'vol_ratio': vol_ratio,
                       'price_at_add': w['price_at_add']}
                alerts.append(rec)
                breakouts.append(rec)
        elif w['status'] == 'breakout' and pd.notna(w['breakout_price']):
            if st['price'] < STOP * float(w['breakout_price']):
                watch.at[i, 'status'] = 'stopped'
                rec = {'date': st['date'], 'market': w['market'], 'ticker': w['ticker'], 'name': w['name'],
                       'type': 'stop', 'price': st['price'], 'pivot': w['breakout_price'], 'vol_ratio': None,
                       'price_at_add': w['price_at_add']}
                alerts.append(rec)
                stops.append(rec)
    if not dry:
        watch.to_csv(os.path.join(OUT, 'watchlist.csv'), index=False, encoding='utf-8')
        append_alerts(alerts)

    # ---------- پیام ----------
    def nm(n):
        import re
        n = str(n)
        n = re.split(r' - | Common| Class [A-Z]| Ordinary| American Depositary', n)[0].strip().rstrip(',')
        return html.escape(fa(n) or n)

    lines = [f'<b>📊 گزارش روزانه CAN SLIM</b> — {today}',
             '<b>جهت بازار (M):</b> ' + ' | '.join(f"{MARKETS[m]['flag']} {mdir[m][1]}" for m in markets), '']
    lines.append('<b>🚨 هشدار شروع رشد</b> <i>(عبور از سقف ۳۰ روزه با حجم بالا)</i>')
    if breakouts:
        for b in breakouts:
            cur = MARKETS[b['market']]['cur']
            lines.append(f"• {MARKETS[b['market']]['flag']} <b>{b['ticker']}</b> ({nm(b['name'])}): "
                         f"{money(cur, b['price'])} | سقف {money(cur, b['pivot'])} | حجم {b['vol_ratio']:.1f}× | "
                         f"قیمت ورود به فهرست {money(cur, float(b['price_at_add']))}")
    else:
        lines.append('امروز هشداری نبود.')
    if stops:
        lines += ['', '<b>⚠️ حد ضرر (۸٪ زیر قیمت شکست)</b>']
        for s in stops:
            cur = MARKETS[s['market']]['cur']
            lines.append(f"• {MARKETS[s['market']]['flag']} <b>{s['ticker']}</b>: {money(cur, s['price'])} "
                         f"(قیمت شکست {money(cur, float(s['pivot']))})")
    lines += ['', f'<b>🆕 سهم‌های جدید با معیار CAN SLIM</b> ({len(new_rows)})']
    q_by = {(q['market'], q['ticker']): q for q in qualified}
    for r in sorted(new_rows, key=lambda r: -q_by[(r['market'], r['ticker'])]['rs'])[:25]:
        q = q_by[(r['market'], r['ticker'])]
        cur = MARKETS[r['market']]['cur']
        lines.append(f"• {MARKETS[r['market']]['flag']} <b>{r['ticker']}</b> ({nm(r['name'])}): "
                     f"{money(cur, r['price_at_add'])} | C +{q['c_growth']:.0f}٪ | A +{q['a_growth']:.0f}٪ | RS {q['rs']:.0f}")
    if not new_rows:
        lines.append('سهم جدیدی اضافه نشد.')
    counts = watch['status'].value_counts().to_dict()
    lines += ['', f"<b>👀 فهرست پیگیری:</b> {counts.get('watch', 0)} در انتظار شکست | "
                  f"{counts.get('breakout', 0)} شکسته | {counts.get('stopped', 0)} حد ضرر خورده",
              '<i>واجد شرایط امروز در هر بازار: ' + ' | '.join(
                  f"{MARKETS[m]['flag']} {int((qdf['market'] == m).sum()) if len(qdf) else 0}" for m in markets) + '</i>',
              '<i>معیارها با داده‌ی Yahoo؛ این گزارش توصیه‌ی خرید نیست.</i>']

    with open(os.path.join(OUT, 'last_message.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    if dry:
        DIAG.append('dry run: message not sent')
        return 0
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    ok = True
    for cid in chat_ids:
        for ch in S.chunks(lines):
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    try:
        code = main()
    except Exception as e:
        import traceback
        DIAG.append('ERROR: ' + traceback.format_exc()[-1500:])
        code = 3
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'diagnostics.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(DIAG) + '\n')
    sys.exit(code)
