"""آزمون مدل Kronos (مدل پایه‌ی پیش‌بینی کندل، github.com/shiyu-coder/Kronos، مجوز MIT) روی داده‌ی روزانه.

برای هر نماد، در ۴۰ نقطه‌ی گذشته (هر ۵ روز معاملاتی) با ۴۰۰ کندل قبلی، ۵ کندل بعدی پیش‌بینی می‌شود (میانگین ۵ مسیر نمونه).
فقط داده‌ی قبل از هر نقطه به مدل داده می‌شود. سنجش: درصد درستی جهت ۵ روزه، همبستگی پیش‌بینی با واقعیت (IC)،
و قانون «فقط وقتی پیش‌بینی مثبت است در بازار باش» در برابر نگه‌داشتن ساده.
معیار قبول (از پیش): درستی جهت ≥ ۵۵٪ و IC ≥ ۰٫۰۵ و شارپ قانون ≥ شارپ نگه‌داشتن، در دست‌کم ۳ نماد از ۵.
خروجی: data/kronos/result.json (به‌علاوه‌ی پیش‌بینی ۵ روز آینده). پیام تلگرام نمی‌فرستد.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402

SYMS = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] not in ('', 'x') else 'SPY,QQQ,GLD,BTC-USD,ETH-USD').split(',')
MODEL = os.getenv('KRONOS_MODEL', 'NeoQuasar/Kronos-small')
LOOKBACK, H, ORIGINS, STEP, SAMPLES = 400, 5, 40, 5, 5
OUT = os.path.join('data', 'kronos')


def candles(sym):
    d = yf.download(sym, period='4y', auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower)[['open', 'high', 'low', 'close', 'volume']].dropna()
    d['amount'] = d['volume'] * d['close']
    return d


def future_ts(last, n, crypto):
    return pd.Series(pd.date_range(last + pd.Timedelta(days=1), periods=n, freq='D' if crypto else 'B'))


def main():
    torch.set_num_threads(os.cpu_count() or 2)
    tok = KronosTokenizer.from_pretrained('NeoQuasar/Kronos-Tokenizer-base')
    mdl = Kronos.from_pretrained(MODEL)
    pr = KronosPredictor(mdl, tok, device='cpu', max_context=512)
    res = {'model': MODEL, 'lookback': LOOKBACK, 'horizon_days': H, 'origins': ORIGINS, 'symbols': {}}
    t0 = time.time()
    for sym in SYMS:
        d = candles(sym)
        crypto = sym.endswith('-USD')
        n = len(d)
        rows = []
        for k in range(ORIGINS, 0, -1):
            o = n - H - (k - 1) * STEP          # آخرین کندل معلوم = o-1
            if o - LOOKBACK < 0:
                continue
            x = d.iloc[o - LOOKBACK:o]
            y_ts = pd.Series(d.index[o:o + H])
            p = pr.predict(df=x.reset_index(drop=True), x_timestamp=pd.Series(x.index), y_timestamp=y_ts,
                           pred_len=H, T=1.0, top_p=0.9, sample_count=SAMPLES, verbose=False)
            c0 = float(x['close'].iloc[-1])
            rows.append({'date': str(x.index[-1].date()), 'pred': float(p['close'].iloc[-1]) / c0 - 1,
                         'real': float(d['close'].iloc[o + H - 1]) / c0 - 1})
        t = pd.DataFrame(rows)
        hit = float((np.sign(t.pred) == np.sign(t.real)).mean())
        ic = float(np.corrcoef(t.pred, t.real)[0, 1])
        rule = t.real.where(t.pred > 0, 0.0)
        sh = lambda r: float(r.mean() / r.std() * np.sqrt(252 / H)) if r.std() > 0 else 0.0  # noqa: E731
        x = d.iloc[-LOOKBACK:]
        fut = pr.predict(df=x.reset_index(drop=True), x_timestamp=pd.Series(x.index),
                         y_timestamp=future_ts(x.index[-1], H, crypto), pred_len=H, T=1.0, top_p=0.9,
                         sample_count=SAMPLES, verbose=False)
        s = {'n': len(t), 'hit_rate': round(hit * 100, 1), 'ic': round(ic, 3),
             'rule_sharpe': round(sh(rule), 2), 'hold_sharpe': round(sh(t.real), 2),
             'rule_return_pct': round(float((1 + rule).prod() - 1) * 100, 1),
             'hold_return_pct': round(float((1 + t.real).prod() - 1) * 100, 1),
             'forecast_5d_pct': round((float(fut['close'].iloc[-1]) / float(x['close'].iloc[-1]) - 1) * 100, 2),
             'last_close': round(float(x['close'].iloc[-1]), 2), 'last_date': str(x.index[-1].date())}
        s['pass'] = bool(hit >= 0.55 and ic >= 0.05 and s['rule_sharpe'] >= s['hold_sharpe'])
        res['symbols'][sym] = s
        print(sym, s, f'{time.time() - t0:.0f}s', flush=True)
    passed = sum(v['pass'] for v in res['symbols'].values())
    res['verdict'] = 'قبول' if passed >= 3 else 'رد'
    res['passed'] = passed
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'result.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
