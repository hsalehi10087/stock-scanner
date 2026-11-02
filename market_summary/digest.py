"""گزارش صبحگاهی یکجا: خروجی ۶ گزارش ساعت ۵ صبح را در یک آلبوم عکس + چند پیام متنی پشت‌سرهم می‌فرستد.

هر گزارش با DIGEST_DIR=<پوشه> اجرا می‌شود و پیام‌هایش (به‌جای ارسال) در <پوشه>/<نام>.jsonl ذخیره می‌شود.
اجرا: python3 market_summary/digest.py <پوشه>
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summary as S  # noqa: E402

ORDER = [('report', '🧭 بازار و نظر تحلیلگران'), ('gainers', '🚀 آمریکا: رشد قیمت بیش از ۱۰٪'),
         ('fund_growth', '📈 آمریکا: رشد سود بیش از ۱۰٪'), ('jp_growth', '🇯🇵 ژاپن'),
         ('cn_growth', '🇨🇳 چین'), ('tw_growth', '🇹🇼 تایوان')]
# گزارش دوم (حدود ۰۸:۴۰ تهران): هوش مصنوعی، احتمال رشد، فارکس، سرمایه‌گذاران بزرگ
ORDER2 = [('ai_report', '🤖 سهام هوش مصنوعی'), ('growth_report', '🚀 احتمال رشد تکنیکال و بنیادی'),
          ('scorecard_all', '📊 کارنامه‌ی هفتگی ایجنت‌ها'), ('cot', '💱 فارکس — موقعیت معامله‌گران بزرگ'), ('run', '🏦 سرمایه‌گذاران بزرگ (Dataroma)')]
SLOTS = {'morning': ('☀️ گزارش صبحگاهی', ORDER), 'morning2': ('🌤 گزارش میان‌صبح', ORDER2)}
FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def main(d, slot='morning'):
    import datetime as dt
    title_main, order = SLOTS[slot]
    photos, texts, have, missing = [], [], [], []
    for name, title in order:
        p = os.path.join(d, name + '.jsonl')
        if not os.path.exists(p):
            missing.append(title)
            continue
        have.append(title)
        texts.append(f'━━━━━━━━━━\n<b>{title}</b>')
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            body = r['data'].get('text') or r['data'].get('caption') or ''
            if r.get('photo'):
                photos.append((os.path.join(d, r['photo']), title))
            if body.strip():
                texts.append(body.strip())
    if not have:
        print('nothing to send')
        return 0 if slot != 'morning' else 1
    today = dt.date.today().strftime('%Y/%m/%d').translate(FA)
    head = [f'<b>{title_main} — {today}</b>',
            'در این گزارش: ' + '، '.join(t for t in have)]
    if missing and slot == 'morning':
        head.append('<i>⚠️ امروز نرسید: ' + '، '.join(missing) + '</i>')
    if photos:
        head.append(f'<i>🖼 {len(photos)} جدول در آلبوم بالا (به همان ترتیب).</i>'.translate(FA))
    tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip() and c.strip() != 'none']
    lines = '\n'.join(head + [''] + texts).split('\n')
    ok = True
    print('\n'.join(lines)[:3000])
    for cid in chats:
        for i in range(0, len(photos), 10):
            part = photos[i:i + 10]
            files, media = {}, []
            for k, (png, title) in enumerate(part):
                files[f'p{k}'] = open(png, 'rb')
                media.append({'type': 'photo', 'media': f'attach://p{k}', 'caption': title})
            if len(part) == 1:
                ok &= S.tg_post(tok, cid, 'sendPhoto', data={'chat_id': cid, 'caption': part[0][1]},
                                files={'photo': files['p0']})
            else:
                ok &= S.tg_post(tok, cid, 'sendMediaGroup', data={'chat_id': cid, 'media': json.dumps(media, ensure_ascii=False)},
                                files=files)
            for f in files.values():
                f.close()
        for ch in S.chunks(lines, limit=3900):
            ok &= S.tg_post(tok, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML',
                                                           'disable_web_page_preview': 'true'})
    return 0 if ok else 2


if __name__ == '__main__':
    os.environ.pop('DIGEST_DIR', None)
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'morning'))
