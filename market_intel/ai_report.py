"""گزارش روزانه‌ی «سهام هوش مصنوعی با آینده‌ی درخشان» — از data/ai_stocks/latest.json که کار روزانه‌ی Claude می‌نویسد."""
import datetime as dt
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_summary'))
import summary as S  # noqa: E402

P = os.path.join(ROOT, 'data', 'ai_stocks', 'latest.json')
D = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    try:
        v = json.load(open(P, encoding='utf-8'))
    except Exception:
        print('no latest.json')
        return 0
    if v.get('date') != str(dt.datetime.now(dt.timezone.utc).date()):
        print('latest.json is not from today; nothing sent')
        return 0
    e = html.escape
    L = [f"<b>🤖 گزارش سهام هوش مصنوعی</b> — {v['date'].replace('-', '/').translate(D)}",
         f"<i>{e(v.get('method_fa', ''))}</i>", '']
    if v.get('market_fa'):
        L += [f"🌐 <b>فضای بازار AI:</b> {e(v['market_fa'])}", '']
    for i, p in enumerate(v.get('picks', [])[:5], 1):
        L.append(f"<b>{str(i).translate(D)}. {e(p['ticker'])} — {e(p.get('name', ''))}</b> ({e(p.get('segment_fa', ''))})")
        L.append(f"📊 {e(p.get('numbers_fa', ''))}")
        L.append(f"🚀 چرا: {e(p.get('thesis_fa', ''))}")
        if p.get('news_fa'):
            src = p.get('news_url')
            L.append(f"📰 {e(p['news_fa'])}" + (f' (<a href="{e(src)}">خبر</a>)' if src else ''))
        L.append(f"⚠️ ریسک: {e(p.get('risk_fa', ''))}")
        L.append('')
    if v.get('dropped_fa'):
        L += [f"🔻 <b>از فهرست بیرون رفت:</b> {e(v['dropped_fa'])}", '']
    L.append('<i>فقط درصد کمی از سهم‌ها در یک دهه ۱۰ برابر می‌شوند و بیشتر سهم‌های پرهیجان این‌طور نمی‌شوند؛ این فهرست سهم‌هایی است که شرایطش را بیشتر از بقیه دارند، '
             'نه پیش‌بینی قطعی و نه توصیه‌ی خرید.</i>')
    msg = '\n'.join(L)
    print(msg)
    if not token or not chats:
        return 0
    ok = True
    for cid in chats:
        for ch in S.chunks(msg.split('\n')):
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML',
                                                            'disable_web_page_preview': 'true'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
