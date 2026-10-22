"""الگویاب — گزارش روزانه به تلگرام: پیشنهادهای امروز هر بازار، سنجش گذشته‌ی الگو، و نتیجه‌ی پیشنهادهای قبلی."""
import datetime as dt
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FA_FEAT, MARKETS, OUT, ROOT, fa_digits as fa  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

FLAG = {'us': '🇺🇸', 'cn': '🇨🇳', 'in': '🇮🇳', 'jp': '🇯🇵', 'tw': '🇹🇼'}


def pct(x):
    return '—' if x is None else fa(f'{x:+.1f}') + '٪'


def main():
    today = json.load(open(os.path.join(OUT, 'today.json'), encoding='utf-8'))
    track = json.load(open(os.path.join(OUT, 'track.json'), encoding='utf-8'))['markets']
    e = html.escape
    L = [f"<b>🔍 الگویاب</b> — {fa(today['date'].replace('-', '/'))}",
         '<i>سهم‌هایی که امروز بیشترین شباهت را به الگوی «قبل از دو برابر شدن در ۱۲ ماه» دارند (الگو از ۱۰ سال گذشته)</i>', '']
    weekly = dt.date.today().weekday() == 5   # شنبه‌ها: توضیح الگو
    for m, cfg in MARKETS.items():
        d = today['markets'].get(m)
        if not d:
            continue
        prof = {}
        try:
            prof = json.load(open(os.path.join(OUT, f'profile_{m}.json'), encoding='utf-8'))
        except Exception:
            pass
        L.append(f"{FLAG[m]} <b>{cfg['fa']}</b> (از {fa(d['scored'])} سهم، داده‌ی {fa(d['data_date'].replace('-', '/'))})")
        for p in d['picks']:
            nm = f" — {e(p['name'])}" if p.get('name') else ''
            L.append(f"{fa(p['rank'])}. <b>{e(p['ticker'])}</b>{nm} | قیمت {fa(p['price'])} | امتیاز الگو {fa(round(p['prob'] * 100))} "
                     f"| ۶ ماه {pct(p['r6m'])}")
        o = prof.get('out_of_sample')
        if o:
            L.append(f"🧪 سنجش گذشته ({fa(o['period'].replace('-', '/'))}): از ۱۰ انتخاب هر هفته {fa(o['top10_hit_rate_pct'])}٪ "
                     f"در ۱۲ ماه دو برابر شدند؛ میانگین بازار {fa(o['base_rate_pct'])}٪ "
                     f"(بازده میانه {pct(o['top10_median_fwd_12m_pct'])} در برابر {pct(o['all_median_fwd_12m_pct'])})")
        if weekly and prof.get('importance'):
            parts = []
            for f, _ in prof['importance'][:3]:
                w, r = prof['profile'][f]['winners_median'], prof['profile'][f]['others_median']
                pc = f not in ('log_price', 'log_dollar_vol', 'vol_ratio', 'volu_ratio')
                fmt = (lambda x: fa(f'{x * 100:.0f}') + '٪') if pc else (lambda x: fa(f'{x:.2f}'))
                parts.append(f"{FA_FEAT[f]} {fmt(w)} در برابر {fmt(r)}")
            L.append('📐 الگوی برنده‌ها: ' + '؛ '.join(parts))
        t = track.get(m) or {}
        if t.get('evaluated'):
            b = t.get('best') or {}
            L.append(f"📒 پیشنهادهای قبلی: {fa(t['evaluated'])} سهم، میانگین {pct(t['avg_ret_pct'])} در برابر شاخص "
                     f"{pct(t['avg_index_pct'])}؛ بهتر از شاخص: {fa(int(t['beat_index_pct']))}٪"
                     + (f"؛ بهترین {e(b['ticker'])} {pct(b['ret_pct'])}" if b else ''))
        elif t.get('picks_total'):
            L.append(f"📒 {fa(t['picks_total'])} پیشنهاد در تاریخچه ثبت شد؛ نتیجه بعد از یک هفته گزارش می‌شود.")
        L.append('')
    L.append('<i>الگو فقط از رفتار قیمت و حجم است و فهرست سهم‌ها فقط شرکت‌های فعلی را دارد (شرکت‌های حذف‌شده نیستند)؛ '
             'پیشنهاد خرید نیست.</i>')
    msg = '\n'.join(L)
    print(msg)
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    ok = True
    for cid in chats:
        for ch in S.chunks(msg.split('\n')):
            ok &= S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
