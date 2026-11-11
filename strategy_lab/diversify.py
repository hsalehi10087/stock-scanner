"""کدام دارایی کم‌همبستگی جای ربات «باند SPY» را بگیرد؟ (تقریباً همسان با ربات ۱۰ ماهه‌ی VOO است)

همان قانون بدون هیچ تنظیم تازه: ورود وقتی بسته‌شدن ۲٪ بالای میانگین ۲۰۰ روزه‌ی خود دارایی است، خروج ۲٪ زیر آن
(سیگنال روی بسته‌شدن روز t، معامله در روز t+1، هزینه‌ی ۰٫۰۵٪ هر جابه‌جایی). دوره‌ی سنجش از ۲۰۱۶ (مثل آزمون اصلی).
همبستگی با «سبد فعلی»: جمع وزنی بازده روزانه‌ی نمادهای ربات‌های فعلی به نسبت سرمایه‌شان.
معیار قبول از پیش تعیین‌شده: همبستگی با سبد < ۰٫۳، بازده سالانه > ۳٪، شارپ ≥ ۰٫۳، بیشترین افت بهتر از −۲۵٪،
و کاهش بیشترین افت سبد ترکیبی. از قبول‌شده‌ها بالاترین شارپ انتخاب می‌شود.
خروجی: data/strategy_lab/diversify/result.json
"""
import json
import os

import numpy as np
import pandas as pd
import yfinance as yf

OUT = os.path.join('data', 'strategy_lab', 'diversify')
CANDS = {'TLT': 'اوراق بلندمدت آمریکا', 'DBC': 'سبد کالاها', 'UUP': 'دلار آمریکا', 'BTAL': 'ضدبتا (بلند کم‌نوسان/کوتاه پرنوسان)',
         'DBMF': 'مدیریت‌شده‌ی آتی (روند)', 'KMLM': 'مدیریت‌شده‌ی آتی KFA', 'XLU': 'خدمات عمومی', 'SLV': 'نقره',
         'CPER': 'مس', 'FXY': 'ین ژاپن'}
BOOK = {'GLD': 10000, 'QQQ': 20000 + 5000, 'SPY': 10000, 'BTC-USD': 5000, 'ETH-USD': 5000}   # بدون باند SPY
START, COST = '2016-01-01', 0.0005


def band(c, n=200, up=0.02, dn=0.02):
    sma = c.rolling(n).mean()
    pos, cur = [], 0
    for p, m in zip(c.values, sma.values):
        if m == m:
            if cur == 0 and p > m * (1 + up):
                cur = 1
            elif cur == 1 and p < m * (1 - dn):
                cur = 0
        pos.append(cur)
    pos = pd.Series(pos, index=c.index).shift().fillna(0)
    r = c.pct_change().fillna(0) * pos - pos.diff().abs().fillna(0) * COST
    return r


def stats(r):
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    return {'cagr': round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), 'max_dd': round(float((eq / eq.cummax() - 1).min()) * 100, 1),
            'sharpe': round(float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0, 2), 'years': round(yrs, 1)}


def main():
    syms = list(CANDS) + list(BOOK)
    px = yf.download(syms, start='2014-01-01', auto_adjust=True, progress=False)['Close']
    px = px[px.index.dayofweek < 5].ffill()
    br = px[list(BOOK)].pct_change()
    w = pd.Series(BOOK, dtype=float) / sum(BOOK.values())
    book = (br.fillna(0) @ w)[START:]
    res = {'book_alone': stats(book), 'candidates': {}}
    # ترکیب فعلی (با باند SPY روی SPY) برای مقایسه
    spy_band = band(px['SPY'].dropna())[START:]
    cur = (book * sum(BOOK.values()) + spy_band.reindex(book.index).fillna(0) * 5000) / (sum(BOOK.values()) + 5000)
    res['book_with_spy_band'] = stats(cur)
    for s, nm in CANDS.items():
        c = px[s].dropna()
        if len(c) < 260:
            continue
        r = band(c)
        r = r[r.index >= max(pd.Timestamp(START), c.index[0] + pd.Timedelta(days=300))]
        idx = r.index.intersection(book.index)
        if len(idx) < 500:
            res['candidates'][s] = {'name_fa': nm, 'skip': 'کمتر از ۲ سال داده'}
            continue
        corr = float(np.corrcoef(r[idx], book[idx])[0, 1])
        comb = (book[idx] * sum(BOOK.values()) + r[idx] * 5000) / (sum(BOOK.values()) + 5000)
        base = cur.reindex(idx)
        st = stats(r)
        st.update({'name_fa': nm, 'start': str(idx[0].date()), 'corr_book': round(corr, 2),
                   'corr_spy': round(float(np.corrcoef(r[idx], px['SPY'].pct_change()[idx].fillna(0))[0, 1]), 2),
                   'combined': stats(comb), 'combined_now_same_period': stats(base),
                   'buy_hold': stats(c.pct_change()[idx].fillna(0)),
                   'in_market_pct': round(float((r[idx] != 0).mean()) * 100)})
        st['pass'] = bool(corr < 0.3 and st['cagr'] > 3 and st['sharpe'] >= 0.3 and st['max_dd'] > -25
                          and st['combined']['max_dd'] >= st['combined_now_same_period']['max_dd'])
        res['candidates'][s] = st
    ok = {k: v for k, v in res['candidates'].items() if v.get('pass')}
    res['winner'] = max(ok, key=lambda k: ok[k]['sharpe']) if ok else None
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, 'result.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
