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
M = os.path.join(ROOT, 'data', 'ai_stocks', 'metrics.json')
SC = os.path.join(ROOT, 'data', 'ai_stocks', 'scorecard.json')
SENT = os.path.join(ROOT, 'data', 'ai_stocks', 'sent.json')   # جلوگیری از ارسال دوباره (اجرای دستی Claude + زمان‌بندی GitHub)
D = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa(x):
    return f'{x:+.1f}'.replace('.', '٫').translate(D).replace('+', '+\u200e') if x is not None else '؟'


def scorecard_lines():
    try:
        c = json.load(open(SC, encoding='utf-8'))
    except Exception:
        return []
    if not c.get('days_measured'):
        return []
    b = c.get('benchmarks_pct', {})
    L = [f"📈 <b>کارنامه‌ی انتخاب‌ها</b> (از {c['first_pick_date'].replace('-', '/').translate(D)}، "
         f"{str(c['days_measured']).translate(D)} روز معاملاتی): سبد انتخاب‌ها {fa(c['portfolio_pct'])}٪ | "
         f"QQQ {fa(b.get('QQQ'))}٪ | SMH {fa(b.get('SMH'))}٪"]
    if c.get('hit_rate_vs_qqq_pct') is not None:
        L.append(f"روزهایی که سبد از QQQ بهتر بود: {str(int(c['hit_rate_vs_qqq_pct'])).translate(D)}٪")
    per = sorted(c.get('per_ticker', []), key=lambda r: -r['ret_pct'])
    if per:
        L.append(' | '.join(f"{r['ticker']} {fa(r['ret_pct'])}٪" + ('' if r['in_list_now'] else ' (خارج‌شده)') for r in per))
    L.append(f"<i>{html.escape(c.get('note', ''))}؛ دوره کوتاه است و نتیجه هنوز معنی‌دار نیست.</i>")
    return L + ['']


def watchlist_lines(v, e):
    """نامزدهای بعدی: سهم‌هایی که شرط‌ها را دارند ولی در فهرست اصلی نیستند."""
    w = v.get('watchlist') or []
    if not w:
        return []
    L = ['🔭 <b>نامزدهای بعدی</b> (واجد شرایط، ولی هنوز در فهرست اصلی نیستند):']
    for r in w[:5]:
        L.append(f"• <b>{e(r.get('ticker', ''))}</b>" + (f" — {e(r['name'])}" if r.get('name') else '') + f": {e(r.get('why_fa', ''))}")
    return L + ['']


def short_report(v, e):
    """گزارش روزهای عادی (غیر دوشنبه): فقط تغییرات و هشدار خبری، کوتاه."""
    L = [f"<b>🤖 سهام هوش مصنوعی — خلاصه‌ی روز</b> — {v['date'].replace('-', '/').translate(D)}", '']
    if v.get('market_fa'):
        L += [f"🌐 {e(v['market_fa'])}", '']
    w = weak_market()
    if w:
        L += [w, '']
    ch = v.get('changes_fa') or []
    L.append('🔔 <b>چه چیزی از دیروز عوض شد:</b>')
    L += [f"• {e(c)}" for c in ch[:6]] if ch else ['• تغییر مهمی نبود.']
    L.append('')
    al = v.get('alerts') or []
    if al:
        L.append('📰 <b>هشدار خبری درباره‌ی سهم‌های فهرست:</b>')
        for a in al[:5]:
            src = a.get('url')
            L.append(f"• <b>{e(a.get('ticker', ''))}</b>: {e(a.get('alert_fa', ''))}" + (f' (<a href="{e(src)}">خبر</a>)' if src else ''))
        L.append('')
    picks = [p['ticker'] for p in v.get('picks', [])[:5]]
    if picks:
        L += [f"📋 <b>فهرست فعلی:</b> {'، '.join(picks)} (فهرست کامل با دلیل و ریسک، دوشنبه‌ها)", '']
    L += watchlist_lines(v, e)
    if v.get('dropped_fa'):
        L += [f"🔻 <b>از فهرست بیرون رفت:</b> {e(v['dropped_fa'])}", '']
    L.append('<i>پیش‌بینی قطعی و توصیه‌ی خرید نیست.</i>')
    return L


def weak_market():
    """اگر QQQ زیر میانگین ۵۰ روزه است: هشدار (سهم‌های کوچک و پرنوسان AI در بازار نزولی بیشتر می‌ریزند)."""
    try:
        import yfinance as yf
        c = yf.download('QQQ', period='6mo', interval='1d', auto_adjust=True, progress=False)['Close'].squeeze().dropna()
        p, m50 = float(c.iloc[-1]), float(c.rolling(50).mean().iloc[-1])
    except Exception:
        return ''
    if p >= m50:
        return ''
    gap = f'{(p / m50 - 1) * 100:.1f}'.translate(str.maketrans('0123456789.-', '۰۱۲۳۴۵۶۷۸۹٫−'))
    return (f"🌧 <b>هشدار بازار:</b> QQQ {gap}٪ زیر میانگین ۵۰ روزه است. در چنین بازاری سهم‌های کوچک و پرنوسان AI معمولاً "
            "بیشتر از شاخص می‌ریزند؛ فقط سهم‌هایی که جریان نقد مثبت یا نقد کافی دارند در فهرست مانده‌اند و این زمان، زمان صبر است، نه خرید عجولانه.")


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
    try:
        sent = json.load(open(SENT, encoding='utf-8'))
    except Exception:
        sent = {}
    if chats and token and sent.get('date') == v['date'] and os.getenv('FORCE_SEND') != '1':
        print('already sent today; nothing sent')
        return 0
    try:
        ms = json.load(open(M, encoding='utf-8')).get('stocks', {})
    except Exception:
        ms = {}
    e = html.escape
    # mode: 'weekly' (دوشنبه‌ها: فهرست کامل) | 'daily' (کوتاه). نبودن mode یا بازبینی هفتگی = کامل.
    short = v.get('mode') == 'daily' and not v.get('review_fa')
    L = [f"<b>🤖 گزارش سهام هوش مصنوعی</b> — {v['date'].replace('-', '/').translate(D)}",
         f"<i>{e(v.get('method_fa', ''))}</i>", '']
    if short:
        L = short_report(v, e)
    else:
        if v.get('market_fa'):
            L += [f"🌐 <b>فضای بازار AI:</b> {e(v['market_fa'])}", '']
        w = weak_market()
        if w:
            L += [w, '']
        for i, p in enumerate(v.get('picks', [])[:5], 1):
            L.append(f"<b>{str(i).translate(D)}. {e(p['ticker'])} — {e(p.get('name', ''))}</b> ({e(p.get('segment_fa', ''))})")
            L.append(f"📊 {e(p.get('numbers_fa', ''))}")
            L.append(f"🚀 چرا: {e(p.get('thesis_fa', ''))}")
            if p.get('news_fa'):
                src = p.get('news_url')
                L.append(f"📰 {e(p['news_fa'])}" + (f' (<a href="{e(src)}">خبر</a>)' if src else ''))
            L.append(f"⚠️ ریسک: {e(p.get('risk_fa', ''))}")
            ne = p.get('next_earnings') or ms.get(p['ticker'], {}).get('next_earnings')
            if ne:
                days = (dt.date.fromisoformat(ne) - dt.date.fromisoformat(v['date'])).days
                if days >= 0:
                    L.append(f"📅 گزارش فصلی بعدی: {ne.replace('-', '/').translate(D)}"
                             + (f" ({str(days).translate(D)} روز دیگر)" if days else ' (امروز)'))
            L.append('')
        if v.get('dropped_fa'):
            L += [f"🔻 <b>از فهرست بیرون رفت:</b> {e(v['dropped_fa'])}", '']
        if v.get('review_fa'):
            L += [f"🔄 <b>بازبینی هفتگی:</b> {e(v['review_fa'])}", '']
        # کارنامه: دوشنبه‌ها (روز بازبینی هفتگی) یا هر روزی که بازبینی هفتگی انجام شده
        if v.get('review_fa') or dt.date.fromisoformat(v['date']).weekday() == 0:
            L += scorecard_lines()
        L += watchlist_lines(v, e)
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
    if ok:
        json.dump({'date': v['date'], 'sent_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')},
                  open(SENT, 'w', encoding='utf-8'))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
