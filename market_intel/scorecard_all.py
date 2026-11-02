"""کارنامه‌ی هفتگی یکجا: بازده سیگنال‌های هر ایجنت از روز سیگنال تا آخرین قیمت، در برابر شاخص.

فقط فایل‌های ردیابی موجود در ریپو را می‌خواند (هیچ قیمتی خودش نمی‌سازد):
  - احتمال رشد تکنیکال و بنیادی: data/growth_signal/track.json
  - الگویاب (احتمال آماری):       data/pattern_hunter/track.json
  - سهام هوش مصنوعی:              data/ai_stocks/scorecard.json (سبد در برابر QQQ و SMH)
فقط سیگنال‌هایی که دست‌کم ۷ روز از آنها گذشته در میانگین می‌آیند؛ دوره‌ی کوتاه معنی‌دار نیست و گزارش همین را صریح می‌گوید.
"""
import datetime as dt
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

D = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
MIN_DAYS = 7
FLAG = {'us': '🇺🇸', 'jp': '🇯🇵', 'cn': '🇨🇳', 'tw': '🇹🇼', 'kr': '🇰🇷', 'hk': '🇭🇰', 'in': '🇮🇳', 'gb': '🇬🇧', 'de': '🇩🇪',
        'au': '🇦🇺', 'ca': '🇨🇦'}


def fa(x, signed=True, nd=1):
    if x is None:
        return '؟'
    s = f'{x:+.{nd}f}' if signed else f'{x:.{nd}f}'
    return s.replace('.', '٫').translate(D).replace('+', '+‎')


def load(rel):
    try:
        return json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
    except Exception:
        return None


def days_since(d, today):
    return (today - dt.date.fromisoformat(d)).days


def summarize(items, today):
    """items: [{ticker, date, ret, idx, market}] ← برمی‌گرداند آمار برای سیگنال‌های دست‌کم ۷ روزه."""
    old = [x for x in items if days_since(x['date'], today) >= MIN_DAYS]
    if not old:
        return {'total': len(items), 'n': 0}
    rets = [x['ret'] for x in old]
    beat = [x['ret'] > (x['idx'] if x['idx'] is not None else 0) for x in old]
    idxs = [x['idx'] for x in old if x['idx'] is not None]
    best = max(old, key=lambda x: x['ret'])
    worst = min(old, key=lambda x: x['ret'])
    return {'total': len(items), 'n': len(old), 'avg': st.mean(rets), 'med': st.median(rets), 'avg_idx': st.mean(idxs) if idxs else None,
            'beat': 100 * sum(beat) / len(beat), 'win': 100 * sum(r > 0 for r in rets) / len(rets), 'best': best, 'worst': worst}


def block(title, s):
    if not s['total']:
        return [f'<b>{title}</b>', 'هنوز سیگنالی ثبت نشده.', '']
    if not s['n']:
        return [f'<b>{title}</b>', f"{str(s['total']).translate(D)} سیگنال ثبت شده، ولی هنوز هیچ‌کدام {str(MIN_DAYS).translate(D)} روز کامل نشده؛ نتیجه‌ای نمی‌دهم.", '']
    return [f'<b>{title}</b>',
            f"{str(s['n']).translate(D)} سیگنال سنجیده شد (از {str(s['total']).translate(D)}): میانه {fa(s['med'])}٪ (میانگین {fa(s['avg'])}٪) | "
            f"شاخص همان بازارها {fa(s['avg_idx'])}٪ | بهتر از شاخص: {fa(s['beat'], False, 0)}٪ | مثبت: {fa(s['win'], False, 0)}٪",
            *(['<i>⚠️ یک سیگنال بیش از ۳۰۰٪ دارد؛ میانگین را کج می‌کند و ممکن است خطای داده یا تقسیم سهام باشد، پس به میانه نگاه کنید.</i>']
              if s['best']['ret'] > 300 else []),
            f"🏆 {s['best']['ticker']} {FLAG.get(s['best'].get('market', ''), '')} {fa(s['best']['ret'])}٪ | "
            f"⚠️ {s['worst']['ticker']} {FLAG.get(s['worst'].get('market', ''), '')} {fa(s['worst']['ret'])}٪", '']


def main():
    today = dt.date.today()
    L = [f"<b>📊 کارنامه‌ی هفتگی ایجنت‌ها</b> — {today.strftime('%Y/%m/%d').translate(D)}",
         '<i>بازده از روز سیگنال تا آخرین قیمت، در برابر شاخص همان بازار. فقط سیگنال‌های دست‌کم ۷ روزه حساب می‌شوند.</i>', '']
    # ۱) احتمال رشد تکنیکال و بنیادی
    g = load('data/growth_signal/track.json')
    items = []
    for m, lst in ((g or {}).get('markets') or {}).items():
        for x in lst:
            items.append({'ticker': x['ticker'], 'date': x['date'], 'ret': x['ret_pct'], 'idx': x.get('index_pct'), 'market': m})
    L += block('🚀 احتمال رشد تکنیکال و بنیادی', summarize(items, today))
    # ۲) الگویاب
    p = load('data/pattern_hunter/track.json')
    items = []
    for m, v in ((p or {}).get('markets') or {}).items():
        for x in v.get('items', []):
            items.append({'ticker': x['ticker'], 'date': x['since'], 'ret': x['ret_pct'], 'idx': x.get('index_ret_pct'), 'market': m})
    L += block('🔍 الگویاب (شباهت آماری به قبل از رشد)', summarize(items, today))
    # ۳) سهام هوش مصنوعی
    a = load('data/ai_stocks/scorecard.json')
    if a and a.get('days_measured'):
        b = a.get('benchmarks_pct', {})
        L += ['<b>🤖 سهام هوش مصنوعی</b>',
              f"از {a['first_pick_date'].replace('-', '/').translate(D)} ({str(a['days_measured']).translate(D)} روز معاملاتی): سبد {fa(a['portfolio_pct'])}٪ | "
              f"QQQ {fa(b.get('QQQ'))}٪ | SMH {fa(b.get('SMH'))}٪", '']
    L.append('<i>دوره کوتاه است و نتیجه هنوز معنی‌دار نیست؛ فقط برای پیگیری است و توصیه‌ی خرید نیست.</i>')
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
