"""خودسنجی ماهانه‌ی «احتمال رشد»: هر فیلتر، الگو و بورس چقدر سود داده و کدام ضعیف است.

ورودی: data/growth_signal/track.json (بازده هر سیگنال تا امروز، با حد ضرر ۸٪) + history.csv (فیلترهای روز سیگنال).
خروجی: data/growth_signal/review.json + پیام تلگرام (فقط شنبه‌ی اول هر ماه، یا با --force).
پیشنهادها فقط پیشنهادند؛ تغییر قاعده‌ها با تأیید مالک انجام می‌شود.
"""
import datetime as dt
import html
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MARKETS, ROOT, fa_digits as fa  # noqa: E402
from growth_signal import OUT, SETUP_FA  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

MIN_N = 10        # حداقل تعداد سیگنال برای قضاوت درباره‌ی یک گروه
WEAK = -3.0       # گروهی که میانگین بازده اضافه‌اش (نسبت به شاخص) زیر −۳٪ باشد ضعیف است


def pct(x):
    return fa(f'{x:+.1f}') + '٪'


def load():
    t = json.load(open(os.path.join(OUT, 'track.json'), encoding='utf-8'))
    d = pd.DataFrame([dict(x, market=m) for m, xs in t['markets'].items() for x in xs])
    h = pd.read_csv(os.path.join(OUT, 'history.csv')).drop_duplicates(['market', 'ticker'], keep='first')
    d = d.merge(h[['market', 'ticker', 'setups', 'fundamentals', 'quality', 'tech_rank']], on=['market', 'ticker'], how='left')
    d['excess'] = d.ret_pct - d.index_pct.fillna(0)
    d['n_fund'] = d.fundamentals.fillna('').str.count(r'\|') + 1
    d['n_setup'] = d.setups.fillna('').str.count(r'\|') + 1
    d['rank_band'] = pd.cut(d.tech_rank, [0, .8, .9, 1.0], labels=['تا ۸۰٪', '۸۰ تا ۹۰٪', 'بالای ۹۰٪']).astype(str)
    return d


def groups(d):
    out = []

    def add(kind, label, sub):
        if len(sub):
            out.append({'kind': kind, 'label': label, 'n': int(len(sub)), 'ret': round(float(sub.ret_pct.mean()), 2),
                        'excess': round(float(sub.excess.mean()), 2), 'win': round(float((sub.ret_pct > 0).mean() * 100)),
                        'stopped': int(sub.get('stopped', pd.Series(dtype=bool)).fillna(False).sum())})
    for m, g in d.groupby('market'):
        add('بورس', MARKETS.get(m, {}).get('fa', m), g)
    for k, fa_ in SETUP_FA.items():
        add('الگو', fa_, d[d.setups.fillna('').str.contains(k)])
    for f in ('صورت مالی', 'کن‌اسلیم', 'بافت', 'کیفیت رشد'):
        add('فیلتر بنیادی', f, d[d.fundamentals.fillna('').str.contains(f)])
    for n, g in d.groupby('n_fund'):
        add('تعداد فیلتر بنیادی', str(n), g)
    for b, g in d.groupby('rank_band'):
        add('رتبه‌ی الگوی آماری', b, g)
    return out


def main():
    force = '--force' in sys.argv
    today = dt.date.today()
    d = load()
    G = groups(d)
    weak = [g for g in G if g['n'] >= MIN_N and g['excess'] < WEAK]
    strong = [g for g in G if g['n'] >= MIN_N and g['excess'] > -WEAK]
    rev = {'date': str(today), 'signals': int(len(d)), 'mean_ret': round(float(d.ret_pct.mean()), 2),
           'mean_excess': round(float(d.excess.mean()), 2), 'stopped': int(d.get('stopped', pd.Series(dtype=bool)).fillna(False).sum()),
           'groups': G, 'weak': weak, 'strong': strong}
    json.dump(rev, open(os.path.join(OUT, 'review.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not force and not (today.weekday() == 5 and today.day <= 7):
        print('review saved; Telegram only on the first Saturday of the month')
        return 0
    e = html.escape
    L = [f"<b>🧪 خودسنجی ماهانه‌ی «احتمال رشد»</b> — {fa(str(today).replace('-', '/'))}",
         f"{fa(len(d))} سیگنال | میانگین بازده {pct(rev['mean_ret'])} | نسبت به شاخص {pct(rev['mean_excess'])} | "
         f"🛑 حد ضرر خورد: {fa(rev['stopped'])}", '']
    L.append('<b>⚠️ گروه‌های ضعیف</b> (دست‌کم ۱۰ سیگنال و بیش از ۳٪ عقب‌تر از شاخص):')
    L += [f"• {e(g['kind'])}: {e(g['label'])} — {fa(g['n'])} سیگنال، {pct(g['ret'])} (نسبت به شاخص {pct(g['excess'])})"
          for g in sorted(weak, key=lambda g: g['excess'])] or ['• گروه ضعیف مشخصی نبود.']
    L.append('<b>✅ گروه‌های قوی</b> (بیش از ۳٪ جلوتر از شاخص):')
    L += [f"• {e(g['kind'])}: {e(g['label'])} — {fa(g['n'])} سیگنال، {pct(g['ret'])} (نسبت به شاخص {pct(g['excess'])})"
          for g in sorted(strong, key=lambda g: -g['excess'])] or ['• هنوز گروه قوی مشخصی نبود.']
    if weak:
        L += ['', '👉 <b>پیشنهاد:</b> گروه‌های ضعیف بالا محدود یا حذف شوند. تغییر فقط با تأیید شما انجام می‌شود؛ '
                  'برای اعمال، در گفتگو بنویسید «پیشنهاد خودسنجی را اجرا کن».']
    L.append('<i>نمونه‌ی کوچک (کمتر از ۳۰ سیگنال) را با احتیاط بخوانید.</i>')
    msg = '\n'.join(L)
    print(msg)
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    for cid in [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']:
        for ch in S.chunks(msg.split('\n')):
            S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0


if __name__ == '__main__':
    sys.exit(main())
