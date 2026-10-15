"""گزارش هوشمند بازار: اخبار اقتصادی ۲۴ ساعت گذشته (Finnhub) + قیمت‌ها + جمع‌بندی فارسی.

شمارش نظرات بر اساس کلیدواژه‌ی تیتر و خلاصه‌ی خبر است؛ نظر رسمی تحلیلگر نیست.
متغیرهای لازم: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, FINNHUB_API_KEY (اختیاری؛ بدونش فقط قیمت‌ها می‌آید).
"""
import html
import os
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'market_summary'))
import summary as S  # noqa: E402

KEY = os.getenv('FINNHUB_API_KEY', '')

ASSETS = {
    '🥇 طلا': ['gold', 'bullion', 'xau'],
    '🥈 نقره': ['silver'],
    '🟠 مس': ['copper'],
    '₿ بیت‌کوین': ['bitcoin', 'btc', 'crypto'],
    '🛢 نفت': ['oil', 'crude', 'brent', 'wti', 'opec'],
    '🏦 اقتصاد و بانک مرکزی': ['fed', 'inflation', 'recession', 'interest rate', 'treasury', 'yield', 'tariff', 'gdp', 'jobs'],
}
BULL = ['rally', 'surge', 'soar', 'jump', 'record', 'rise', 'gain', 'bullish', 'upgrade', 'boost', 'climb', 'demand', 'optimis']
BEAR = ['fall', 'drop', 'slump', 'plunge', 'bearish', 'decline', 'selloff', 'sell-off', 'recession', 'slide', 'weak', 'crash', 'tumble', 'downgrade', 'fear']


def fetch_news():
    r = requests.get('https://finnhub.io/api/v1/news', params={'category': 'general', 'token': KEY}, timeout=30)
    r.raise_for_status()
    cutoff = time.time() - 86400
    return [n for n in r.json() if n.get('datetime', 0) >= cutoff]


def score(text):
    t = text.lower()
    b = sum(w in t for w in BULL)
    d = sum(w in t for w in BEAR)
    return 1 if b > d else (-1 if d > b else 0)


def classify(news):
    res = {k: {'bull': 0, 'bear': 0, 'neutral': 0, 'example': None} for k in ASSETS}
    for n in news:
        head = n.get('headline', '')
        text = head + ' ' + n.get('summary', '')
        s = score(text)
        for k, kws in ASSETS.items():
            if any(w in text.lower() for w in kws):
                key = {1: 'bull', -1: 'bear', 0: 'neutral'}[s]
                res[k][key] += 1
                if s != 0 and res[k]['example'] is None:
                    res[k]['example'] = head
    return res


def fa(text):
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='auto', target='fa').translate(text) or text
    except Exception:
        return text


def build_lines(prices, cls, news_count):
    lines = ['<b>🧭 گزارش هوشمند بازار</b>',
             f'<i>بر اساس {news_count} خبر ۲۴ ساعت گذشته</i>', '']
    if news_count == 0:
        lines += ['⚠️ کلید Finnhub تنظیم نشده یا خبری دریافت نشد؛ فقط قیمت‌ها و کلان آمده است.', '']
    lines.append('<b>📣 نظر اخبار (شمارش مثبت/منفی/خنثی)</b>')
    for k, d in cls.items():
        total = d['bull'] + d['bear'] + d['neutral']
        if total == 0:
            lines.append(f'• <b>{k}</b>: خبری نبود')
            continue
        lines.append(f"• <b>{k}</b>: 🟢{d['bull']} 🔴{d['bear']} ⚪{d['neutral']} (از {total})")
        if d['example']:
            lines.append(f"   ↳ <i>{html.escape(fa(d['example']))}</i>")
    v = S.build_verdict(prices)
    if v:
        lines += ['', v]
    lines += ['', '<i>⚠️ شمارش بر اساس کلیدواژه‌ی تیتر است؛ نظر رسمی تحلیلگر نیست.</i>']
    return lines


def build_macro(prices):
    lines = ['<b>🌍 خلاصه‌ی نرخ بهره و اقتصاد جهانی</b>', '']
    try:
        lines += ['• ' + x for x in S.macro_bullets()]
    except Exception as e:
        lines.append(f'⚠️ داده‌های کلان در دسترس نبود: {html.escape(str(e))}')
    return lines


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ توکن یا شناسه‌ی چت تنظیم نشده', file=sys.stderr)
        return 1
    news = []
    if KEY:
        try:
            news = fetch_news()
        except Exception as e:
            print(f'⚠️ Finnhub: {e}', file=sys.stderr)
    cls = classify(news)
    prices = S.fetch_prices()
    import tempfile
    png = os.path.join(tempfile.mkdtemp(), 'table.png')
    S.render_table_png(prices, png)
    caption = '<b>🧭 گزارش هوشمند بازار</b>\n<i>قیمت‌ها و نگاه اخبار</i>'
    macro_chunks = S.chunks(build_macro(prices))
    smart_chunks = S.chunks(build_lines(prices, cls, len(news)))
    ok = True
    for cid in chat_ids:
        for ch in macro_chunks:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
        with open(png, 'rb') as f:
            ok &= S.tg_post(token, cid, 'sendPhoto', data={'chat_id': cid, 'caption': caption, 'parse_mode': 'HTML'},
                            files={'photo': f})
        for ch in smart_chunks:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
