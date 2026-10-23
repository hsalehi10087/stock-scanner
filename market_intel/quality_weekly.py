"""امتیاز کیفیت رشد برای کل بازار (هفتگی) — ژاپن، آمریکا، چین، تایوان.

python3 market_intel/quality_weekly.py <jp|us|cn|tw>   ← امتیازدهی و ذخیره در data/quality/weekly_<m>.json
python3 market_intel/quality_weekly.py report          ← ارسال ۲۰ سهم برتر هر بازار به تلگرام
فقط سهم‌های قابل معامله: قیمت دست‌کم مقدار حداقل و ۲٬۰۰۰ سهم پرمعامله‌تر هر بازار (بر اساس ارزش معاملات ۳ ماه).
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'market_summary'))
import quality as Q  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'data', 'quality')
CAP = 2000
MIN_PRICE = {'us': 5, 'jp': 100, 'cn': 3, 'tw': 10}
FA = {'jp': '🇯🇵 ژاپن', 'us': '🇺🇸 آمریکا', 'cn': '🇨🇳 چین', 'tw': '🇹🇼 تایوان'}
D = str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫')
CJK = re.compile(r'[぀-ヿ㐀-鿿가-힯＀-￯]')


def universe(m):
    if m == 'us':
        import gainers
        return gainers.universe()
    if m == 'jp':
        import jp_growth
        return {k: v for k, v in jp_growth.tse_list().items() if k[:4].isdigit() and 1300 <= int(k[:4]) <= 9999}
    if m == 'cn':
        import pandas as pd
        u = {}
        for f in ('universe_sse.csv', 'universe_szse.csv'):
            df = pd.read_csv(os.path.join(ROOT, 'data', 'cn_gainers', f), dtype=str)
            u.update({t: '' for t in df['ticker']})
        return u
    if m == 'tw':
        import tw_growth
        return {k: '' for k in {**tw_growth.twse_list(), **tw_growth.tpex_list()}}


def liquid(tickers, m):
    """۲٬۰۰۰ سهم پرمعامله‌تر با قیمت بالای حداقل (یک دانلود گروهی ۳ ماهه)."""
    import yfinance as yf
    dv = {}
    tl = sorted(tickers)
    for i in range(0, len(tl), 200):
        part = tl[i:i + 200]
        try:
            df = yf.download(part, period='3mo', interval='1d', group_by='ticker', progress=False, threads=True,
                             auto_adjust=True)
        except Exception:
            continue
        for t in part:
            try:
                d = df[t] if len(part) > 1 else df
                c, v = d['Close'].dropna(), d['Volume'].dropna()
                if len(c) > 40 and float(c.iloc[-1]) >= MIN_PRICE[m]:
                    dv[t] = float((c * v.reindex(c.index).fillna(0)).median())
            except Exception:
                pass
    return sorted(dv, key=lambda t: -dv[t])[:CAP]


def scan(m):
    names = universe(m)
    pool = liquid(names, m)
    print(f'{m}: universe {len(names)} liquid {len(pool)}', flush=True)
    res = {}

    def one(t):
        try:
            return t, Q.score(t, m)
        except Exception as e:
            return t, {'error': repr(e)[:80]}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for k, (t, r) in enumerate(ex.map(one, pool), 1):
            res[t] = r
            if k % 200 == 0:
                print(f'{m}: scored {k}/{len(pool)}', flush=True)
                Q.save()
    Q.save()
    ok = {t: r for t, r in res.items() if 'score' in r}
    top = sorted(ok, key=lambda t: (-ok[t]['score'], -ok[t]['known'], (ok[t].get('badges') or {}).get('peg') or 99))[:20]
    # نام: آمریکا و ژاپن از فهرست بورس؛ چین فارسی؛ تایوان انگلیسی (بدون حروف چینی)
    labels = {}
    for t in top:
        n = names.get(t, '')
        if m == 'cn':
            import cn_growth
            n = cn_growth.fa_name(t)
        elif m == 'tw':
            import tw_growth
            n = tw_growth.en_name(t)
        labels[t] = CJK.sub('', str(n)).strip(' -,')[:40]
    dist = {s: sum(1 for r in ok.values() if r['score'] == s) for s in range(6)}
    os.makedirs(OUT, exist_ok=True)
    json.dump({'market': m, 'date': str(dt.date.today()), 'scored': len(ok), 'universe': len(names), 'liquid': len(pool),
               'distribution': dist, 'top': [{'ticker': t, 'name': labels[t], **ok[t]} for t in top]},
              open(os.path.join(OUT, f'weekly_{m}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(m, 'distribution', dist)


def report():
    import summary as S
    L = ['<b>⭐ کیفیت رشد — کل بازار (هفتگی)</b>', Q.LEGEND, '']
    for m in ('jp', 'us', 'cn', 'tw'):
        try:
            v = json.load(open(os.path.join(OUT, f'weekly_{m}.json'), encoding='utf-8'))
        except Exception:
            continue
        if v['date'] < str(dt.date.today() - dt.timedelta(days=2)):
            L += [f"{FA[m]}: داده‌ی این هفته آماده نشد.", '']
            continue
        d5, d4 = v['distribution'].get('5', 0), v['distribution'].get('4', 0)
        L.append(f"<b>{FA[m]}</b> — {str(v['scored']).translate(D)} سهم امتیاز گرفتند؛ "
                 f"⭐۵: {str(d5).translate(D)} سهم، ⭐۴: {str(d4).translate(D)} سهم")
        for i, r in enumerate(v['top'], 1):
            t = r['ticker'].replace('.T', '') if m == 'jp' else r['ticker']
            nm = f" — {html.escape(r['name'])}" if r.get('name') else ''
            peg = (r.get('badges') or {}).get('peg')
            extra = f" | PEG {str(peg).translate(D)}" if peg is not None and 0 < peg < 50 else ''
            L.append(f"{str(i).translate(D)}. <b>{html.escape(t)}</b>{nm} | {Q.label(r)}{extra}")
        L.append('')
    L.append('<i>صرفاً برای بررسی بیشتر؛ توصیه‌ی خرید نیست.</i>')
    msg = '\n'.join(L)
    print(msg)
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    for cid in chats:
        for ch in S.chunks(msg.split('\n')):
            S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})


if __name__ == '__main__':
    report() if sys.argv[1] == 'report' else scan(sys.argv[1])
