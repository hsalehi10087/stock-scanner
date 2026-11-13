"""نمودار تکنیکال سیگنال‌های امروز ایجنت ایران، با همان ابزار نمودار ایجنت رشد تکنیکال و بنیادی جهانی
(pattern_hunter/tech_chart.py): حمایت/مقاومت، سطح ابطال، RSI، حجم.

مرورگر (iran/browser/*.js) فقط بسته‌شدن تعدیل‌شده و حجم را از tsetmc می‌دهد، نه کندل OHLC کامل؛ پس برای هر روز
یک کندل تخمینی می‌سازیم: باز = بسته‌شدن روز قبل، بالا/پایین = بیشینه/کمینه‌ی (باز، بسته). این فقط برای ترسیم و
محاسبه‌ی حمایت/مقاومت/ATR استفاده می‌شود؛ خود قیمت بسته‌شدن واقعی و دقیق tsetmc است.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'pattern_hunter'))
import tech_chart as TC  # noqa: E402

SETUP_EN = {'breakout': 'Volume breakout', 'trend': 'Stage-2 trend', 'vcp': 'Tight near high (VCP)',
            'pullback': 'Pullback to SMA50', 'longpat': 'Long-term pattern'}


def frame(hist):
    """hist: {'d': [تاریخ‌های ISO]، 'c': [بسته‌شدن تعدیل‌شده]، 'v': [حجم]} ← DataFrame با Open/High/Low/Close/Volume."""
    c = pd.Series([float(x) for x in hist['c']], index=pd.to_datetime(hist['d']))
    v = pd.Series([float(x) for x in hist['v']], index=c.index)
    o = c.shift(1).fillna(c.iloc[0])
    hi = pd.concat([o, c], axis=1).max(axis=1)
    lo = pd.concat([o, c], axis=1).min(axis=1)
    return pd.DataFrame({'Open': o, 'High': hi, 'Low': lo, 'Close': c, 'Volume': v}).dropna()


def strength(x):
    return (len(x['st']), x['rank'])


def build(passed, out_dir, max_charts=10):
    """passed: لیست (x, c) خروجی merge() که هر x['hist'] دارد. خروجی: [(png_path, caption_fa), ...]."""
    os.makedirs(out_dir, exist_ok=True)
    top = sorted(passed, key=lambda p: strength(p[0]), reverse=True)[:max_charts]
    out = []
    for x, cod in top:
        if not x.get('hist'):
            continue
        try:
            d = frame(x['hist'])
            if len(d) < 60:
                continue
            a = TC.analyze(d)
            s = {'ticker': x['sym'], 'name': x.get('name'),
                 'setups': [SETUP_EN.get(z, z) for z in x['st']]}
            png = os.path.join(out_dir, x['sym'].replace('/', '_') + '.png')
            TC.render(d, {'ticker': x['sym'], 'name': x.get('name'), 'setups': x['st']}, a, png)
            cap_lines = [f"📈 <b>{x['sym']}</b> — {x['name'].strip()}",
                         f"✅ P/E پیش‌بینی {x['fpe']:.2f} در برابر گروه {x['spe']} | رشد فروش {cod['rev_growth']:+.1f}٪، رشد سود {cod['np_growth']:+.1f}٪"]
            cap_lines += TC.caption(s, a).split('\n')[1:]
            cap = '\n'.join(cap_lines)
            if len(cap) > 1000:
                cap = cap[:1000]
            out.append((png, cap))
        except Exception as e:
            print('⚠️ chart', x.get('sym'), e, file=sys.stderr)
    return out
