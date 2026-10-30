"""گزارش تلگرام «احتمال رشد تکنیکال و بنیادی»: سیگنال‌های امروز + پیگیری همه‌ی سیگنال‌های قبلی."""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MARKETS, ROOT, fa_digits as fa  # noqa: E402
from growth_signal import OUT, SETUP_FA  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

FLAG = {'us': '🇺🇸', 'cn': '🇨🇳', 'in': '🇮🇳', 'jp': '🇯🇵', 'tw': '🇹🇼', 'kr': '🇰🇷', 'hk': '🇭🇰', 'gb': '🇬🇧',
        'de': '🇩🇪', 'ca': '🇨🇦', 'au': '🇦🇺'}
CJK = re.compile(r'[぀-ヿ㐀-鿿가-힯＀-￯]')


def pct(x):
    return '—' if x is None else fa(f'{x:+.1f}') + '٪'


def main():
    today = json.load(open(os.path.join(OUT, 'today.json'), encoding='utf-8'))
    track = json.load(open(os.path.join(OUT, 'track.json'), encoding='utf-8'))['markets']
    e = html.escape
    total = sum(len(v['signals']) for v in today['markets'].values())
    scored = sum(v['scored'] for v in today['markets'].values())
    L = [f"<b>📈 احتمال رشد تکنیکال و بنیادی</b> — {fa(today['date'].replace('-', '/'))}",
         f"<i>{fa(scored)} سهم در {fa(len(today['markets']))} بورس بررسی شد؛ {fa(total)} سهم از هر دو صافی گذشت.</i>",
         '<i>صافی ۱: نمودار و حجم (الگوی آماری قبل از رشد + شکست با حجم، روند منظم، فشردگی نزدیک سقف، برگشت به میانگین). '
         'صافی ۲: صورت مالی سالم، کن‌اسلیم، وارن بافت یا کیفیت رشد ⭐۴ و ⭐۵.</i>', '']
    for m, cfg in MARKETS.items():
        d = today['markets'].get(m)
        if not d or not d['signals']:
            continue
        L.append(f"{FLAG.get(m, '')} <b>{cfg['fa']}</b> (تکنیکال: {fa(d['technical'])} سهم، بنیادی: {fa(len(d['signals']))} سهم)")
        for i, s in enumerate(d['signals'], 1):
            nm = CJK.sub('', s.get('name') or '').strip(' -,')
            L.append(f"{fa(i)}. <b>{e(s['ticker'])}</b>{' — ' + e(nm[:32]) if nm else ''} | قیمت {fa(s['price'])}")
            L.append(f"   📊 {'، '.join(SETUP_FA[x] for x in s['setups'])} | الگوی آماری: {fa(round(s['tech_rank'] * 100))}٪ بالای بازار")
            L.append(f"   ✅ {'، '.join(s['fundamentals'])} {s.get('quality', '')}")
            if s.get('chart'):
                L.append(f"   🗺 نمودار بلندمدت: {e(s['chart'])} (امتیاز {fa(s.get('chart_score', 0))})")
        L.append('')
    if total == 0:
        L += ['امروز هیچ سهمی از هر دو صافی نگذشت.', '']
    else:
        L += ['🖼 <i>نمودار و تحلیل تکنیکال هر سهم (حمایت، مقاومت، سطح ابطال، RSI و حجم) در پیام‌های بعدی آمده است.</i>', '']
    # پیگیری سیگنال‌های قبلی
    items = [dict(x, market=m) for m, xs in track.items() for x in xs]
    if items:
        started = [x for x in items if x['max_pct'] >= 10]
        beat = [x for x in items if x['index_pct'] is not None and x['ret_pct'] > x['index_pct']]
        avg = sum(x['ret_pct'] for x in items) / len(items)
        L.append('<b>📒 پیگیری سیگنال‌های قبلی</b>')
        L.append(f"{fa(len(items))} سیگنال | میانگین بازده {pct(avg)} | بهتر از شاخص: {fa(round(len(beat) / len(items) * 100))}٪ | "
                 f"رشد ≥۱۰٪ شروع شد: {fa(len(started))} سهم")
        ranked = sorted(items, key=lambda x: x['ret_pct'], reverse=True)
        k = min(5, len(ranked))
        def line(x):
            return (f"{FLAG.get(x['market'], '')} <b>{e(x['ticker'])}</b> از {fa(x['date'][5:].replace('-', '/'))}: "
                    f"{pct(x['ret_pct'])} (بیشترین {pct(x['max_pct'])}، کمترین {pct(x['min_pct'])}، شاخص {pct(x['index_pct'])})")
        L.append('')
        L.append('<b>🏆 بهترین سیگنال‌ها از روز سیگنال تا امروز</b>')
        L += [f"{fa(i)}. {line(x)}" for i, x in enumerate(ranked[:k], 1)]
        L.append('<b>⚠️ بدترین سیگنال‌ها از روز سیگنال تا امروز</b>')
        L += [f"{fa(i)}. {line(x)}" for i, x in enumerate(reversed(ranked[-k:]), 1)]
        L.append('')
        L.append('<b>فهرست تازه‌ترین سیگنال‌ها</b>')
        for x in sorted(items, key=lambda x: x['date'], reverse=True)[:25]:
            st = '🚀' if x['max_pct'] >= 10 else ('🔻' if x['ret_pct'] <= -8 else '⏳')
            L.append(f"{st} {FLAG.get(x['market'], '')} <b>{e(x['ticker'])}</b> از {fa(x['date'][5:].replace('-', '/'))}: "
                     f"{pct(x['ret_pct'])} (بیشترین {pct(x['max_pct'])}، شاخص {pct(x['index_pct'])})")
        L.append('<i>🚀 دست‌کم ۱۰٪ رشد از روز سیگنال | 🔻 بیش از ۸٪ افت | ⏳ هنوز در جریان</i>')
    L.append('<i>صرفاً برای بررسی بیشتر؛ توصیه‌ی خرید نیست.</i>')
    msg = '\n'.join(L)
    print(msg)
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    ok = True
    charts = build_charts(today)
    for cid in chats:
        for ch in S.chunks(msg.split('\n')):
            ok &= S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
        for i in range(0, len(charts), 10):          # آلبوم‌های حداکثر ۱۰ تایی
            part = charts[i:i + 10]
            media, files = [], {}
            for k, (png, cap) in enumerate(part):
                media.append({'type': 'photo', 'media': f'attach://p{k}', 'caption': cap[:1024], 'parse_mode': 'HTML'})
                files[f'p{k}'] = open(png, 'rb')
            if len(part) == 1:
                ok &= S.tg_post(tok, cid, 'sendPhoto', data={'chat_id': cid, 'caption': part[0][1][:1024],
                                                             'parse_mode': 'HTML'}, files={'photo': files['p0']})
            else:
                ok &= S.tg_post(tok, cid, 'sendMediaGroup', data={'chat_id': cid, 'media': json.dumps(media, ensure_ascii=False)},
                                files=files)
            for f in files.values():
                f.close()
    return 0 if ok else 2


def build_charts(today):
    """برای هر سیگنال امروز: نمودار PNG + کپشن تحلیل تکنیکال."""
    import tempfile
    import tech_chart as TC
    sig = [(m, s) for m in MARKETS for s in (today['markets'].get(m) or {}).get('signals', [])]
    if not sig:
        return []
    try:
        data = TC.download([s['ticker'] for _, s in sig])
    except Exception as ex:
        print('⚠️ chart download', ex, file=sys.stderr)
        return []
    tmp, out = tempfile.mkdtemp(), []
    for m, s in sig:
        d = data.get(s['ticker'])
        if d is None:
            continue
        try:
            a = TC.analyze(d)
            png = os.path.join(tmp, s['ticker'].replace('.', '_') + '.png')
            TC.render(d, s, a, png)
            out.append((png, TC.caption(s, a, FLAG.get(m, ''))))
        except Exception as ex:
            print('⚠️ chart', s['ticker'], ex, file=sys.stderr)
    return out


if __name__ == '__main__':
    sys.exit(main())
