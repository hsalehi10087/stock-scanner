"""سهام هوش مصنوعی — داده‌ی بنیادی و قیمتی روزانه برای فهرست سهام AI (به‌علاوه‌ی نمادهایی که در خبرها آمده).

خروجی: data/ai_stocks/metrics.json — برای هر نماد: ارزش بازار، رشد فروش، حاشیه‌ها، نقد و بدهی، جریان نقد آزاد،
بازده ۶ و ۱۲ ماهه، فاصله از سقف ۵۲ هفته، هدف قیمت تحلیلگران، و یک امتیاز کمی اولیه (فقط برای مرتب‌سازی).
تحلیل نهایی و انتخاب را کار روزانه‌ی Claude با خواندن خبرها انجام می‌دهد.
"""
import datetime as dt
import glob
import json
import math
import os
import re
import time

import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'ai_stocks')
# فهرست پایه: سهام کوچک و متوسط مرتبط با هوش مصنوعی در لایه‌های مختلف (تراشه، شبکه، دیتاسنتر و انرژی، نرم‌افزار، کاربرد)
UNIVERSE = {
    'chips/networking': ['ALAB', 'CRDO', 'AMBA', 'LSCC', 'SITM', 'AEHR', 'AAOI', 'POET', 'HIMX', 'CAMT', 'ONTO', 'ACMR',
                         'MRVL', 'LITE', 'COHR', 'FN', 'NVTS', 'MU', 'ARM', 'SMCI'],
    'datacenter/power': ['NBIS', 'CRWV', 'IREN', 'APLD', 'CIFR', 'WULF', 'GLXY', 'VRT', 'POWL', 'OKLO', 'SMR', 'BE', 'VNET'],
    'software/data': ['PLTR', 'AI', 'SOUN', 'BBAI', 'PATH', 'SNOW', 'MDB', 'ESTC', 'CFLT', 'GTLB', 'DOCN', 'S', 'ZETA', 'INOD',
                      'DDOG', 'NET', 'TEM', 'APP', 'RDDT', 'DUOL', 'UPST'],
    'robotics/autonomy': ['SERV', 'RR', 'SYM', 'AUR', 'MBLY', 'PONY', 'ACHR', 'JOBY', 'KTOS', 'AVAV', 'TSLA'],
    'quantum': ['IONQ', 'RGTI', 'QBTS', 'QUBT'],
    'ai-bio': ['RXRX', 'SDGR', 'ABSI'],
}
TICK = re.compile(r'(?:\$|\b(?:NASDAQ|NYSE|NYSEARCA|AMEX)\s*:\s*)([A-Z]{1,5})\b')


def news_tickers():
    found = set()
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'news', '20*.jsonl')))[-3:]:
        for ln in open(f, encoding='utf-8'):
            n = json.loads(ln)
            if 'ai' in n.get('assets', []):
                found.update(TICK.findall(n.get('title', '') + ' ' + n.get('summary', '')))
    return found


def ret(h, days):
    c = h['Close'].dropna()
    if len(c) < 5:
        return None
    past = c[c.index <= c.index[-1] - dt.timedelta(days=days)]
    return round((float(c.iloc[-1]) / float(past.iloc[-1]) - 1) * 100, 1) if len(past) else None


def main():
    os.makedirs(OUT, exist_ok=True)
    seg = {t: s for s, ts in UNIVERSE.items() for t in ts}
    extra = sorted(news_tickers() - set(seg))[:30]
    for t in extra:
        seg[t] = 'from-news'
    out = {}
    for t, s in seg.items():
        try:
            tk = yf.Ticker(t)
            i = tk.get_info()
            h = tk.history(period='13mo', auto_adjust=True)
            if not i or h.empty:
                continue
            px = float(h['Close'].dropna().iloc[-1])
            mc = i.get('marketCap')
            rg = i.get('revenueGrowth')
            hi = float(h['High'].max())
            tgt = i.get('targetMeanPrice')
            row = {'name': i.get('shortName') or i.get('longName'), 'segment': s, 'price': round(px, 2),
                   'market_cap_b': round(mc / 1e9, 2) if mc else None,
                   'revenue_ttm_b': round(i['totalRevenue'] / 1e9, 3) if i.get('totalRevenue') else None,
                   'revenue_growth_pct': round(rg * 100, 1) if rg is not None else None,
                   'gross_margin_pct': round(i['grossMargins'] * 100, 1) if i.get('grossMargins') is not None else None,
                   'operating_margin_pct': round(i['operatingMargins'] * 100, 1) if i.get('operatingMargins') is not None else None,
                   'cash_b': round(i['totalCash'] / 1e9, 2) if i.get('totalCash') else None,
                   'debt_b': round(i['totalDebt'] / 1e9, 2) if i.get('totalDebt') else None,
                   'fcf_b': round(i['freeCashflow'] / 1e9, 3) if i.get('freeCashflow') else None,
                   'ps_ratio': round(mc / i['totalRevenue'], 1) if mc and i.get('totalRevenue') else None,
                   'ret_6m_pct': ret(h, 182), 'ret_12m_pct': ret(h, 365),
                   'from_52w_high_pct': round((px / hi - 1) * 100, 1) if hi else None,
                   'analyst_target': tgt, 'analyst_upside_pct': round((tgt / px - 1) * 100, 1) if tgt else None,
                   'analysts': i.get('numberOfAnalystOpinions'), 'recommendation': i.get('recommendationKey')}
            # امتیاز کمی اولیه: رشد فروش بالا، شرکت هنوز کوچک، حاشیه‌ی ناخالص خوب، نقدینگی کافی
            sc = 0.0
            if row['revenue_growth_pct'] is not None:
                sc += min(row['revenue_growth_pct'], 150) / 30
            if row['market_cap_b']:
                sc += max(0, 3 - math.log10(max(row['market_cap_b'], 0.1)) * 1.5)
            if row['gross_margin_pct'] is not None:
                sc += row['gross_margin_pct'] / 40
            if row['cash_b'] is not None and row['debt_b'] is not None:
                sc += 0.5 if row['cash_b'] >= row['debt_b'] else -0.5
            row['quant_score'] = round(sc, 2)
            out[t] = row
        except Exception as e:
            out[t] = {'segment': s, 'error': repr(e)[:120]}
        time.sleep(0.4)
    json.dump({'date': str(dt.date.today()), 'count': len(out), 'from_news': extra, 'stocks': out},
              open(os.path.join(OUT, 'metrics.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = [t for t, r in out.items() if 'error' not in r]
    print(f'metrics for {len(ok)}/{len(out)}; from news: {extra}')


if __name__ == '__main__':
    main()
