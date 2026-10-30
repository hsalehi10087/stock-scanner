"""الگویاب — گزارش روزانه به تلگرام: پیشنهادهای امروز هر بازار، سنجش گذشته‌ی الگو، و نتیجه‌ی پیشنهادهای قبلی."""
import datetime as dt
import html
import re
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FA_FEAT, MARKETS, OUT, ROOT, fa_digits as fa  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

FLAG = {'us': '🇺🇸', 'cn': '🇨🇳', 'in': '🇮🇳', 'jp': '🇯🇵', 'tw': '🇹🇼', 'kr': '🇰🇷', 'hk': '🇭🇰', 'gb': '🇬🇧',
        'de': '🇩🇪', 'ca': '🇨🇦', 'au': '🇦🇺'}


def pct(x):
    return '—' if x is None else fa(f'{x:+.1f}') + '٪'


def main():
    today = json.load(open(os.path.join(OUT, 'today.json'), encoding='utf-8'))
    track = json.load(open(os.path.join(OUT, 'track.json'), encoding='utf-8'))['markets']
    e = html.escape
    L = [f"<b>🔍 الگویاب</b> — {fa(today['date'].replace('-', '/'))}",
         '<i>سهم‌هایی که هم به الگوی «قبل از دو برابر شدن در ۱۲ ماه» (۱۰ سال گذشته) شبیه‌اند و هم دست‌کم با یکی از روش‌های صورت مالی سالم، کن‌اسلیم یا وارن بافت همخوانی دارند</i>', '']
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
        L.append(f"{FLAG[m]} <b>{cfg['fa']}</b> (از {fa(d['scored'])} سهم؛ {fa(d.get('checked', 0))} نامزد الگو بررسی بنیادی شد، "
                 f"{fa(d.get('dropped', 0))} حذف شد)")
        if not d['picks']:
            L.append('امروز هیچ نامزد الگو با صورت مالی، کن‌اسلیم یا روش بافت همخوانی نداشت.')
        for p in d['picks']:
            clean = re.sub(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]', '', p.get('name') or '').strip(' -,')
            nm = f" — {e(clean)}" if clean else ''
            ok = '، '.join(p.get('passed', []))
            L.append(f"{fa(p['rank'])}. <b>{e(p['ticker'])}</b>{nm} | قیمت {fa(p['price'])} | امتیاز الگو {fa(round(p['prob'] * 100))}")
            L.append(f"   ✅ {ok} | صورت مالی {fa(p.get('health', '?'))}، کن‌اسلیم {fa(p.get('canslim', '?'))}، بافت {fa(p.get('buffett', '?'))} | {p.get('quality', '')}")
            if p.get('chart'):
                L.append(f"   📈 نمودار بلندمدت: {e(p['chart'])} (امتیاز {fa(p.get('chart_score', 0))}، روند {e(p.get('chart_trend', ''))})")
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
