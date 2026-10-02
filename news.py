"""
Daily digest of global economy / tech news and analyst views, with headline-tone statistics
and Polymarket odds. Free: Google News + major outlets' public RSS feeds, Polymarket public API.
Optional: GEMINI_API_KEY (free) adds a written summary of analysts' views.
"""
import datetime as dt
import html
import re
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}


def gnews(q):
    return ("https://news.google.com/rss/search?q=" + requests.utils.quote(q + " when:2d")
            + "&hl=en-US&gl=US&ceid=US:en")


# topic -> (Google News queries, up words, down words, up sentence, down sentence, Polymarket topic)
TOPICS = {
    "نرخ بهره و فدرال رزرو": (
        ["Fed interest rate outlook analysts", "Federal Reserve rate cut expectations economists"],
        ["cut", "cuts", "easing", "dovish", "lower rates", "pause"],
        ["hike", "hikes", "hawkish", "higher for longer", "sticky inflation", "no cut", "delay"],
        "بیشتر خبرها از کاهش نرخ بهره در آمریکا می‌گویند", "بیشتر خبرها از ثابت ماندن یا افزایش نرخ بهره می‌گویند", "نرخ بهره و فدرال رزرو"),
    "اقتصاد آمریکا": (
        ["US economy outlook economists", "US recession risk analysts", "US jobs report economy"],
        ["growth", "strong", "beats", "resilient", "expands", "rebound", "soft landing", "robust", "gains"],
        ["recession", "slowdown", "contraction", "weak", "layoffs", "misses", "downturn", "stagflation", "slows"],
        "بیشتر خبرها از رشد و قوی بودن اقتصاد آمریکا می‌گویند", "بیشتر خبرها از کند شدن اقتصاد آمریکا می‌گویند", "رکود و رشد"),
    "اقتصاد جهان": (
        ["global economy outlook IMF World Bank", "world economy forecast analysts", "China economy outlook"],
        ["growth", "upgrade", "recovery", "rebound", "strong", "expands", "raises forecast"],
        ["recession", "slowdown", "downgrade", "weak", "risks", "cuts forecast", "contraction", "slump"],
        "بیشتر خبرها درباره‌ی اقتصاد جهان مثبت‌اند", "بیشتر خبرها درباره‌ی اقتصاد جهان نگران‌کننده‌اند", None),
    "تورم": (
        ["inflation outlook economists", "CPI inflation expectations"],
        ["cools", "eases", "slows", "falls", "lower", "moderates"],
        ["rises", "accelerates", "hot", "sticky", "jumps", "higher", "surges"],
        "بیشتر خبرها از کم شدن تورم می‌گویند", "بیشتر خبرها از بالا رفتن تورم می‌گویند", "تورم"),
    "نفت": (
        ["oil price forecast analysts", "OPEC oil market outlook", "Brent crude outlook"],
        ["rise", "rises", "surge", "rally", "higher", "jump", "climbs", "gains", "deficit", "tight"],
        ["fall", "falls", "drop", "slump", "glut", "surplus", "lower", "slides", "declines", "tumbles"],
        "بیشتر خبرها از بالا رفتن قیمت نفت می‌گویند", "بیشتر خبرها از پایین آمدن قیمت نفت می‌گویند", "نفت و انرژی"),
    "طلا و فلزات": (
        ["gold price outlook analysts", "copper silver price forecast"],
        ["rise", "rises", "record", "rally", "higher", "jump", "gains", "climbs", "surge"],
        ["fall", "falls", "drop", "slump", "lower", "slides", "declines", "tumbles", "retreat"],
        "بیشتر خبرها از بالا رفتن قیمت طلا و فلزات می‌گویند", "بیشتر خبرها از پایین آمدن قیمت طلا و فلزات می‌گویند", "طلا و فلزات"),
    "تکنولوژی و هوش مصنوعی": (
        ["AI stocks outlook analysts", "tech stocks Nasdaq outlook", "semiconductor demand outlook"],
        ["record", "surge", "beats", "rally", "boom", "strong demand", "gains", "upgrade"],
        ["slump", "selloff", "bubble", "falls", "layoffs", "downgrade", "weak", "slides", "misses"],
        "بیشتر خبرها درباره‌ی شرکت‌های فناوری و هوش مصنوعی مثبت‌اند", "بیشتر خبرها درباره‌ی شرکت‌های فناوری و هوش مصنوعی نگران‌کننده‌اند", None),
}

# Major outlets' own feeds (broad coverage; matched to topics by keywords)
FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",   # CNBC Economy
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",                            # MarketWatch
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",                                         # WSJ Markets
    "https://www.economist.com/finance-and-economics/rss.xml",                               # The Economist
    "https://oilprice.com/rss/main",                                                         # OilPrice
    "https://techcrunch.com/feed/",                                                          # TechCrunch
    "https://www.federalreserve.gov/feeds/press_all.xml",                                    # Federal Reserve
]
FEED_KEYS = {
    "نرخ بهره و فدرال رزرو": ["fed", "fomc", "rate", "powell"],
    "اقتصاد آمریکا": ["u.s.", "us ", "america", "jobs", "payrolls", "gdp", "consumer", "recession", "economy"],
    "اقتصاد جهان": ["global", "world", "imf", "china", "europe", "ecb", "germany", "japan", "economy"],
    "تورم": ["inflation", "cpi", "pce", "prices"],
    "نفت": ["oil", "crude", "opec", "brent"],
    "طلا و فلزات": ["gold", "silver", "copper", "metal", "platinum"],
    "تکنولوژی و هوش مصنوعی": ["ai", "nvidia", "chip", "tech", "openai", "semiconductor", "nasdaq", "software"],
}


def fetch_items(url):
    try:
        r = requests.get(url, headers=UA, timeout=25)
        root = ET.fromstring(r.content)
    except Exception as e:
        print("feed failed:", url[:60], str(e)[:80])
        return []
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = it.find("source")
        source = src.text.strip() if src is not None and src.text else ""
        if " - " in title:
            head, tail = title.rsplit(" - ", 1)
            if not source or len(tail.strip()) < 40:
                title, source = head, source or tail
        if not source:
            source = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        if title:
            out.append((title.strip(), source.strip()))
    return out


def tone(title, up, down):
    t = " " + title.lower() + " "
    def hit(w):  # also matches simple word forms: jump/jumps/jumped/jumping
        return re.search(r"\b" + re.escape(w) + r"(s|es|ed|d|ing)?\b", t) is not None
    u = sum(1 for w in up if hit(w))
    d = sum(1 for w in down if hit(w))
    return "up" if u > d else ("down" if d > u else "neutral")


def collect():
    feed_items = []
    for f in FEEDS:
        feed_items += fetch_items(f)
    data = {}
    for topic, (queries, up, down, *_rest) in TOPICS.items():
        items, seen = [], set()
        keys = FEED_KEYS[topic]
        for q in queries:
            for title, source in fetch_items(gnews(q)):
                tl = " " + title.lower() + " "
                if not any(" " + k in tl for k in keys):
                    continue  # keep only headlines that are really about this topic
                k = title.lower()[:80]
                if k not in seen:
                    seen.add(k)
                    items.append((title, source))
        for title, source in feed_items:
            tl = " " + title.lower() + " "
            if any(" " + k in tl for k in FEED_KEYS[topic]):
                k = title.lower()[:80]
                if k not in seen:
                    seen.add(k)
                    items.append((title, source))
        data[topic] = [(t, s, tone(t, up, down)) for t, s in items]
    return data


def run(send, polymarket=None, gemini=None):
    today = dt.date.today().strftime("%Y-%m-%d")
    data = collect()
    pm = polymarket() if polymarket else {}
    total = sum(len(v) for v in data.values())
    sources = {s for v in data.values() for _, s, _ in v}
    blocks = [f"📰 <b>خلاصه‌ی خبرها و نظر کارشناسان</b> — {today}\n"
              f"<i>{total} خبر از {len(sources)} رسانه در دو روز گذشته بررسی شد.</i>"]

    # statistics table: headline tone per topic
    rows = [f"{'Topic':<12}{'N':>4}{'Up%':>5}{'Down%':>6}{'Neu%':>5}", "-" * 32]
    short = {"نرخ بهره و فدرال رزرو": "Fed/Rates", "اقتصاد آمریکا": "US Economy", "اقتصاد جهان": "World Econ",
             "تورم": "Inflation", "نفت": "Oil", "طلا و فلزات": "Gold/Metals", "تکنولوژی و هوش مصنوعی": "Tech/AI"}
    readings = []
    for topic, items in data.items():
        n = len(items)
        if not n:
            continue
        up = sum(1 for *_, t in items if t == "up") * 100 / n
        dn = sum(1 for *_, t in items if t == "down") * 100 / n
        neu = 100 - up - dn
        rows.append(f"{short[topic]:<12}{n:>4}{up:>5.0f}{dn:>6.0f}{neu:>5.0f}")
        _, _, _, ul, dl, _ = TOPICS[topic]
        if n < 5:
            sentence = "امروز خبر کافی برای نتیجه‌گیری نبود."
        elif neu >= 70:
            sentence = "بیشتر خبرها جهت روشنی ندارند و نمی‌شود نتیجه‌ی مشخصی گرفت."
        elif up > dn + 10:
            sentence = ul + "."
        elif dn > up + 10:
            sentence = dl + "."
        else:
            sentence = "خبرهای مثبت و منفی تقریباً برابرند."
        readings.append(f"• <b>{topic}:</b> {sentence}")
    blocks.append("📊 <b>کارشناسان و رسانه‌ها چه می‌گویند؟</b>\n"
                  "<i>در جدول: N تعداد خبرها، Up درصد خبرهای مثبت، Down درصد خبرهای منفی، "
                  "Neu درصد خبرهای بی‌طرف.</i>\n"
                  + "<pre>" + html.escape("\n".join(rows)) + "</pre>\n" + "\n".join(readings))

    # translate displayed English texts (headlines, Polymarket questions) to Persian
    try:
        from translate import fa_list
    except Exception:
        fa_list = lambda x: x
    shown = [q for items in pm.values() for q, _, _ in items[:2]]
    shown += [title[:150] for items in data.values() for title, _, _ in items[:4]]
    tr = dict(zip(shown, fa_list(shown)))

    # Polymarket side by side
    if pm:
        lines = ["🎲 <b>پیش‌بینی‌ها در Polymarket</b>",
                 "<i>Polymarket سایتی است که مردم روی اتفاق‌های آینده شرط می‌بندند. "
                 "عدد هر سطر یعنی به نظر آن‌ها چقدر احتمال دارد آن اتفاق بیفتد.</i>"]
        for topic, items in pm.items():
            for q, p, _ in items[:2]:
                lines.append(f"• {html.escape(tr.get(q, q))} — احتمال <b>{p * 100:.0f}٪</b>")
        blocks.append("\n".join(lines))

    # key headlines per topic
    for topic, items in data.items():
        if not items:
            continue
        top = items[:4]
        mark = {"up": "🟢", "down": "🔴", "neutral": "⚪️"}
        blocks.append(f"<b>مهم‌ترین خبرهای {topic}</b>\n" + "\n".join(
            f"{mark[t]} {html.escape(tr.get(title[:150], title[:150]))} — <i>{html.escape(src)}</i>"
            for title, src, t in top))

    if gemini:
        heads = "\n".join(f"[{tp}] {t} ({s})" for tp, it in data.items() for t, s, _ in it[:12])
        pm_txt = "\n".join(f"[{t}] {q}: {p * 100:.0f}%" for t, it in pm.items() for q, p, _ in it)
        ai = gemini(
            "تو تحلیلگر ارشد اقتصاد کلان هستی. با فارسی ساده، روان و قابل فهم برای عموم و جمله‌های کوتاه، از تیترهای خبری و احتمالات Polymarket زیر، یک جمع‌بندی خلاصه "
            "(حداکثر ۱۵ خط) بنویس: دیدگاه غالب تحلیلگران درباره‌ی نرخ بهره‌ی فدرال رزرو، اقتصاد آمریکا، "
            "اقتصاد جهان، تورم، نفت، طلا و تکنولوژی؛ برای هر مورد بگو اکثریت چه نظری دارند و اختلاف نظر کجاست. "
            "هرجا از Polymarket استفاده می‌کنی بنویس «طبق Polymarket». توصیه‌ی خرید و فروش نده.\n\n"
            f"تیترها:\n{heads}\n\nPolymarket:\n{pm_txt}")
        if ai:
            blocks.append("🤖 <b>جمع‌بندی نظر کارشناسان</b>\n" + html.escape(ai))
    blocks.append("<i>این آمار از روی کلمات تیترها حساب شده و فقط یک دید کلی می‌دهد. "
                  "ترجمه‌ی خبرها ماشینی است.</i>")
    send(blocks)
