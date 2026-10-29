"""اسکن ساعتی بازار آمریکا در ساعت‌های باز بودن بازار: هشدار تکنیکال + برچسب بنیادی.

هر اجرا (هر ساعت، فقط بین ۹:۴۵ تا ۱۶:۱۰ نیویورک در روزهای کاری):
  ۱) نمادها: universe_us شکارچی الگو + watchlist + سبد AI + انتخاب‌های AI + سهم‌های metrics.json
  ۲) کندل روزانه‌ی ~۱۸ ماه اخیر به‌اضافه‌ی کندل نیمه‌کاره‌ی امروز (Alpaca SIP با ۱۶ دقیقه تأخیر؛ اگر نشد Yahoo)
  ۳) سیگنال‌ها:
       🟢 شکست سقف ۵۲ هفته با حجم   🟢 شکست سقف ۲۰ روزه در روند صعودی با حجم   🚀 جهش قیمت با حجم
       🔴 هشدار ریسک (فقط برای سهم‌های زیر نظر): افت شدید یا شکست میانگین ۵۰ روزه به پایین
  ۴) برچسب بنیادی: رشد فروش و سود (fundamentals.csv)، امتیاز AI و احتمال شکارچی الگو
  ۵) فقط هشدارهای تازه‌ی همان روز به تلگرام می‌رود (data/intraday/state.json تکرار را می‌گیرد)
هیچ سفارشی ثبت نمی‌شود. این هشدار است، نه توصیه‌ی خرید.

اجرا: python3 market_intel/intraday_scan.py [--force]   (--force: بدون چک ساعت بازار، برای آزمایش)
"""
import csv
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'data', 'intraday')
STATE = os.path.join(OUT_DIR, 'state.json')
NY, TEH = ZoneInfo('America/New_York'), ZoneInfo('Asia/Tehran')
DATA = 'https://data.alpaca.markets'

MIN_PRICE = 5.0
MIN_DOLLAR_VOL = 5e6        # میانگین ارزش معاملات روزانه‌ی ۲۰ روزه
MAX_LINES = 12              # حداکثر هشدار مثبت در هر پیام


# ---------------------------------------------------------------- کمکی
def fa(x):
    return str(x).translate(str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫'))


def pct(v):
    return fa(f'{v:+.1f}٪').replace('+', '▲').replace('-', '▼')


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def tg(text):
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    if not tok or not chats:
        print('(telegram skipped)\n' + text)
        return True
    ok = True
    for c in chats:
        r = requests.post(f'https://api.telegram.org/bot{tok}/sendMessage',
                          data={'chat_id': c, 'text': text, 'disable_web_page_preview': 'true'}, timeout=20)
        print('telegram', c[-4:], r.status_code)
        ok = ok and r.ok
    return ok


# ---------------------------------------------------------------- نمادها و داده‌ی بنیادی
def universe():
    syms, watched = set(), set()
    syms |= set(load_json(os.path.join(ROOT, 'data', 'pattern_hunter', 'universe_us.json'), {}))
    for fn in ('watchlist.txt', 'extra_tickers.txt'):
        p = os.path.join(ROOT, fn)
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                parts = [x.strip() for x in line.split(',')]
                if len(parts) >= 2 and parts[1].upper() == 'US' and not parts[0].startswith('#'):
                    syms.add(parts[0].upper())
                    if fn == 'watchlist.txt':
                        watched.add(parts[0].upper())
    p = os.path.join(ROOT, 'ai_basket.csv')
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8')):
            watched.add(r['ticker'].upper())
    for pk in load_json(os.path.join(ROOT, 'data', 'ai_stocks', 'latest.json'), {}).get('picks', []):
        watched.add(pk['ticker'].upper())
    syms |= set(load_json(os.path.join(ROOT, 'data', 'ai_stocks', 'metrics.json'), {}).get('stocks', {}))
    syms |= watched
    syms = {s for s in syms if s and s.replace('.', '').replace('-', '').isalpha()}
    return sorted(syms), watched


def fundamentals():
    info = {}
    p = os.path.join(ROOT, 'fundamentals.csv')
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if (r.get('market') or 'US').upper() != 'US':
                continue
            try:
                info[r['ticker'].upper()] = {'rev': float(r['rev_growth']) if r['rev_growth'] else None,
                                             'profit': float(r['profit_growth']) if r['profit_growth'] else None}
            except ValueError:
                pass
    for t, m in load_json(os.path.join(ROOT, 'data', 'ai_stocks', 'metrics.json'), {}).get('stocks', {}).items():
        d = info.setdefault(t.upper(), {})
        if m.get('revenue_growth_pct') is not None and d.get('rev') is None:
            d['rev'] = m['revenue_growth_pct']
        d['ai'] = m.get('quant_score')
    us = load_json(os.path.join(ROOT, 'data', 'pattern_hunter', 'today.json'), {}).get('markets', {}).get('us', {})
    for pk in us.get('picks', []):
        info.setdefault(pk['ticker'].upper(), {})['pattern'] = pk.get('prob')
    return info


# ---------------------------------------------------------------- قیمت
def alpaca_headers():
    return {'APCA-API-KEY-ID': os.getenv('ALPACA_KEY', ''), 'APCA-API-SECRET-KEY': os.getenv('ALPACA_SECRET', '')}


def bars_alpaca(symbols, start):
    h = alpaca_headers()
    if not h['APCA-API-KEY-ID']:
        raise RuntimeError('no Alpaca keys')
    end = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=16)).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = {}
    for feed in ('sip', 'iex'):
        try:
            for i in range(0, len(symbols), 200):
                part = symbols[i:i + 200]
                token = None
                while True:
                    p = {'symbols': ','.join(part), 'timeframe': '1Day', 'start': start, 'end': end,
                         'adjustment': 'split', 'feed': feed, 'limit': 10000}
                    if token:
                        p['page_token'] = token
                    r = requests.get(f'{DATA}/v2/stocks/bars', params=p, headers=h, timeout=60)
                    r.raise_for_status()
                    j = r.json()
                    for s, rows in (j.get('bars') or {}).items():
                        out.setdefault(s, []).extend(rows)
                    token = j.get('next_page_token')
                    if not token:
                        break
            return {s: _df(rows) for s, rows in out.items()}, f'Alpaca {feed.upper()}'
        except requests.HTTPError as e:
            print(f'Alpaca feed={feed}: {e}', file=sys.stderr)
            out = {}
    raise RuntimeError('Alpaca failed')


def _df(rows):
    df = pd.DataFrame(rows).rename(columns={'t': 'date', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert(NY).dt.date
    return df.set_index('date')[['open', 'high', 'low', 'close', 'volume']].astype(float).sort_index()


def bars_yahoo(symbols):
    import yfinance as yf
    out = {}
    for i in range(0, len(symbols), 200):
        part = symbols[i:i + 200]
        try:
            df = yf.download(part, period='18mo', interval='1d', group_by='ticker', threads=True,
                             progress=False, auto_adjust=False)
        except Exception as e:
            print(f'Yahoo batch {i}: {e}', file=sys.stderr)
            continue
        for s in part:
            try:
                d = df[s][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
                d.columns = ['open', 'high', 'low', 'close', 'volume']
                d.index = [x.date() for x in pd.to_datetime(d.index)]
                if len(d):
                    out[s] = d.astype(float)
            except Exception:
                pass
    return out, 'Yahoo'


# ---------------------------------------------------------------- سیگنال
def signals(sym, df, today, frac, watched):
    """کندل آخر باید مال امروز باشد. خروجی: فهرست (کد سیگنال، داده)."""
    if df is None or len(df) < 60 or df.index[-1] != today:
        return []
    hist, cur = df.iloc[:-1], df.iloc[-1]
    c, h, l, v = cur['close'], cur['high'], cur['low'], cur['volume']
    prev = hist['close'].iloc[-1]
    avg_vol = hist['volume'].iloc[-20:].mean()
    if c < MIN_PRICE or avg_vol <= 0 or (hist['close'].iloc[-20:] * hist['volume'].iloc[-20:]).mean() < MIN_DOLLAR_VOL:
        return []
    chg = (c / prev - 1) * 100
    rvol = v / max(frac, 0.15) / avg_vol            # حجم پیش‌بینی‌شده‌ی کل روز نسبت به میانگین ۲۰ روزه
    ma50 = hist['close'].iloc[-50:].mean()
    ma200 = hist['close'].iloc[-200:].mean() if len(hist) >= 200 else None
    near_hi = (c - l) / (h - l) if h > l else 1.0   # بسته شدن نزدیک سقف روز = خرید جدی، نه فروش در اوج
    d = {'price': c, 'chg': chg, 'rvol': rvol}
    out = []
    hi52 = hist['high'].iloc[-252:].max()
    hi20 = hist['high'].iloc[-20:].max()
    if c > hi52 and rvol >= 1.5 and near_hi >= 0.6 and c > ma50:
        out.append(('hi52', d))
    elif c > hi20 and rvol >= 2 and near_hi >= 0.6 and c > ma50 and ma200 and ma50 > ma200:
        out.append(('hi20', d))
    if chg >= 6 and rvol >= 2 and near_hi >= 0.5:
        out.append(('surge', d))
    if sym in watched:
        if chg <= -6:
            out.append(('drop', d))
        elif prev >= ma50 > c:
            out.append(('ma50', dict(d, ma50=ma50)))
    return out


LABELS = {'hi52': '🟢 شکست سقف ۵۲ هفته با حجم بالا',
          'hi20': '🟢 شکست سقف ۲۰ روزه در روند صعودی',
          'surge': '🚀 جهش قیمت با حجم بالا',
          'drop': '🔴 افت شدید (سهم زیر نظر)',
          'ma50': '🔴 شکست میانگین ۵۰ روزه به پایین (سهم زیر نظر)'}


def fund_tag(f):
    if not f:
        return '', 0
    bits, score = [], 0
    if f.get('rev') is not None:
        bits.append(f'فروش {pct(f["rev"])}')
        score += f['rev'] >= 20
    if f.get('profit') is not None:
        bits.append(f'سود {pct(f["profit"])}')
        score += f['profit'] > 0
    if f.get('pattern'):
        bits.append(f'الگو {fa(round(f["pattern"] * 100))}٪')
        score += 1
    if f.get('ai') is not None:
        bits.append(f'AI {fa(round(f["ai"], 1))}')
    star = ' ⭐' if score >= 2 else ''
    return (' | ' + '، '.join(bits) + star) if bits else '', score


def main():
    force = '--force' in sys.argv
    now = dt.datetime.now(NY)
    today = now.date()
    mins = (now.hour - 9) * 60 + now.minute - 30
    if not force and (now.weekday() >= 5 or not (15 <= mins <= 400)):
        print(f'market closed ({now:%a %H:%M} NY) — skip')
        return
    frac = min(max(mins, 1) / 390, 1.0)

    syms, watched = universe()
    finfo = fundamentals()
    start = (now - dt.timedelta(days=400)).strftime('%Y-%m-%dT00:00:00Z')
    try:
        data, src = bars_alpaca(syms, start)
    except Exception as e:
        print(f'Alpaca unavailable ({e}); falling back to Yahoo', file=sys.stderr)
        data, src = bars_yahoo(syms)
    fresh = sum(1 for d in data.values() if len(d) and d.index[-1] == today)
    print(f'{src}: {len(data)}/{len(syms)} symbols, {fresh} with today bar')
    if fresh == 0:
        print('no bars for today (holiday or data delay) — skip')
        return

    state = load_json(STATE, {})
    sent = state.get(str(today), {})
    new = []
    for s in syms:
        for code, d in signals(s, data.get(s), today, frac, watched):
            if code in sent.get(s, []):
                continue
            new.append((code, s, d))
    if not new:
        print('no new signals')
        return

    groups = {}
    for code, s, d in new:
        tag, score = fund_tag(finfo.get(s))
        groups.setdefault(code, []).append((score, d['rvol'], s, d, tag))
    lines_left = MAX_LINES
    t_teh = dt.datetime.now(TEH)
    msg = [f'⚡ اسکن ساعتی بازار آمریکا — {fa(now.strftime("%H:%M"))} نیویورک ({fa(t_teh.strftime("%H:%M"))} تهران)',
           f'{fa(fresh)} سهم بررسی شد؛ فقط هشدارهای تازه‌ی امروز.', '']
    sent_now = []
    for code in ('hi52', 'hi20', 'surge', 'drop', 'ma50'):
        items = sorted(groups.get(code, []), key=lambda x: (-x[0], -x[1]))
        if not items:
            continue
        if code in ('hi52', 'hi20', 'surge'):
            items = items[:max(lines_left, 0)]
            lines_left -= len(items)
        if not items:
            continue
        msg.append(LABELS[code])
        for score, rvol, s, d, tag in items:
            msg.append(f'{s} {fa(round(d["price"], 2))}$ {pct(d["chg"])} | حجم {fa(round(rvol, 1))} برابر{tag}')
            sent_now.append((s, code))
        msg.append('')
    skipped = len(new) - len(sent_now)
    if skipped > 0:
        msg.append(f'(+{fa(skipped)} هشدار دیگر با اولویت کمتر)')
    msg.append('⭐ = رشد فروش/سود یا تأیید شکارچی الگو. حجم = حجم پیش‌بینی‌شده‌ی امروز نسبت به میانگین ۲۰ روزه.')
    msg.append('هشدار است، نه توصیه‌ی خرید. داده با حدود ۱۵ دقیقه تأخیر.')

    if sent_now and tg('\n'.join(msg)):
        for s, code in sent_now:
            sent.setdefault(s, []).append(code)
        state = {str(today): sent}                    # فقط روز جاری نگه داشته می‌شود
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(STATE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=0)
        with open(os.path.join(OUT_DIR, f'{today}.jsonl'), 'a', encoding='utf-8') as f:
            for code, s, d in new:
                if (s, code) in sent_now:
                    f.write(json.dumps({'time': now.strftime('%H:%M'), 'ticker': s, 'signal': code,
                                        'price': round(d['price'], 2), 'chg': round(d['chg'], 2),
                                        'rvol': round(d['rvol'], 2), 'src': src}) + '\n')


if __name__ == '__main__':
    main()
