"""شکارچی روش — بک‌تست روش‌های قبول‌شده با داده‌ی تاریخی Alpaca (به جای Yahoo).

برای هر روش: داده‌ی روزانه از Alpaca ← همان موتور engine.run_spec ← فرض سرمایه‌ی ۱٬۰۰۰ دلاری ←
یک پیام تلگرام جدا برای هر روش. هیچ سفارشی ثبت نمی‌شود.
اجرا: python3 strategy_hunter/alpaca_test.py <spec_id> [<spec_id> ...]
"""
import datetime as dt
import json
import os
import sys

import pandas as pd
import requests
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import engine as E  # noqa: E402

DATA = 'https://data.alpaca.markets'
CAPITAL = float(os.getenv('CAPITAL', '1000'))


def keys():
    k, s = os.getenv('ALPACA_KEY', ''), os.getenv('ALPACA_SECRET', '')
    if not (k and s) and os.path.exists(os.path.join(ROOT, 'config.txt')):
        for line in open(os.path.join(ROOT, 'config.txt'), encoding='utf-8'):
            if line.startswith('ALPACA_KEY='):
                k = k or line.split('=', 1)[1].strip()
            if line.startswith('ALPACA_SECRET='):
                s = s or line.split('=', 1)[1].strip()
    return {'APCA-API-KEY-ID': k, 'APCA-API-SECRET-KEY': s}


def _pages(url, params, headers, key):
    rows, token = [], None
    while True:
        p = dict(params, limit=10000)
        if token:
            p['page_token'] = token
        r = requests.get(url, params=p, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        bars = j.get('bars') or {}
        rows += bars.get(key, []) if isinstance(bars, dict) else bars
        token = j.get('next_page_token')
        if not token:
            return rows


def to_df(rows):
    df = pd.DataFrame(rows).rename(columns={'t': 'date', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_convert(None).dt.normalize()
    return df.set_index('date')[['open', 'high', 'low', 'close', 'volume']].astype(float).sort_index()


def load_alpaca(symbol, start):
    end = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    if symbol.endswith('-USD'):                                  # کریپتو: BTC-USD → BTC/USD
        sym = symbol.replace('-', '/')
        rows = _pages(f'{DATA}/v1beta3/crypto/us/bars', {'symbols': sym, 'timeframe': '1Day', 'start': start, 'end': end},
                      keys(), sym)
        return to_df(rows), 'Alpaca crypto'
    h = keys()
    for feed in ('sip', 'iex'):
        try:
            rows = _pages(f'{DATA}/v2/stocks/{symbol}/bars', {'timeframe': '1Day', 'start': start, 'end': end,
                                                              'adjustment': 'all', 'feed': feed}, h, None)
            if rows:
                return to_df(rows), f'Alpaca {feed.upper()}'
        except requests.HTTPError as e:
            print(f'{symbol} feed={feed}: {e}', file=sys.stderr)
    raise RuntimeError(f'no Alpaca data for {symbol}')


def fa(x):
    return str(x).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


def pct(v):
    return fa(f'{v:+.1f}٪')


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


def run(spec_id, yahoo):
    spec = yaml.safe_load(open(os.path.join(HERE, 'specs', f'{spec_id}.yaml'), encoding='utf-8'))
    prices, src = {}, ''
    for s in spec['symbols']:
        prices[s], src = load_alpaca(s, '2015-01-01T00:00:00Z')
    res = E.run_spec(spec, prices)
    x = E.build_frame(prices[spec['symbols'][0]], spec)
    in_now = bool(E.evaluate_expr(x, spec['entry']).iloc[-1])
    f, b, o, bo = res['full'], res['buyhold_full'], res['out_sample'], res['buyhold_out_sample']
    end_val, bh_val = CAPITAL * (1 + f['total'] / 100), CAPITAL * (1 + b['total'] / 100)
    y = yahoo.get(spec['id'], {})
    lines = [
        f"🧪 تست روی داده‌ی آلپاکا — {spec['name_fa']}",
        f"نماد: {', '.join(spec['symbols'])} | منبع داده: {src}",
        f"قانون: ورود «{spec['entry']}»، خروج «{spec['exit']}»",
        f"دوره: {fa(res['period'])}",
        '',
        f"💵 ۱٬۰۰۰ دلار ← {fa(f'{end_val:,.0f}')} دلار ({pct(f['total'])})",
        f"   نگه‌داشتن ساده: {fa(f'{bh_val:,.0f}')} دلار ({pct(b['total'])})",
        f"📈 بازده سالانه: {pct(f['cagr'])} (نگه‌داشتن: {pct(b['cagr'])})",
        f"📉 بیشترین افت: {pct(f['max_dd'])} (نگه‌داشتن: {pct(b['max_dd'])})",
        f"⚖️ شارپ: {fa(f['sharpe'])} (نگه‌داشتن: {fa(b['sharpe'])})",
        f"🔁 معاملات: {fa(res['trades'])} | برد: {fa(res['win_rate'])}٪ | زمان در بازار: {fa(round(res['exposure'] * 100))}٪",
        f"🧷 خارج از نمونه (از {fa(res['oos_start'])}): سالانه {pct(o['cagr'])}، شارپ {fa(o['sharpe'])} "
        f"| نگه‌داشتن: {pct(bo['cagr'])}، شارپ {fa(bo['sharpe'])}",
        f"🏁 نتیجه با داده‌ی آلپاکا: {res['verdict']}",
    ]
    if y.get('full'):
        lines.append(f"🔎 مقایسه با تست Yahoo ({fa(y.get('period', ''))}): سالانه {pct(y['full']['cagr'])}، "
                     f"شارپ {fa(y['full']['sharpe'])}، نتیجه: {y.get('verdict')}")
    lines += ['', f"📍 وضعیت امروز طبق قانون: {'داخل بازار (خرید)' if in_now else 'بیرون از بازار (نقد)'}",
              'ℹ️ فقط بک‌تست است؛ هیچ سفارشی ثبت نشد. هزینه‌ی معامله در هر طرف لحاظ شده.']
    return '\n'.join(lines), res


def main():
    ids = sys.argv[1:]
    yp = os.path.join(ROOT, 'data', 'strategy_hunter', 'results.json')
    yahoo = json.load(open(yp, encoding='utf-8')).get('results', {}) if os.path.exists(yp) else {}
    failed = 0
    for sid in ids:
        try:
            text, _ = run(sid, yahoo)
        except Exception as e:
            failed += 1
            text = f'⚠️ تست آلپاکا برای {sid} انجام نشد: {e!r}'[:500]
        print(text, '\n')
        if not tg(text):
            failed += 1
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
