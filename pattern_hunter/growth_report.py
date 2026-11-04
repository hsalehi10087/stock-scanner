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
sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
import intrinsic as IV  # noqa: E402

FLAG = {'us': '🇺🇸', 'cn': '🇨🇳', 'in': '🇮🇳', 'jp': '🇯🇵', 'tw': '🇹🇼', 'kr': '🇰🇷', 'hk': '🇭🇰', 'gb': '🇬🇧',
        'de': '🇩🇪', 'ca': '🇨🇦', 'au': '🇦🇺'}
MAX_CHARTS = 10
CJK = re.compile(r'[぀-ヿ㐀-鿿가-힯＀-￯]')


def pct(x):
    return '—' if x is None else fa(f'{x:+.1f}') + '٪'


def entry_lines(i, s):
    """شرح هر سهم برگزیده؛ هم در پیام متنی و هم در کپشن نمودارش."""
    e = html.escape
    nm = CJK.sub('', s.get('name') or '').strip(' -,')
    out = [f"{fa(i)}. <b>{e(s['ticker'])}</b>{' — ' + e(nm[:32]) if nm else ''} | قیمت {fa(s['price'])}",
           f"   📊 {'، '.join(SETUP_FA[x] for x in s['setups'])} | الگوی آماری: جزو {fa(max(1, 100 - round(s['tech_rank'] * 100)))}٪ برتر بازار",
           f"   ✅ {'، '.join(s['fundamentals'])} {s.get('quality', '')}",
           f"   📈 سود خالص {fa(s.get('profit_streak', 2))} فصل پیاپی بالا رفته" + (
               ' (فصل قبل‌تر هم افزایش داشته ✅)' if s.get('profit_more') else '') + f" ({s.get('profit_basis') or ''})",
           f"   💎 {IV.label(s.get('iv'))}"]
    if s.get('chart'):
        out.append(f"   🗺 نمودار بلندمدت: {e(s['chart'])} (امتیاز {fa(s.get('chart_score', 0))})")
    return out


def main():
    today = json.load(open(os.path.join(OUT, 'today.json'), encoding='utf-8'))
    track = json.load(open(os.path.join(OUT, 'track.json'), encoding='utf-8'))['markets']
    e = html.escape
    for v in today['markets'].values():                 # ارزش ذاتی هر سیگنال
        for sg in v['signals']:
            try:
                sg['iv'] = IV.value(sg['ticker'], sg['price'])
            except Exception:
                sg['iv'] = None
    IV.save()
    total = sum(len(v['signals']) for v in today['markets'].values())
    scored = sum(v['scored'] for v in today['markets'].values())
    L = [f"<b>📈 احتمال رشد تکنیکال و بنیادی</b> — {fa(today['date'].replace('-', '/'))}",
         f"<i>{fa(scored)} سهم در {fa(len(today['markets']))} بورس بررسی شد؛ {fa(total)} سهم از هر دو صافی گذشت.</i>",
         '<i>صافی ۱: نمودار و حجم (الگوی آماری قبل از رشد + شکست با حجم، روند منظم، فشردگی نزدیک سقف، برگشت به میانگین). '
         'صافی ۲: دست‌کم ۲ تا از صورت مالی سالم، کن‌اسلیم، وارن بافت یا کیفیت رشد ⭐۴ و ⭐۵. '
         'کنار گذاشته می‌شوند: سهم‌های داغ (بیش از ۲۰٪ بالای میانگین ۵۰ روزه یا RSI بالای ۷۵) و سهم‌هایی که تا ۱۰ روز آینده گزارش فصلی دارند. '
         'وقتی شاخص یک بورس زیر میانگین ۵۰ روزه است، حداکثر ۲ سیگنال از آن بورس می‌آید. پیگیری با حد ضرر ۸٪.</i>',
         '<i>«الگوی آماری: جزو ۸٪ برتر بازار» یعنی امتیاز این سهم از ۹۲٪ سهم‌های همان بورس در همان روز بیشتر است؛ '
         'یعنی بیشتر از بقیه شبیه سهم‌هایی است که در ۱۰ سال گذشته ظرف ۱۲ ماه دو برابر شده‌اند. '
         'عدد کوچک‌تر بهتر است (جزو ۱٪ برتر = شبیه‌ترین). این عدد احتمال رشد نیست و نسبی است: '
         'در روزی که کل بازار ضعیف است، سهم برتر هم فقط از بقیه بهتر است.</i>', IV.LEGEND, '']
    for m, cfg in MARKETS.items():
        d = today['markets'].get(m)
        if not d or not d['signals']:
            continue
        weak = '' if d.get('market_up50', True) else ' | 🌧 بازار ضعیف (شاخص زیر میانگین ۵۰): حداکثر ۲ سیگنال'
        L.append(f"{FLAG.get(m, '')} <b>{cfg['fa']}</b> (تکنیکال: {fa(d['technical'])} سهم، بنیادی: {fa(len(d['signals']))} سهم){weak}")
        for i, s in enumerate(d['signals'], 1):
            L += entry_lines(i, s)
        L.append('')
    weak_all = [MARKETS[m]['fa'] for m, d in today['markets'].items() if m in MARKETS and not d.get('market_up50', True)]
    if weak_all:
        L += [f"<i>🌧 بورس‌های با شاخص زیر میانگین ۵۰ روزه (سیگنال محدود): {'، '.join(weak_all)}</i>", '']
    drops = {}
    for d in today['markets'].values():
        for k, v in (d.get('dropped') or {}).items():
            drops[k] = drops.get(k, 0) + v
    if any(drops.values()):
        L += [f"<i>کنار گذاشته شد: داغ {fa(drops.get('ext', 0) + drops.get('rsi', 0))}، گزارش فصلی نزدیک {fa(drops.get('earn', 0))}، "
              f"کمتر از ۲ فیلتر بنیادی {fa(drops.get('fund', 0))} سهم</i>", '']
    if total == 0:
        L += ['امروز هیچ سهمی از هر دو صافی نگذشت.', '']
    else:
        L += ['🖼 <i>نمودار و تحلیل تکنیکال هر سهم (حمایت، مقاومت، سطح ابطال، RSI و حجم) برای ۱۰ سهم برتر در پیام‌های بعدی آمده است؛ هر نمودار با شرح همان سهم و به همین ترتیب.</i>', '']
    # پیگیری سیگنال‌های قبلی
    items = [dict(x, market=m) for m, xs in track.items() for x in xs]
    if items:
        started = [x for x in items if x['max_pct'] >= 10]
        stopped = [x for x in items if x.get('stopped')]
        beat = [x for x in items if x['index_pct'] is not None and x['ret_pct'] > x['index_pct']]
        avg = sum(x['ret_pct'] for x in items) / len(items)
        L.append('<b>📒 پیگیری سیگنال‌های قبلی</b>')
        L.append(f"{fa(len(items))} سیگنال | میانگین بازده {pct(avg)} | بهتر از شاخص: {fa(round(len(beat) / len(items) * 100))}٪ | "
                 f"رشد ≥۱۰٪ شروع شد: {fa(len(started))} سهم | 🛑 حد ضرر ۸٪ خورد: {fa(len(stopped))} سهم")
        ranked = sorted(items, key=lambda x: x['ret_pct'], reverse=True)
        k = min(5, len(ranked))
        def line(x):
            return (f"{'🛑 ' if x.get('stopped') else ''}{FLAG.get(x['market'], '')} <b>{e(x['ticker'])}</b> از {fa(x['date'][5:].replace('-', '/'))}: "
                    f"{pct(x['ret_pct'])} (بیشترین {pct(x['max_pct'])}، کمترین {pct(x['min_pct'])}، شاخص {pct(x['index_pct'])})")
        L.append('')
        L.append('<b>🏆 بهترین سیگنال‌ها از روز سیگنال تا امروز</b>')
        L += [f"{fa(i)}. {line(x)}" for i, x in enumerate(ranked[:k], 1)]
        L.append('<b>⚠️ بدترین سیگنال‌ها از روز سیگنال تا امروز</b>')
        L += [f"{fa(i)}. {line(x)}" for i, x in enumerate(reversed(ranked[-k:]), 1)]
        L.append('')
        L.append('<b>فهرست تازه‌ترین سیگنال‌ها</b>')
        for x in sorted(items, key=lambda x: x['date'], reverse=True)[:25]:
            st = '🛑' if x.get('stopped') else ('🚀' if x['max_pct'] >= 10 else '⏳')
            L.append(f"{st} {FLAG.get(x['market'], '')} <b>{e(x['ticker'])}</b> از {fa(x['date'][5:].replace('-', '/'))}: "
                     f"{pct(x['ret_pct'])} (بیشترین {pct(x['max_pct'])}، شاخص {pct(x['index_pct'])})")
        L.append('<i>🚀 دست‌کم ۱۰٪ رشد از روز سیگنال | 🛑 حد ضرر ۸٪ خورد و سیگنال بسته شد | ⏳ هنوز در جریان</i>')
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
    # فقط ۱۰ سهم برتر نمودار می‌گیرند: بیشترین فیلتر بنیادی، بعد کیفیت رشد، بعد رتبه‌ی الگوی آماری
    def strength(x):
        q = re.search(r'⭐(\S)', x[2].get('quality') or '')
        qn = int(q.group(1).translate(str.maketrans('۰۱۲۳۴۵', '012345'))) if q else 0
        return (len(x[2]['fundamentals']), qn, x[2]['tech_rank'])
    top = sorted(sig, key=strength, reverse=True)[:MAX_CHARTS]
    sig = [x for x in sig if x in top]
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
