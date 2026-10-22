"""شکارچی روش — گزارش روزانه‌ی ۵ خطی به تلگرام + تصویر جدول همه‌ی روش‌ها."""
import datetime as dt
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

OUT = os.path.join(ROOT, 'data', 'strategy_hunter')
FA = str.maketrans('0123456789.-', '۰۱۲۳۴۵۶۷۸۹٫−')


def fa(x):
    return str(x).translate(FA)


def pct(x):
    return fa(f'{x:+.1f}') + '٪'


def load():
    res = json.load(open(os.path.join(OUT, 'results.json'), encoding='utf-8'))['results']
    inbox = []
    p = os.path.join(OUT, 'inbox.jsonl')
    if os.path.exists(p):
        inbox = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
    return res, inbox


def render(rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    heads = ['METHOD', 'MARKET', 'CLAIMED', 'TEST CAGR', 'MAX DD', 'BUY&HOLD', 'LIVE $1000', 'VERDICT']
    cells = []
    for r in rows:
        o, b = r.get('out_sample') or {}, r.get('buyhold_out_sample') or {}
        v = r.get('verdict', '')
        cells.append([(r.get('name') or r['id'])[:30], f"{r.get('asset_class', '')} {','.join(r.get('symbols') or [])[:12]}",
                      str(r.get('claimed_return') or '-')[:14],
                      f"{o.get('cagr', 0):+.1f}%" if o else '-', f"{o.get('max_dd', 0):.0f}%" if o else '-',
                      f"{b.get('cagr', 0):+.1f}%" if b else '-',
                      f"${r['forward_usd']:,.0f}" if r.get('forward_usd') else '-',
                      'PASS' if v == 'قبول' else ('N/A' if v.startswith('غیرقابل') or v.startswith('خطا') else 'FAIL')])
    fig, ax = plt.subplots(figsize=(13, 0.42 * (len(cells) + 1) + 0.5))
    ax.axis('off')
    t = ax.table(cellText=cells, colLabels=heads, loc='center', cellLoc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(9.5)
    t.scale(1, 1.45)
    widths = [0.22, 0.13, 0.11, 0.1, 0.08, 0.1, 0.1, 0.08]
    for (i, j), cell in t.get_celld().items():
        cell.set_width(widths[j])
        cell.set_edgecolor('#9ca3af')
        txt = cell.get_text()
        txt.set_fontweight('bold')
        if i == 0:
            cell.set_facecolor('#1f2937')
            txt.set_color('white')
        else:
            cell.set_facecolor('#f3f4f6' if i % 2 else 'white')
            if j == 7:
                txt.set_color({'PASS': '#15803d', 'FAIL': '#b91c1c'}.get(txt.get_text(), '#6b7280'))
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    res, inbox = load()
    now = dt.datetime.now(dt.timezone.utc)
    day_ago = (now - dt.timedelta(days=1)).isoformat()
    today = now.date()
    new_claims = sum(1 for x in inbox if x.get('found_at', '') >= day_ago)
    rows = sorted(res.values(), key=lambda r: (r.get('verdict') != 'قبول', -(r.get('out_sample') or {}).get('sharpe', -9)))
    fresh = [r for r in res.values() if r.get('added') and str(r['added'])[:10] >= str(today - dt.timedelta(days=1))]
    tested = [r for r in rows if r.get('out_sample')]
    passed = [r for r in tested if r.get('verdict') == 'قبول']

    tested_new = [r for r in fresh if r.get('out_sample')]
    l1 = (f"🔎 <b>شکارچی روش</b> — {fa(str(today).replace('-', '/'))}: {fa(new_claims)} ادعای تازه پیدا شد؛ "
          f"{fa(len(fresh))} مورد بررسی شد ({fa(len(tested_new))} آزموده، {fa(len(fresh) - len(tested_new))} غیرقابل آزمون).")

    def short(r):
        v = r.get('verdict', '')
        return '✅ قبول' if v == 'قبول' else '❌ ' + v.replace('رد: ', '')
    l2 = ('🧪 نتیجه‌ی امروز: ' + '؛ '.join(f"{r.get('name_fa') or r.get('name')} {short(r)}" for r in tested_new[:3])
          if tested_new else '🧪 امروز ادعای تازه‌ای با قانون عددی قابل آزمون نبود.')
    if passed:
        b = passed[0]
        l3 = (f"🏆 بهترین روش: {b.get('name_fa') or b.get('name')} — سالانه {pct(b['out_sample']['cagr'])}، "
              f"ریزش {pct(b['out_sample']['max_dd'])}؛ ۱٬۰۰۰ دلار زنده ← {fa(round(b['forward_usd']))} دلار")
    else:
        l3 = '🏆 هنوز هیچ روشی آزمون واقعی را قبول نشده است.'
    if tested:
        ex = max(tested, key=lambda r: (r.get('full') or {}).get('total', -999))
        l4 = (f"📊 جدول: {fa(len(tested))} آزموده، {fa(len(passed))} قبول | نمونه: «{ex.get('name_fa') or ex.get('name')}» "
              f"ادعا {ex.get('claimed_return') or '؟'}، واقعی {pct(ex['full']['total'])} کل دوره، "
              f"نگه‌داشتن ساده {pct(ex['buyhold_full']['total'])}.")
    else:
        l4 = '📊 هنوز روشی در جدول نیست.'
    l5 = '👉 تصمیم با شماست: برای اجرای یک روش قبول‌شده در حساب آزمایشی، اسمش را در گفتگو بنویسید.'
    caption = '\n'.join([l1, l2, l3, l4, l5])
    print(caption)

    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    if not token or not chats:
        return 0
    ok = True
    if rows:
        png = os.path.join(tempfile.mkdtemp(), 'hunter.png')
        render(rows[:25], png)
        for cid in chats:
            with open(png, 'rb') as f:
                ok &= S.tg_post(token, cid, 'sendPhoto', data={'chat_id': cid, 'caption': caption[:1024], 'parse_mode': 'HTML'},
                                files={'photo': f})
    else:
        for cid in chats:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': caption, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
