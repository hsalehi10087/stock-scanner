"""«پیش‌بینی پلی‌مارکت سهام» — هر روز بازارهای باز پلی‌مارکت درباره‌ی سهام و شاخص‌ها را می‌خواند (فقط خواندن، بدون حساب و معامله).

سیگنال: بازاری که احتمال «بالا رفتن / بسته‌شدن بالای هدف / رسیدن به هدف بالاتر» در آن ۷۰٪ یا بیشتر است و حجمش ≥ ۱۰ هزار دلار.
احتمال = قیمت گزینه‌ی «بله/بالا» در پلی‌مارکت. قیمت سهم = آخرین بسته‌شدن روزانه (Yahoo).
هر سیگنال یک بار در data/polymarket/history.csv ثبت می‌شود؛ هر روز بازده، بیشترین رشد و افت از روز سیگنال،
و بعد از بسته‌شدن بازار پلی‌مارکت نتیجه‌ی نهایی (درست/غلط) حساب می‌شود. پیام از راه گزارش صبحگاهی می‌رود.
"""
import csv
import datetime as dt
import json
import os
import re
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

G = 'https://gamma-api.polymarket.com'
OUT = os.path.join(ROOT, 'data', 'polymarket')
HIST = os.path.join(OUT, 'history.csv')
COLS = ['date', 'id', 'event_slug', 'ticker', 'yahoo', 'kind', 'question', 'prob', 'target', 'price', 'end', 'volume',
        'above_already', 'resolved', 'correct']
TAGS = ['stocks', 'equities', 'indicies', 'sp-500', 'nasdaq', 'finance']
MIN_PROB, MIN_VOL, TRACK_DAYS, MAX_SHOW = 0.70, 10000, 60, 15
INDEX = {'SPX': '^GSPC', 'NDX': '^NDX', 'DJIA': '^DJI', 'DJI': '^DJI', 'NIK': '^N225', 'NKY': '^N225', 'RUT': '^RUT',
         'DAX': '^GDAXI', 'FTSE': '^FTSE', 'HSI': '^HSI', 'COMP': '^IXIC', 'IXIC': '^IXIC', 'VIX': None}
FA = str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫')
NUM = r'\$?([\d,]+(?:\.\d+)?)\s*([kK])?'


def fa(x):
    return str(x).translate(FA)


def num(a, k=None):
    return float(a.replace(',', '')) * (1000 if k else 1)


def parse(q):
    """سؤال بازار → (نماد، نوع، هدف، متن فارسی) یا None. فقط صورت‌بندی‌های «رو به بالا»."""
    m = re.search(r'\(([A-Z][A-Z.\-]{0,6})\)', q)
    if not m:
        return None
    t = m.group(1)
    when = re.search(r'\b(?:on|by|in|end of)\s+([A-Z][a-z]+(?:\s+\d{1,2})?(?:,?\s+\d{4})?|\d{4})', q)
    when = when.group(1) if when else ''
    if re.search(r'Up or Down', q, re.I):
        o = 'باز می‌شود' if re.search(r'Opens', q) else 'بسته می‌شود'
        return t, 'updown', None, f'آیا {t} در {when} بالاتر از بسته‌شدن قبلی {o}؟'
    if re.search(r'\(LOW\)|below|under|<\s*\$|less than|dip|drop|fall', q, re.I):
        return None                                           # بازارهای رو به پایین سیگنال رشد نیستند
    if re.search(r'\d\s*[-–]\s*\$?\d', q) or re.search(r'between', q, re.I):
        return None                                           # بازه‌ی قیمتی
    if re.search(r'market cap|earnings|IPO', q, re.I):
        return None
    m2 = (re.search(r'hit\s+' + NUM + r'\s*\(HIGH\)', q) or re.search(r'hit\s+\(HIGH\)\s*' + NUM, q)
          or re.search(r'(?:hit|reach|touch)\s+' + NUM, q, re.I))
    if m2:
        z = num(m2.group(1), m2.group(2))
        return t, 'hit', z, f'آیا {t} تا {when} به {z:,.0f}$ می‌رسد؟'
    m2 = (re.search(r'clos\w*\s+(?:at\s+)?(?:above|over|>)\s*' + NUM, q, re.I)
          or re.search(r'(?:above|over|>)\s*' + NUM, q, re.I))
    if m2:
        z = num(m2.group(1), m2.group(2))
        return t, 'above', z, f'آیا {t} در {when} بالای {z:,.2f}$ بسته می‌شود؟'.replace('.00$', '$')
    return None


def jl(x):
    try:
        return json.loads(x) if isinstance(x, str) else (x or [])
    except Exception:
        return []


def yes_prob(m):
    outs, pr = jl(m.get('outcomes')), jl(m.get('outcomePrices'))
    for i, o in enumerate(outs):
        if str(o).lower() in ('yes', 'up') and i < len(pr):
            try:
                return float(pr[i])
            except Exception:
                return None
    return None


def vol(m):
    try:
        return float(m.get('volumeNum') or m.get('volume') or 0)
    except Exception:
        return 0.0


def fetch_markets(log):
    seen, out = set(), []
    for tag in TAGS:
        off = 0
        while off < 1000:
            try:
                r = requests.get(G + '/events', params={'closed': 'false', 'tag_slug': tag, 'limit': 100, 'offset': off},
                                 timeout=40)
                ev = r.json() if r.ok else []
            except Exception as e:
                log.append(f'{tag}: {e}')
                break
            if not ev:
                break
            for e in ev:
                for m in e.get('markets') or []:
                    if m.get('id') in seen or m.get('closed') or m.get('active') is False:
                        continue
                    seen.add(m.get('id'))
                    m['_event'] = e.get('slug')
                    try:
                        m['_event_vol'] = float(e.get('volume') or 0)
                    except Exception:
                        m['_event_vol'] = 0.0
                    out.append(m)
            off += 100
    return out


def closes(symbols, start):
    """آخرین قیمت‌های پایانی روزانه از Yahoo: {sym: Series}."""
    import yfinance as yf
    res = {}
    for s in symbols:
        try:
            h = yf.Ticker(s).history(start=str(start - dt.timedelta(days=7)), auto_adjust=False)['Close'].dropna()
            if len(h):
                h.index = [d.date() for d in h.index]
                res[s] = h
        except Exception:
            pass
    return res


def load_hist():
    if not os.path.exists(HIST):
        return []
    return list(csv.DictReader(open(HIST, encoding='utf-8')))


def save_hist(rows):
    os.makedirs(OUT, exist_ok=True)
    with open(HIST, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def resolve(rows, log):
    """بازارهای تمام‌شده: نتیجه‌ی نهایی از پلی‌مارکت."""
    today = str(dt.date.today())
    for r in rows:
        if r['resolved'] or (r['end'] or '9999')[:10] > today:
            continue
        try:
            m = requests.get(f"{G}/markets/{r['id']}", timeout=30).json()
        except Exception as e:
            log.append(f"resolve {r['id']}: {e}")
            continue
        p = yes_prob(m)
        if m.get('closed') and p is not None and (p >= 0.99 or p <= 0.01):
            r['resolved'], r['correct'] = today, '1' if p >= 0.99 else '0'


def main():
    today = dt.date.today()
    log = []
    markets = fetch_markets(log)
    hist = load_hist()
    known = {r['id'] for r in hist}
    cands, unparsed = [], []
    for m in markets:
        q = m.get('question') or ''
        p = parse(q)
        if not p:
            if re.search(r'\([A-Z]{1,6}\)', q):
                unparsed.append(q)
            continue
        t, kind, target, q_fa = p
        y = INDEX.get(t, t.replace('.', '-'))
        prob = yes_prob(m)
        if y is None or prob is None:
            continue
        cands.append({'id': str(m.get('id')), 'event_slug': m.get('_event') or '', 'ticker': t, 'yahoo': y, 'kind': kind,
                      'question': q, 'q_fa': q_fa, 'prob': prob, 'target': target, 'end': (m.get('endDate') or '')[:10],
                      'volume': vol(m), 'event_vol': m.get('_event_vol', 0.0)})
    strong = [c for c in cands if c['prob'] >= MIN_PROB and c['volume'] >= MIN_VOL]
    # در هر پله‌کان قیمتی (یک سهم، یک تاریخ، یک نوع) فقط بالاترین هدفِ بالای ۷۰٪ می‌ماند؛ بقیه همان حرف را تکرار می‌کنند
    top = {}
    for c in strong:
        k = (c['ticker'], c['kind'], c['end'])
        if k not in top or (c['target'] or 0) > (top[k]['target'] or 0):
            top[k] = c
    strong = list(top.values())
    hp = [c for c in cands if c['prob'] >= MIN_PROB]
    vstat = {'prob70_total': len(hp), 'vol>=10k': sum(c['volume'] >= 10000 for c in hp),
             'vol>=1k': sum(c['volume'] >= 1000 for c in hp), 'vol>=100': sum(c['volume'] >= 100 for c in hp),
             'event_vol>=10k': sum(c['event_vol'] >= 10000 for c in hp),
             'max_vol': max([c['volume'] for c in hp] or [0]),
             'top': sorted([[c['question'], round(c['prob'], 3), round(c['volume']), round(c['event_vol'])] for c in hp],
                           key=lambda x: -x[2])[:25]}
    low_vol = sum(1 for c in cands if c['prob'] >= MIN_PROB and c['volume'] < MIN_VOL)
    cut = str(today - dt.timedelta(days=TRACK_DAYS))
    track = [r for r in hist if r['date'] >= cut]
    syms = sorted({c['yahoo'] for c in strong} | {r['yahoo'] for r in track})
    start = min([dt.date.fromisoformat(r['date']) for r in track] + [today])
    px = closes(syms, start) if syms else {}
    new = []
    for c in sorted(strong, key=lambda c: -c['volume']):
        s = px.get(c['yahoo'])
        c['price'] = round(float(s.iloc[-1]), 2) if s is not None else None
        c['above_already'] = bool(c['price'] and c['target'] and c['price'] >= c['target'])
        if c['id'] not in known:
            new.append(c)
            hist.append({'date': str(today), 'id': c['id'], 'event_slug': c['event_slug'], 'ticker': c['ticker'],
                         'yahoo': c['yahoo'], 'kind': c['kind'], 'question': c['question'], 'prob': round(c['prob'], 3),
                         'target': c['target'] or '', 'price': c['price'] or '', 'end': c['end'],
                         'volume': round(c['volume']), 'above_already': int(c['above_already']), 'resolved': '',
                         'correct': ''})
    resolve(hist, log)
    if os.getenv('POLY_DRY') != 'true':          # اجرای آزمایشی چیزی در تاریخچه ثبت نمی‌کند
        save_hist(hist)

    # ---- پیگیری
    perf, seen = [], set()
    for r in hist:
        if r['date'] < cut or not r['price'] or (r['ticker'], r['date']) in seen or r['date'] == str(today):
            continue
        s = px.get(r['yahoo'])
        if s is None:
            continue
        after = s[[d > dt.date.fromisoformat(r['date']) for d in s.index]]
        if not len(after):
            continue
        seen.add((r['ticker'], r['date']))
        p0 = float(r['price'])
        perf.append({'ticker': r['ticker'], 'date': r['date'], 'ret': (float(after.iloc[-1]) / p0 - 1) * 100,
                     'max': max(0.0, (float(after.max()) / p0 - 1) * 100),
                     'min': min(0.0, (float(after.min()) / p0 - 1) * 100)})
    done = [r for r in hist if r['resolved']]
    right = sum(r['correct'] == '1' for r in done)

    # ---- پیام
    L = [f"🔮 <b>پیش‌بینی پلی‌مارکت سهام</b> — {fa(len(markets))} بازار باز سهام و شاخص خوانده شد؛ "
         f"{fa(len(cands))} بازار «رو به بالا»، {fa(len(strong))} تا با احتمال ۷۰٪ به بالا و حجم کافی."]
    if not markets:
        L.append('⚠️ امروز داده‌ای از پلی‌مارکت نیامد.' + (f' ({log[0][:80]})' if log else ''))
    if new:
        L.append(f"\n<b>سیگنال‌های تازه ({fa(len(new))}):</b>")
        for i, c in enumerate(new[:MAX_SHOW], 1):
            L.append(f"{fa(i)}. <b>{c['ticker']}</b> — {fa(c['q_fa'])}")
            L.append(f"   احتمال <b>{fa(round(c['prob'] * 100))}٪</b> | پایان {fa(c['end'].replace('-', '/'))} | "
                     f"حجم {fa(f'{c['volume']:,.0f}')}$")
            if c['price'] is None:
                L.append('   قیمت سهم از Yahoo نیامد.')
            elif c['target']:
                gap = (c['target'] / c['price'] - 1) * 100
                L.append(f"   قیمت فعلی {fa(f'{c['price']:,.2f}')} | هدف {fa(f'{c['target']:,.2f}')} | فاصله تا هدف {fa(f'{gap:+.1f}')}٪")
                if c['above_already']:
                    L.append('   ⚠️ احتمال بالا به این دلیل است که سهم همین حالا بالای هدف است، نه پیش‌بینی رشد.')
            else:
                L.append(f"   قیمت فعلی {fa(f'{c['price']:,.2f}')} (هدف: بالاتر از بسته‌شدن قبلی)")
            L.append(f"   <a href=\"https://polymarket.com/event/{c['event_slug']}\">بازار در پلی‌مارکت</a>")
        if len(new) > MAX_SHOW:
            L.append(f"… و {fa(len(new) - MAX_SHOW)} بازار دیگر (در فایل تاریخچه ثبت شد).")
    else:
        L.append('\nامروز بازار تازه‌ای با احتمال ۷۰٪ به بالا نبود.')
    if low_vol:
        L.append(f"<i>{fa(low_vol)} بازار با احتمال بالا کنار گذاشته شد چون حجمش زیر ۱۰ هزار دلار بود.</i>")
    if perf:
        row = lambda x: (f"{x['ticker']} (از {fa(x['date'][5:].replace('-', '/'))}): {fa(f'{x['ret']:+.1f}')}٪ "  # noqa: E731
                         f"(بیشترین رشد {fa(f'{x['max']:+.1f}')}٪، بیشترین افت {fa(f'{x['min']:+.1f}')}٪)")
        best = sorted(perf, key=lambda x: -x['ret'])[:5]
        worst = [x for x in sorted(perf, key=lambda x: x['ret'])[:5] if x['ret'] < 0]
        L.append('\n🏆 <b>بیشترین رشد از روز سیگنال تا امروز</b>')
        L += [f"{fa(i)}. {row(x)}" for i, x in enumerate(best, 1)]
        if worst:
            L.append('⚠️ <b>بیشترین افت از روز سیگنال تا امروز</b>')
            L += [f"{fa(i)}. {row(x)}" for i, x in enumerate(worst, 1)]
    if done:
        pct = right / len(done) * 100
        L.append(f"\n📊 کارنامه: از {fa(len(done))} بازار بسته‌شده با احتمال ۷۰٪ به بالا، {fa(right)} تا درست درآمد ({fa(round(pct))}٪).")
        if pct < 70 and len(done) >= 10:
            L.append('⚠️ این عدد زیر ۷۰٪ است؛ یعنی احتمال‌های پلی‌مارکت در این بازارها بیش از حد خوش‌بینانه بوده‌اند.')
    else:
        L.append('\n📊 کارنامه: هنوز هیچ بازار سیگنال‌شده‌ای بسته نشده است.')
    L.append('<i>احتمال پلی‌مارکت نظر شرط‌بندان است، نه توصیه‌ی خرید.</i>')
    text = '\n'.join(L)
    print(text)
    os.makedirs(OUT, exist_ok=True)
    json.dump({'date': str(today), 'markets': len(markets), 'candidates': len(cands), 'strong': len(strong),
               'new': len(new), 'log': log[:10], 'vstat': vstat, 'unparsed_sample': unparsed[:60],
               'candidate_sample': [[c['question'], round(c['prob'], 3), round(c['volume'])] for c in cands[:80]]},
              open(os.path.join(OUT, 'last_run.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    ok = True
    for cid in [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']:
        for ch in S.chunks(text.split('\n'), limit=3900):
            ok &= S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML',
                                                           'disable_web_page_preview': 'true'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
