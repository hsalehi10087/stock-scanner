"""ربات فارکس بر اساس گزارش COT (موقعیت معامله‌گران بزرگ در آتی ارزها، CFTC).

داده: گزارش هفتگی «Traders in Financial Futures» (publicreporting.cftc.gov، رایگان). هر سه‌شنبه ثبت و جمعه منتشر می‌شود.
  «صندوق‌های اهرمی» (Leveraged Funds = هج‌فاندها و CTAها) و «مدیران دارایی» (Asset Managers).
هفت ارز اصلی در برابر دلار: EUR, JPY, GBP, CHF, CAD, AUD, NZD.

دستورها:
  python3 forex/cot.py fetch      دریافت تاریخچه‌ی COT ← data/forex/cot.csv
  python3 forex/cot.py backtest   آزمون قاعده‌ها روی ۱۰+ سال (۷۰٪ آموزش، ۳۰٪ آزمون جدا) ← data/forex/backtest.json
  python3 forex/cot.py weekly     سیگنال این هفته + دفتر معاملات آزمایشی ← data/forex/{signals,ledger}.json
  python3 forex/cot.py report     گزارش تلگرام
"""
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'forex')
COT = os.path.join(OUT, 'cot.csv')
API = 'https://publicreporting.cftc.gov/resource/gpe5-46if.json'
# کد قرارداد CFTC → (ارز، جفت‌ارز OANDA، نماد Yahoo، آیا قیمت جفت‌ارز برعکس ارز است؟)
CURR = {
    '099741': ('EUR', 'EUR_USD', 'EURUSD=X', False),
    '097741': ('JPY', 'USD_JPY', 'JPY=X', True),
    '096742': ('GBP', 'GBP_USD', 'GBPUSD=X', False),
    '092741': ('CHF', 'USD_CHF', 'CHF=X', True),
    '090741': ('CAD', 'USD_CAD', 'CAD=X', True),
    '232741': ('AUD', 'AUD_USD', 'AUDUSD=X', False),
    '112741': ('NZD', 'NZD_USD', 'NZDUSD=X', False),
}
FA_CUR = {'EUR': '🇪🇺 یورو', 'JPY': '🇯🇵 ین', 'GBP': '🇬🇧 پوند', 'CHF': '🇨🇭 فرانک', 'CAD': '🇨🇦 دلار کانادا',
          'AUD': '🇦🇺 دلار استرالیا', 'NZD': '🇳🇿 دلار نیوزیلند'}
PAPER_USD = 10000          # سرمایه‌ی آزمایشی کل (هر ارز سهم مساوی)
FA = str.maketrans('0123456789.-', '۰۱۲۳۴۵۶۷۸۹٫−')


def fa(x):
    return str(x).translate(FA)


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- داده
def fetch():
    codes = ','.join(f"'{c}'" for c in CURR)
    rows, off = [], 0
    while True:
        r = requests.get(API, timeout=60, params={'$where': f'cftc_contract_market_code in ({codes})',
                                                  '$order': 'report_date_as_yyyy_mm_dd', '$limit': 5000, '$offset': off})
        r.raise_for_status()
        js = r.json()
        rows += js
        if len(js) < 5000:
            break
        off += 5000
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    if not len(df):
        raise RuntimeError('COT: no rows')
    json.dump(rows[-2:], open(os.path.join(OUT, 'cot_sample.json'), 'w'), indent=1)
    keep = ['report_date_as_yyyy_mm_dd', 'cftc_contract_market_code', 'open_interest_all',
            'lev_money_positions_long', 'lev_money_positions_short', 'asset_mgr_positions_long', 'asset_mgr_positions_short']
    miss = [k for k in keep if k not in df.columns]
    if miss:
        raise RuntimeError(f'COT columns missing: {miss}; have {list(df.columns)[:40]}')
    df = df[keep].copy()
    df['date'] = pd.to_datetime(df.pop('report_date_as_yyyy_mm_dd')).dt.date
    for c in keep[2:]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['cur'] = df.pop('cftc_contract_market_code').map(lambda c: CURR[c][0])
    df['lev_net'] = (df.lev_money_positions_long - df.lev_money_positions_short) / df.open_interest_all
    df['am_net'] = (df.asset_mgr_positions_long - df.asset_mgr_positions_short) / df.open_interest_all
    df = df.sort_values(['cur', 'date'])
    df.to_csv(COT, index=False)
    log(f'COT: {len(df)} rows, {df.date.min()} → {df.date.max()}')
    return df


def load():
    df = pd.read_csv(COT, parse_dates=['date'])
    return df


def prices(start='2009-01-01'):
    """قیمت هفتگی ارز در برابر دلار (بالا رفتن = ارز قوی‌تر)، بسته‌شدن سه‌شنبه‌ها هم‌زمان با تاریخ COT."""
    import yfinance as yf
    syms = {v[0]: (v[2], v[3]) for v in CURR.values()}
    df = yf.download([s for s, _ in syms.values()], start=start, interval='1d', auto_adjust=True, progress=False)['Close']
    out = {}
    for cur, (s, inv) in syms.items():
        c = df[s].dropna()
        out[cur] = 1 / c if inv else c
    return pd.DataFrame(out)


# ---------------------------------------------------------------- قاعده‌ها
def features(cot):
    """برای هر ارز و هفته: z-score سه‌ساله‌ی موقعیت خالص صندوق‌های اهرمی و تغییر ۴ هفته‌ای آن."""
    f = []
    for cur, g in cot.groupby('cur'):
        g = g.set_index('date').sort_index()
        x = g['lev_net']
        z = (x - x.rolling(156, min_periods=104).mean()) / x.rolling(156, min_periods=104).std()
        d4 = x.diff(4)
        f.append(pd.DataFrame({'cur': cur, 'lev_net': x, 'z': z, 'd4': d4, 'am_net': g['am_net']}))
    return pd.concat(f).reset_index()


RULES = {
    # دنبال‌کردن: هم‌جهت با تغییر موقعیت هج‌فاندها در ۴ هفته‌ی اخیر
    'follow_flow': lambda r: np.sign(r.d4),
    # دنبال‌کردن جهت موقعیت خالص (خرید اگر خالص مثبت)
    'follow_net': lambda r: np.sign(r.lev_net),
    # خلاف‌جهت در افراط: اگر z > ۲ فروش، اگر z < −۲ خرید، وگرنه بی‌موقعیت
    'contrarian_extreme': lambda r: np.where(r.z > 2, -1, np.where(r.z < -2, 1, 0)),
    # ترکیب: هم‌جهت با جریان، مگر در افراط
    'flow_unless_extreme': lambda r: np.where(abs(r.z) > 2, -np.sign(r.z), np.sign(r.d4)),
}


def weekly_returns(px, dates):
    """بازده ارز از جمعه‌ی انتشار گزارش (تاریخ COT + ۳ روز) تا جمعه‌ی بعد — بدون نگاه به آینده."""
    px = px.sort_index()
    rel = {}
    for d in dates:
        t0 = pd.Timestamp(d) + pd.Timedelta(days=4)        # سه‌شنبه + ۴ = شنبه؛ اولین بسته‌شدن بعد از انتشار جمعه
        t1 = t0 + pd.Timedelta(days=7)
        a = px[px.index >= t0].head(1)
        b = px[px.index >= t1].head(1)
        if len(a) and len(b):
            rel[d] = b.iloc[0] / a.iloc[0] - 1
    return pd.DataFrame(rel).T


def stats(r):
    r = r.dropna()
    if len(r) < 20:
        return None
    eq = (1 + r).cumprod()
    yrs = len(r) / 52
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = (eq / eq.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(52) if r.std() > 0 else 0
    return {'cagr': round(cagr * 100, 1), 'max_dd': round(dd * 100, 1), 'sharpe': round(float(sh), 2),
            'weeks': int(len(r)), 'hit': round(float((r > 0).mean() * 100), 1)}


def backtest():
    cot = load()
    F = features(cot).dropna(subset=['z', 'd4'])
    px = prices()
    dates = sorted(F.date.unique())
    R = weekly_returns(px, dates)                     # rows: date, cols: currencies
    res, split = {}, dates[int(len(dates) * 0.7)]
    for name, rule in RULES.items():
        port = []
        for d, g in F.groupby('date'):
            if d not in R.index:
                continue
            pos = pd.Series(np.asarray(rule(g), dtype=float), index=g.cur.values)
            ret = (pos * R.loc[d].reindex(pos.index)).dropna()
            n = int((pos != 0).sum())
            port.append((d, float(ret.sum() / len(CURR)) if n else 0.0))   # سهم مساوی برای هر ارز
        s = pd.Series(dict(port)).sort_index()
        res[name] = {'train': stats(s[s.index < split]), 'test': stats(s[s.index >= split]), 'full': stats(s)}
    bh = R.mean(axis=1)                                # مقایسه: خرید همه‌ی ارزها در برابر دلار
    res['_buy_all_vs_usd'] = {'train': stats(bh[bh.index < split]), 'test': stats(bh[bh.index >= split]), 'full': stats(bh)}
    # انتخاب: بهترین Sharpe در دوره‌ی آموزش؛ «قبول» فقط اگر در آزمون جدا هم Sharpe ≥ ۰٫۳ و CAGR > ۰ و ریزش کمتر از ۲۵٪
    cands = {k: v for k, v in res.items() if not k.startswith('_') and v['train'] and v['test']}
    best = max(cands, key=lambda k: cands[k]['train']['sharpe'])
    t = cands[best]['test']
    verdict = 'قبول' if t['sharpe'] >= 0.3 and t['cagr'] > 0 and t['max_dd'] > -25 else 'رد'
    out = {'date': str(dt.date.today()), 'split': str(split)[:10], 'rules': res, 'chosen': best, 'verdict': verdict}
    json.dump(out, open(os.path.join(OUT, 'backtest.json'), 'w'), ensure_ascii=False, indent=1)
    log(json.dumps({k: v['test'] for k, v in res.items()}, ensure_ascii=False))
    log('chosen', best, verdict)
    return out


# ---------------------------------------------------------------- سیگنال هفتگی + دفتر آزمایشی
def weekly():
    bt = json.load(open(os.path.join(OUT, 'backtest.json'), encoding='utf-8'))
    cot = load()
    F = features(cot)
    last = F[F.date == F.date.max()].set_index('cur')
    rule = RULES[bt['chosen']]
    pos = pd.Series(np.nan_to_num(np.asarray(rule(last.reset_index()), dtype=float)), index=last.index)
    sig = {'cot_date': str(F.date.max())[:10], 'rule': bt['chosen'], 'verdict': bt['verdict'], 'currencies': {}}
    for cur, r in last.iterrows():
        sig['currencies'][cur] = {'lev_net_pct': round(r.lev_net * 100, 1), 'am_net_pct': round(r.am_net * 100, 1),
                                  'z': round(float(r.z), 2) if r.z == r.z else None,
                                  'd4_pct': round(r.d4 * 100, 1) if r.d4 == r.d4 else None,
                                  'position': int(pos[cur])}
    # دفتر آزمایشی: هر هفته موقعیت‌ها با قیمت روز اجرا ثبت و بازده هفته‌ی قبل حساب می‌شود
    lp = os.path.join(OUT, 'ledger.json')
    led = json.load(open(lp, encoding='utf-8')) if os.path.exists(lp) else {'start': str(dt.date.today()), 'equity': PAPER_USD,
                                                                          'open': None, 'history': []}
    px = prices(start=str(dt.date.today() - dt.timedelta(days=30))).ffill().iloc[-1]
    if led['open'] and led['open']['cot_date'] != sig['cot_date']:
        o = led['open']
        rets = {c: o['pos'][c] * (float(px[c]) / o['px'][c] - 1) for c in o['pos'] if o['pos'][c]}
        week = sum(rets.values()) / len(CURR)
        led['equity'] = round(led['equity'] * (1 + week), 2)
        led['history'].append({'from': o['date'], 'to': str(dt.date.today()), 'ret_pct': round(week * 100, 2),
                               'per_cur': {c: round(v * 100, 2) for c, v in rets.items()}, 'equity': led['equity']})
        led['open'] = None
    if not led['open'] or led['open']['cot_date'] != sig['cot_date']:
        led['open'] = {'date': str(dt.date.today()), 'cot_date': sig['cot_date'],
                       'pos': {c: int(v) for c, v in pos.items()}, 'px': {c: float(px[c]) for c in pos.index}}
    json.dump(sig, open(os.path.join(OUT, 'signals.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(led, open(lp, 'w'), ensure_ascii=False, indent=1)
    oanda(sig, bt)
    return sig, led


def oanda(sig, bt):
    """اجرا روی حساب آزمایشی OANDA — فقط اگر کلیدها تنظیم شده باشند و قاعده آزمون جدا را قبول شده باشد."""
    tok, acc = os.getenv('OANDA_TOKEN'), os.getenv('OANDA_ACCOUNT')
    if not tok or not acc:
        log('OANDA: keys not set — paper ledger only')
        return
    if bt['verdict'] != 'قبول':
        log('OANDA: rule did not pass out-of-sample test — no orders')
        return
    base = 'https://api-fxpractice.oanda.com/v3'          # فقط حساب آزمایشی
    H = {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}
    units_each = int(PAPER_USD / len(CURR))
    cur_pos = {p['instrument']: int(p['long']['units']) + int(p['short']['units'])
               for p in requests.get(f'{base}/accounts/{acc}/openPositions', headers=H, timeout=30).json().get('positions', [])}
    for code, (cur, inst, _, inv) in CURR.items():
        want = sig['currencies'][cur]['position'] * (-1 if inv else 1) * units_each   # جفت برعکس: خرید ارز = فروش جفت
        diff = want - cur_pos.get(inst, 0)
        if diff:
            r = requests.post(f'{base}/accounts/{acc}/orders', headers=H, timeout=30,
                              json={'order': {'type': 'MARKET', 'instrument': inst, 'units': str(diff)}})
            log('OANDA', inst, diff, r.status_code)


# ---------------------------------------------------------------- گزارش
def report():
    sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
    import summary as S
    bt = json.load(open(os.path.join(OUT, 'backtest.json'), encoding='utf-8'))
    sig = json.load(open(os.path.join(OUT, 'signals.json'), encoding='utf-8'))
    led = json.load(open(os.path.join(OUT, 'ledger.json'), encoding='utf-8'))
    t = bt['rules'][bt['chosen']]['test']
    bh = bt['rules']['_buy_all_vs_usd']['test']
    RN = {'follow_flow': 'هم‌جهت با تغییر موقعیت هج‌فاندها (۴ هفته)', 'follow_net': 'هم‌جهت با موقعیت خالص هج‌فاندها',
          'contrarian_extreme': 'خلاف‌جهت در موقعیت‌های افراطی', 'flow_unless_extreme': 'هم‌جهت با جریان، مگر در افراط'}
    L = [f"<b>💱 فارکس — موقعیت معامله‌گران بزرگ (COT)</b> — گزارش {fa(sig['cot_date'].replace('-', '/'))}",
         '<i>هج‌فاندها و صندوق‌ها هر هفته در آتی ارزها چه موقعیتی دارند (منبع: CFTC، با ۳ روز تأخیر)</i>', '']
    for cur, c in sorted(sig['currencies'].items(), key=lambda x: -abs(x[1]['lev_net_pct'])):
        p = {1: '🟢 خرید', -1: '🔴 فروش', 0: '⚪ بی‌موقعیت'}[c['position']]
        ext = ' ⚠️افراطی' if c['z'] is not None and abs(c['z']) > 2 else ''
        L.append(f"{FA_CUR[cur]}: هج‌فاندها {fa(f'{c['lev_net_pct']:+.1f}')}٪ "
                 f"(تغییر ۴ هفته {fa(f'{c['d4_pct']:+.1f}') if c['d4_pct'] is not None else '—'}٪){ext} ← {p}")
    L += ['', f"<b>📐 قاعده‌ی انتخاب‌شده:</b> {RN[bt['chosen']]}",
          f"آزمون جدا (از {fa(bt['split'][:7].replace('-', '/'))}): سالانه {fa(f'{t['cagr']:+.1f}')}٪، "
          f"ریزش {fa(f'{t['max_dd']:.1f}')}٪، شارپ {fa(t['sharpe'])} | خرید همه‌ی ارزها: سالانه {fa(f'{bh['cagr']:+.1f}')}٪",
          ('✅ قاعده آزمون را قبول شد.' if bt['verdict'] == 'قبول' else
           '❌ هیچ قاعده‌ای آزمون جدا را قبول نشد؛ سیگنال فقط برای اطلاع است و معامله‌ی واقعی (حتی آزمایشی OANDA) انجام نمی‌شود.'), '']
    h = led['history']
    L.append(f"<b>📒 دفتر آزمایشی</b> (از {fa(led['start'].replace('-', '/'))}، ۱۰٬۰۰۰ دلار فرضی): "
             f"{fa(f'{led['equity']:,.0f}')} دلار" + (f" | هفته‌ی قبل {fa(f'{h[-1]['ret_pct']:+.2f}')}٪" if h else ' | اولین هفته'))
    L.append('<i>' + ('اجرا روی حساب آزمایشی OANDA فعال است.' if os.getenv('OANDA_TOKEN') else
                      'برای اجرا روی حساب آزمایشی OANDA، کلید API لازم است.') + ' صرفاً آزمایشی؛ توصیه‌ی معامله نیست.</i>')
    msg = '\n'.join(L)
    print(msg)
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    for cid in [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']:
        S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': msg, 'parse_mode': 'HTML'})


if __name__ == '__main__':
    {'fetch': fetch, 'backtest': backtest, 'weekly': weekly, 'report': report}[sys.argv[1]]()
