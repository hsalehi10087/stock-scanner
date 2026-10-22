"""گزارش هوشمند بازار: اخبار اقتصادی ۲۴ ساعت گذشته (Finnhub) + قیمت‌ها + جمع‌بندی فارسی.

شمارش نظرات بر اساس کلیدواژه‌ی تیتر و خلاصه‌ی خبر است؛ نظر رسمی تحلیلگر نیست.
متغیرهای لازم: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, FINNHUB_API_KEY (اختیاری؛ بدونش فقط قیمت‌ها می‌آید).
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'market_summary'))
import summary as S  # noqa: E402

KEY = os.getenv('FINNHUB_API_KEY', '')
UA = {'User-Agent': 'Mozilla/5.0 (compatible; market-intel/1.0)'}

ASSETS = {
    '🥇 طلا': ['gold', 'bullion', 'xau'],
    '🥈 نقره': ['silver'],
    '🟠 مس': ['copper'],
    '₿ بیت‌کوین': ['bitcoin', 'btc', 'crypto'],
    '🛢 نفت': ['oil', 'crude', 'brent', 'wti', 'opec'],
    '🏦 نرخ بهره و تورم': ['fed', 'inflation', 'recession', 'interest rate', 'treasury', 'yield', 'tariff', 'gdp', 'jobs'],
}
BULL = ['rally', 'surge', 'soar', 'jump', 'record', 'rise', 'gain', 'bullish', 'upgrade', 'boost', 'climb', 'demand', 'optimis']
BEAR = ['fall', 'drop', 'slump', 'plunge', 'bearish', 'decline', 'selloff', 'sell-off', 'recession', 'slide', 'weak', 'crash', 'tumble', 'downgrade', 'fear']


def fetch_news():
    r = requests.get('https://finnhub.io/api/v1/news', params={'category': 'general', 'token': KEY}, timeout=30)
    r.raise_for_status()
    cutoff = time.time() - 7 * 86400
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
    """ترجمه‌ی فارسی؛ اگر ترجمه ممکن نباشد None برمی‌گرداند (تا متن انگلیسی نشان داده نشود)."""
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source='auto', target='fa').translate(text)
        if out and out.strip() and out.strip() != text.strip():
            return out
    except Exception:
        pass
    return None


def fetch_article(url):
    """متن ساده‌ی مقاله؛ اگر باز نشد رشته‌ی خالی."""
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', r.text, flags=re.S | re.I)
        txt = re.sub(r'<[^>]+>', ' ', txt)
        txt = html.unescape(re.sub(r'\s+', ' ', txt))
        return txt[:3000]
    except Exception:
        return ''


JUNK = ['subscribe', 'click', 'sign up', 'cookie', 'advertis', 'newsletter', 'read more', 'copyright', 'all rights']
VIEW_WORDS = ['forecast', 'outlook', 'expect', 'predict', 'target', 'analyst', 'expects', 'sees', 'says']


def sentence_strength(sent):
    sl = sent.lower()
    b = sum(w in sl for w in BULL)
    d = sum(w in sl for w in BEAR)
    return abs(b - d) + (2 if any(w in sl for w in VIEW_WORDS) else 0)


def investor_points(news, per_asset=2):
    """جملات مرتبط و جهت‌دار از متن مقاله‌ها (بدون مدل زبانی)، مرتب‌شده بر اساس قدرت و ترجمه‌شده."""
    cands = {k: [] for k in ASSETS}
    seen = set()
    for n in news[:40]:
        head = n.get('headline', '')
        text = (head + ' ' + n.get('summary', '')).lower()
        if not n.get('url') or not any(w in text for kws in ASSETS.values() for w in kws):
            continue
        body = fetch_article(n['url']) or n.get('summary', '')
        for sent in re.split(r'(?<=[.!?])\s+', body):
            sent = sent.strip()
            if not 50 <= len(sent) <= 260:
                continue
            sl = sent.lower()
            if any(j in sl for j in JUNK) or score(sent) == 0:
                continue
            key = sl[:60]
            if key in seen:
                continue
            seen.add(key)
            for k, kws in ASSETS.items():
                if any(w in sl for w in kws):
                    cands[k].append((sentence_strength(sent), sent))
    lines = []
    for k, items in cands.items():
        shown = 0
        for _, sent in sorted(items, key=lambda x: -x[0]):
            if shown >= per_asset:
                break
            tr = fa(sent)
            if not tr:
                continue
            label = 'مثبت' if score(sent) > 0 else 'منفی'
            lines.append(f"• <b>{k}</b> ({label}): {html.escape(tr)}")
            shown += 1
    return lines


VIEWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'analyst_views', 'latest.json')
AI_ASSETS = [('gold', '🥇 طلا'), ('silver', '🥈 نقره'), ('bitcoin', '₿ بیت‌کوین'), ('copper', '🟠 مس'),
             ('oil', '🛢 نفت'), ('rates', '🏦 نرخ بهره')]
STANCE = {'صعودی': '🟢', 'نزولی': '🔴', 'خنثی': '⚪', 'دوگانه': '🟡'}


def analyst_section():
    """نظر تحلیلگران که کار روزانه‌ی Claude از متن خبرها درک و خلاصه کرده (اگر تازه باشد)."""
    try:
        v = json.load(open(VIEWS, encoding='utf-8'))
    except Exception:
        return None
    try:
        age = (dt.datetime.now(dt.timezone.utc).date() - dt.date.fromisoformat(v['date'])).days
    except Exception:
        return None
    if age > 1:
        return None
    lines = ['<b>🧠 نظر تحلیلگران</b>', f"<i>از {v.get('articles_read', '؟')} خبر و تحلیل ۲۴ ساعت اخیر، درک‌شده با هوش مصنوعی</i>"]
    for key, label in AI_ASSETS:
        a = (v.get('assets') or {}).get(key)
        if not a:
            continue
        st = a.get('stance', 'خنثی')
        cnt = a.get('counts') or {}
        d = lambda x: str(x).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
        if key == 'rates':
            tag = {'صعودی': '🔺 احتمال افزایش نرخ', 'نزولی': '🔻 احتمال کاهش نرخ'}.get(st, '⚪ ثابت ماندن نرخ')
            cnt_txt = f"افزایش {d(cnt.get('bull', 0))}، کاهش {d(cnt.get('bear', 0))}، ثابت {d(cnt.get('neutral', 0))}"
        else:
            tag = f"{STANCE.get(st, '⚪')} {st}"
            cnt_txt = f"صعودی {d(cnt.get('bull', 0))}، نزولی {d(cnt.get('bear', 0))}، خنثی {d(cnt.get('neutral', 0))}"
        lines.append(f"• <b>{label}</b> — {tag} ({cnt_txt}): "
                     f"{html.escape(a.get('summary_fa', ''))}")
        for w in (a.get('views') or [])[:2]:
            who = html.escape(w.get('who', ''))
            url = w.get('url', '')
            txt = html.escape(w.get('view_fa', ''))
            lines.append(f'   ↳ <a href="{html.escape(url)}">{who}</a>: {txt}' if url else f'   ↳ {who}: {txt}')
    if v.get('watch_fa'):
        lines += ['', '<b>👀 مهم برای روزهای آینده:</b> ' + html.escape(v['watch_fa'])]
    return lines


def build_lines(prices, cls, news_count, view=None):
    ai = analyst_section()
    if ai:
        lines = ['<b>🧭 گزارش هوشمند بازار</b>', ''] + ai
        lines += [''] + build_macro(prices)[1:]
        v = S.build_verdict(prices)
        if v:
            lines += ['', v]
        lines += ['', '<i>⚠️ خلاصه‌ی نظر تحلیلگران از خبرهاست، نه توصیه‌ی سرمایه‌گذاری.</i>']
        return lines
    return build_lines_keywords(prices, cls, news_count, view)


def build_lines_keywords(prices, cls, news_count, view=None):
    lines = ['<b>🧭 گزارش هوشمند بازار</b>',
             f'<i>بر اساس {news_count} خبر ۷ روز گذشته</i>', '']
    if news_count == 0:
        lines += ['⚠️ کلید Finnhub تنظیم نشده یا خبری دریافت نشد؛ فقط قیمت‌ها و کلان آمده است.', '']
    lines.append('<b>📣 نظر اخبار هفته</b>')
    lines.append('<i>🟢 خبر مثبت برای قیمت  🔴 خبر منفی برای قیمت  ⚪ خبر خنثی</i>')
    for k, d in cls.items():
        total = d['bull'] + d['bear'] + d['neutral']
        if total == 0:
            lines.append(f'• <b>{k}</b>: خبری نبود')
            continue
        lines.append(f"• <b>{k}</b>: 🟢{d['bull']} 🔴{d['bear']} ⚪{d['neutral']} (از {total})")
        tr = fa(d['example']) if d['example'] else None
        if tr:
            lines.append(f"   ↳ <i>{html.escape(tr)}</i>")
    if view:
        lines += ['', '<b>🧠 نکات کلیدی از مقاله‌های هفته</b>'] + view
    lines += [''] + build_macro(prices)[1:]
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
    view = None if analyst_section() else investor_points(news)
    prices = S.fetch_prices()
    import tempfile
    png = os.path.join(tempfile.mkdtemp(), 'table.png')
    S.render_table_png(prices, png)
    caption = '<b>🧭 گزارش هوشمند بازار</b>\n<i>قیمت‌ها و نگاه اخبار</i>'
    smart_chunks = S.chunks(build_lines(prices, cls, len(news), view))
    ok = True
    for cid in chat_ids:
        with open(png, 'rb') as f:
            ok &= S.tg_post(token, cid, 'sendPhoto', data={'chat_id': cid, 'caption': caption, 'parse_mode': 'HTML'},
                            files={'photo': f})
        for ch in smart_chunks:
            ok &= S.tg_post(token, cid, 'sendMessage', data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
