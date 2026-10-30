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

import requests
import yfinance as yf

import quality as Q

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'ai_stocks')
# فهرست پایه: سهام کوچک و متوسط مرتبط با هوش مصنوعی در لایه‌های مختلف (تراشه، شبکه، دیتاسنتر و انرژی، نرم‌افزار، کاربرد)
UNIVERSE = {
    'chips/networking': ['ALAB', 'CRDO', 'AMBA', 'LSCC', 'SITM', 'AEHR', 'AAOI', 'POET', 'HIMX', 'CAMT', 'ONTO', 'ACMR',
                         'MRVL', 'LITE', 'COHR', 'FN', 'NVTS', 'MU', 'ARM', 'SMCI'],
    'datacenter/power': ['NBIS', 'CRWV', 'IREN', 'APLD', 'CIFR', 'WULF', 'GLXY', 'VRT', 'POWL', 'OKLO', 'SMR', 'BE', 'VNET'],
    'software/data': ['PLTR', 'AI', 'SOUN', 'BBAI', 'PATH', 'SNOW', 'MDB', 'ESTC', 'CFLT', 'GTLB', 'DOCN', 'S', 'ZETA', 'INOD',
                      'DDOG', 'NET', 'TEM', 'APP', 'RDDT', 'DUOL', 'UPST'],
    'robotics/autonomy': ['SERV', 'RR', 'SYM', 'AUR', 'MBLY', 'PONY', 'ACHR', 'JOBY', 'KTOS', 'AVAV', 'TSLA',
                          'OUST', 'RCAT', 'ARBE', 'PDYN', 'KSCP'],
    'quantum': ['IONQ', 'RGTI', 'QBTS', 'QUBT'],
    'ai-bio': ['RXRX', 'SDGR', 'ABSI'],
}
FINNHUB_KEY = os.getenv('FINNHUB_API_KEY', '')
# شرط‌های لازم برای نامزد شدن (همان شرط‌های کار روزانه‌ی Claude)
MAX_CAP_B, MAX_CAP_NEW_B, MIN_GROWTH, MIN_REV_B = 20, 10, 40, 0.1
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


def data_flags(r):
    """عددهای مشکوک Yahoo: رشد هزاران درصدی از پایه‌ی تقریباً صفر، حاشیه‌ی ناخالص ۱۰۰٪، فروش ناچیز، P/S عجیب."""
    f = []
    g, rv, gm, ps = r.get('revenue_growth_pct'), r.get('revenue_ttm_b'), r.get('gross_margin_pct'), r.get('ps_ratio')
    if g is not None and (g > 1000 or (g > 300 and (rv or 0) < 0.3)):
        f.append('growth_from_tiny_base')
    if gm is not None and gm >= 99:
        f.append('gross_margin_100')
    if gm is not None and gm <= 0 and (rv or 0) > 0:
        f.append('gross_margin_zero')
    if rv is None or rv < 0.05:
        f.append('revenue_tiny')
    if ps is not None and ps > 200:
        f.append('ps_extreme')
    return f


def next_earnings(i, t):
    today = dt.date.today()
    for k in ('earningsTimestampStart', 'earningsTimestamp'):
        v = i.get(k)
        if v:
            d = dt.datetime.fromtimestamp(v, dt.timezone.utc).date()
            if d >= today:
                return str(d)
    if FINNHUB_KEY:
        try:
            time.sleep(1.1)   # سقف رایگان Finnhub
            r = requests.get('https://finnhub.io/api/v1/calendar/earnings', timeout=20,
                             params={'symbol': t, 'from': str(today), 'to': str(today + dt.timedelta(days=100)),
                                     'token': FINNHUB_KEY})
            cal = sorted(x['date'] for x in r.json().get('earningsCalendar', []) if x.get('date'))
            if cal:
                return cal[0]
        except Exception:
            pass
    return None


def company_news(tickers):
    """خبرهای ۳ روز اخیر هر نامزد از Finnhub (با لینک اصلی خبر، نه لینک واسط Google News)."""
    out = {}
    if not FINNHUB_KEY:
        return out
    today = dt.date.today()
    for t in tickers:
        try:
            r = requests.get('https://finnhub.io/api/v1/company-news', timeout=20,
                             params={'symbol': t, 'from': str(today - dt.timedelta(days=3)), 'to': str(today),
                                     'token': FINNHUB_KEY})
            rows = r.json() if r.ok else []
            out[t] = [{'headline': n.get('headline', ''), 'summary': (n.get('summary') or '')[:600],
                       'source': n.get('source', ''), 'url': n.get('url', ''),
                       'published': dt.datetime.fromtimestamp(n.get('datetime', 0), dt.timezone.utc).isoformat()}
                      for n in rows[:15]]
        except Exception as e:
            out[t] = [{'error': repr(e)[:120]}]
        time.sleep(1.1)   # سقف رایگان Finnhub: ۶۰ درخواست در دقیقه
    return out


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
                   'analysts': i.get('numberOfAnalystOpinions'), 'recommendation': i.get('recommendationKey'),
                   'next_earnings': next_earnings(i, t)}
            row['data_flags'] = data_flags(row)
            row['suspect'] = bool(row['data_flags'])
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
            row['quant_score'] = None if row['suspect'] else round(sc, 2)
            cap, gr, rv = row['market_cap_b'], row['revenue_growth_pct'], row['revenue_ttm_b']
            row['eligible'] = bool(not row['suspect'] and cap and cap <= MAX_CAP_B * 1.1 and gr is not None
                                   and gr >= MIN_GROWTH and rv and rv >= MIN_REV_B * 0.9)
            row['eligible_new'] = bool(row['eligible'] and cap <= MAX_CAP_NEW_B * 1.1)
            row['cash_covers_burn'] = (None if row['fcf_b'] is None or row['cash_b'] is None
                                       else bool(row['fcf_b'] >= 0 or row['cash_b'] >= 2 * abs(row['fcf_b'])))
            qq = Q.score(t, 'us')
            row['quality_score'] = qq['score']
            row['quality_flags'] = qq['flags']
            out[t] = row
        except Exception as e:
            out[t] = {'segment': s, 'error': repr(e)[:120]}
        time.sleep(0.4)
    Q.save()
    try:
        prev = [p['ticker'] for p in json.load(open(os.path.join(OUT, 'latest.json'), encoding='utf-8')).get('picks', [])]
    except Exception:
        prev = []
    cands = sorted({t for t, r in out.items() if r.get('eligible')} | set(prev))
    json.dump({'date': str(dt.date.today()), 'built_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'tickers': cands, 'news': company_news(cands)},
              open(os.path.join(OUT, 'company_news.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'date': str(dt.date.today()), 'built_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
               'count': len(out), 'from_news': extra,
               'rules': {'max_cap_b': MAX_CAP_B, 'max_cap_new_b': MAX_CAP_NEW_B, 'min_growth_pct': MIN_GROWTH,
                         'min_revenue_b': MIN_REV_B},
               'eligible': sorted(t for t, r in out.items() if r.get('eligible')),
               'suspect': sorted(t for t, r in out.items() if r.get('suspect')), 'stocks': out},
              open(os.path.join(OUT, 'metrics.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = [t for t, r in out.items() if 'error' not in r]
    print(f'metrics for {len(ok)}/{len(out)}; from news: {extra}; eligible: {sorted(t for t, r in out.items() if r.get("eligible"))}')


if __name__ == '__main__':
    main()
