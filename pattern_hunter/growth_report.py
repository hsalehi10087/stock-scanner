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


def entry_lines(i, s):
    """شرح هر سهم برگزیده؛ هم در پیام متنی و هم در کپشن نمودارش."""
    e = html.escape
    nm = CJK.sub('', s.get('name') or '').strip(' -,')
    out = [f"{fa(i)}. <b>{e(s['ticker'])}</b>{' — ' + e(nm[:32]) if nm else ''} | قیمت {fa(s['price'])}",
           f"   📊 {'، '.join(SETUP_FA[x] for x in s['setups'])} | الگوی آماری: جزو {fa(max(1, 100 - round(s['tech_rank'] * 100)))}٪ برتر بازار",
           f"   ✅ {'، '.join(s['fundamentals'])} {s.get('quality', '')}"]
    if s.get('chart'):
        out.append(f"   🗺 نمودار بلندمدت: {e(s['chart'])} (امتیاز {fa(s.get('chart_score', 0))})")
    return out


def main():
    today = json.load(open(os.path.join(OUT, 'today.json'), encoding='utf-8'))
    track = json.load(open(os.path.join(OUT, 'track.json'), encoding='utf-8'))['markets']
    e = html.escape
    total = sum(len(v['signals']) for v in today['markets'].values())
    scored = sum(v['scored'] for v in today['markets'].values())
    L = [f"<b>📈 احتمال رشد تکنیکال و بنیادی</b> — {fa(today['date'].replace('-', '/'))}",
         f"<i>{fa(scored)} سهم در {fa(len(today['markets']))} بورس بررسی شد؛ {fa(total)} سهم از هر دو صافی گذشت.</i>",
         '<i>صافی ۱: نمودار و حجم (الگوی آماری قبل از رشد + شکست با حجم، روند منظم، فشردگی نزدیک سقف، برگشت به میانگین). '
         'صافی ۲: صورت مالی سالم، کن‌اسلیم، وارن بافت یا کیفیت رشد ⭐۴ و ⭐۵.</i>',
         '<i>«الگوی آماری: جزو ۸٪ برتر بازار» یعنی امتیاز این سهم از ۹۲٪ سهم‌های همان بورس در همان روز بیشتر است؛ '
         'یعنی بیشتر از بقیه شبیه سهم‌هایی است که در ۱۰ سال گذشته ظرف ۱۲ ماه دو برابر شده‌اند. '
         'عدد کوچک‌تر بهتر است (جزو ۱٪ برتر = شبیه‌ترین). این عدد احتمال رشد نیست و نسبی است: '
         'در روزی که کل بازار ضعیف است، سهم برتر هم فقط از بقیه بهتر است.</i>', '']
    for m, cfg in MARKETS.items():
        d = today['markets'].get(m)
        if not d or not d['signals']:
            continue
        L.append(f"{FLAG.get(m, '')} <b>{cfg['fa']}</b> (تکنیکال: {fa(d['technical'])} سهم، بنیادی: {fa(len(d['signals']))} سهم)")
        for i, s in enumerate(d['signals'], 1):
            L += entry_lines(i, s)
        L.append('')
    if total == 0:
        L += ['امروز هیچ سهمی از هر دو صافی نگذشت.', '']
    else:
        L += ['🖼 <i>نمودار و تحلیل تکنیکال هر سهم (حمایت، مقاومت، سطح ابطال، RSI و حجم) در پیام‌های بعدی آمده است؛ هر نمودار با شرح همان سهم و به همین ترتیب.</i>', '']
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
        for png, cap in charts:                     # هر نمودار جدا، با شرح کامل همان سهم در کپشن، به ترتیب فهرست
            with open(png, 'rb') as f:
                ok &= S.tg_post(tok, cid, 'sendPhoto', data={'chat_id': cid, 'caption': cap, 'parse_mode': 'HTML'},
                                files={'photo': f})
    return 0 if ok else 2


def build_charts(today):
    """برای هر سیگنال امروز: نمودار PNG + کپشن تحلیل تکنیکال."""
    import tempfile
    import tech_chart as TC
    sig = [(m, i, s) for m in MARKETS for i, s in enumerate((today['markets'].get(m) or {}).get('signals', []), 1)]
    if not sig:
        return []
    try:
        data = TC.download([s['ticker'] for _, _, s in sig])
    except Exception as ex:
        print('⚠️ chart download', ex, file=sys.stderr)
        return []
    tmp, out = tempfile.mkdtemp(), []
    for m, i, s in sig:
        d = data.get(s['ticker'])
        if d is None:
            continue
        try:
            a = TC.analyze(d)
            png = os.path.join(tmp, s['ticker'].replace('.', '_') + '.png')
            TC.render(d, s, a, png)
            n = len(today['markets'][m]['signals'])
            head = [f"{FLAG.get(m, '')} <b>{MARKETS[m]['fa']}</b> — سهم برتر {fa(i)} از {fa(n)}"] + entry_lines(i, s)
            tech = ['', '<b>🔍 تحلیل تکنیکال</b>'] + TC.caption(s, a).split('\n')[1:]
            lines = head + tech
            while len('\n'.join(lines)) > 1024 and len(lines) > len(head) + 2:   # سقف کپشن تلگرام
                lines.pop()
            out.append((png, '\n'.join(lines)))
        except Exception as ex:
            print('⚠️ chart', s['ticker'], ex, file=sys.stderr)
    return out


if __name__ == '__main__':
    sys.exit(main())
