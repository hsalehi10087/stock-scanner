"""نمودار و تحلیل تکنیکال هر سیگنال «احتمال رشد تکنیکال و بنیادی».

برای هر سهم: شمع‌های روزانه‌ی ۱۲ ماه، میانگین‌های ۵۰/۱۵۰/۲۰۰ روزه، سطح مقاومت (سقف ۵۰ روز قبل = نقطه‌ی شکست)،
سقف ۵۲ هفته، حمایت (کف ۲۰ روزه و میانگین ۵۰)، سطح ابطال (حد ضرر فرضی) و حجم با میانگین ۵۰ روزه.
همه‌ی محاسبات فقط با داده تا امروز است.
"""
import datetime as dt

import numpy as np
import pandas as pd


def fa(x):
    return str(x).translate(str.maketrans('0123456789.-', '۰۱۲۳۴۵۶۷۸۹٫−'))


def download(tickers):
    import yfinance as yf
    out = {}
    if not tickers:
        return out
    df = yf.download(list(tickers), period='2y', interval='1d', group_by='ticker', auto_adjust=True,
                     threads=True, progress=False)
    for t in tickers:
        try:
            d = (df[t] if len(tickers) > 1 else df)[['Open', 'High', 'Low', 'Close', 'Volume']].dropna(subset=['Close'])
            if len(d) >= 210:
                out[t] = d
        except Exception:
            continue
    return out


def rsi(c, n=14):
    d = c.diff()
    up, dn = d.clip(lower=0).ewm(alpha=1 / n).mean(), (-d.clip(upper=0)).ewm(alpha=1 / n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def analyze(d):
    c, h, lo, v = d.Close, d.High, d.Low, d.Volume
    p = float(c.iloc[-1])
    s50, s150, s200 = (float(c.rolling(n).mean().iloc[-1]) for n in (50, 150, 200))
    hi52 = float(h.tail(252).max())
    pivot = float(h.iloc[-51:-1].max())          # سقف ۵۰ روز قبل از امروز: سطح شکست/مقاومت
    low20 = float(lo.tail(20).min())
    atr = float((pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)).tail(14).mean())
    # سطح ابطال: زیر کف ۲۰ روزه، ولی نه بیشتر از ۸٪ زیر قیمت (قاعده‌ی اونیل)
    stop = max(low20 - 0.5 * atr, p * 0.92)
    v50 = float(v.iloc[-51:-1].mean())
    a = {'price': p, 's50': s50, 's150': s150, 's200': s200, 'hi52': hi52, 'pivot': pivot, 'low20': low20,
         'stop': stop, 'risk_pct': (p / stop - 1) * 100, 'to_hi_pct': (hi52 / p - 1) * 100,
         'rsi': float(rsi(c).iloc[-1]), 'vol_x': float(v.iloc[-1] / v50) if v50 > 0 else None,
         'vol5_x': float(v.tail(5).mean() / v50) if v50 > 0 else None,
         'atr_pct': atr / p * 100, 'broke_out': p > pivot}
    # جمع‌بندی ساده
    if p > s50 > s150 > s200:
        a['trend_fa'] = 'روند صعودی کامل (قیمت بالای میانگین‌های ۵۰، ۱۵۰ و ۲۰۰)'
    elif p > s200:
        a['trend_fa'] = 'بالای میانگین ۲۰۰ روزه، ولی روند هنوز کامل نیست'
    else:
        a['trend_fa'] = 'زیر میانگین ۲۰۰ روزه (روند بلندمدت ضعیف)'
    return a


def caption(s, a, flag=''):
    r = a['rsi']
    rsi_fa = 'داغ؛ احتمال استراحت' if r >= 70 else ('ضعیف' if r < 40 else 'متعادل')
    if a['broke_out']:
        lvl = f"شکست انجام شده؛ سطح {fa(round(a['pivot'], 2))} حالا حمایت است"
    else:
        lvl = f"مقاومت/نقطه‌ی شکست: {fa(round(a['pivot'], 2))} ({fa(f'{(a['pivot'] / a['price'] - 1) * 100:+.1f}')}٪)"
    vol = ''
    if a['vol_x'] is not None:
        vol = f"حجم امروز {fa(f'{a['vol_x']:.1f}')}× میانگین؛ ۵ روز اخیر {fa(f'{a['vol5_x']:.1f}')}×"
    lines = [f"{flag} <b>{s['ticker']}</b> — قیمت {fa(round(a['price'], 2))}",
             f"📈 {a['trend_fa']}",
             f"🎯 {lvl} | سقف ۵۲ هفته: {fa(round(a['hi52'], 2))} ({fa(f'{a['to_hi_pct']:+.1f}')}٪)",
             f"🛡 حمایت: میانگین ۵۰ = {fa(round(a['s50'], 2))} | کف ۲۰ روزه = {fa(round(a['low20'], 2))}",
             f"⛔ سطح ابطال: {fa(round(a['stop'], 2))} (ریسک {fa(f'{a['risk_pct']:.1f}')}٪)",
             f"⚡ RSI: {fa(round(r))} ({rsi_fa}) | {vol}"]
    return '\n'.join(lines)


def render(d, s, a, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    c = d.Close
    sma = {n: c.rolling(n).mean() for n in (50, 150, 200)}
    d = d.tail(252)
    x = np.arange(len(d))
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(10, 6.2), dpi=110, sharex=True,
                                  gridspec_kw={'height_ratios': [3.2, 1], 'hspace': 0.04})
    up = (d.Close >= d.Open).values
    col = np.where(up, '#16a34a', '#dc2626')
    ax.vlines(x, d.Low, d.High, color=col, linewidth=0.7)
    ax.bar(x, (d.Close - d.Open).abs().clip(lower=d.Close * 0.0008), bottom=np.minimum(d.Open, d.Close),
           color=col, width=0.7)
    for n, cl in ((50, '#2563eb'), (150, '#f59e0b'), (200, '#7c3aed')):
        ax.plot(x, sma[n].reindex(d.index).values, color=cl, linewidth=1.2, label=f'SMA{n}')
    last = len(d) - 1
    lv = [(a['hi52'], '#6b7280', '52w high', ':'), (a['pivot'], '#dc2626', 'Resistance', '--'),
          (a['low20'], '#16a34a', 'Support (20d low)', '--'), (a['stop'], '#111827', 'Stop', '-.')]
    merged = []
    for y, cl, lab, ls in sorted(lv, key=lambda z: -z[0]):
        if merged and abs(merged[-1][0] / y - 1) < 0.004:      # یک سطح با دو نام
            merged[-1][2] += ' = ' + lab
            continue
        merged.append([y, cl, lab, ls])
        ax.axhline(y, color=cl, linestyle=ls, linewidth=1)
    lo_, hi_ = float(d.Low.min()), float(d.High.max())
    gap, prev = (hi_ - lo_) * 0.055, None
    for y, cl, lab, _ in merged:                               # برچسب‌ها روی هم نیفتند
        ty = y if prev is None else min(y, prev - gap)
        ax.annotate(f'{lab}  {y:,.2f}', xy=(last, y), xytext=(last + 3, ty), fontsize=7.5, color=cl, va='center',
                    arrowprops=dict(arrowstyle='-', color=cl, lw=0.6), bbox=dict(fc='white', ec='none', pad=1))
        prev = ty
    # بازه‌ی پایه (۵۰ روز قبل از امروز) سایه‌دار
    ax.axvspan(last - 50, last - 1, color='#3b82f6', alpha=0.05)
    ax.scatter([last], [a['price']], s=60, color='#f59e0b', zorder=5, edgecolor='k')
    setups = ', '.join({'breakout': 'Volume breakout', 'trend': 'Stage-2 trend', 'vcp': 'Tight near high (VCP)',
                        'pullback': 'Pullback to SMA50'}.get(z, z) for z in s['setups'])
    ax.set_title(f"{s['ticker']}  {(s.get('name') or '')[:30]}  |  {setups}  |  RSI {a['rsi']:.0f}",
                 fontsize=10.5, loc='left')
    ax.legend(loc='upper left', fontsize=8, frameon=False)
    ax.grid(alpha=0.2)
    ax.set_xlim(-2, last + 62)
    axv.bar(x, d.Volume, color=col, width=0.7, alpha=0.6)
    axv.plot(x, d.Volume.rolling(50).mean().values, color='#111827', linewidth=1)
    axv.set_ylabel('Vol', fontsize=8)
    axv.grid(alpha=0.2)
    axv.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda y, _: f'{y / 1e6:.1f}M' if y >= 1e6 else f'{y / 1e3:.0f}K'))
    ticks = [i for i in range(0, len(d), 21)]
    axv.set_xticks(ticks)
    axv.set_xticklabels([d.index[i].strftime('%b %y') for i in ticks], fontsize=8)
    fig.text(0.99, 0.005, f'{dt.date.today()} • not investment advice', ha='right', fontsize=7, color='#9ca3af')
    fig.savefig(path, bbox_inches='tight')
    plt.close(fig)
