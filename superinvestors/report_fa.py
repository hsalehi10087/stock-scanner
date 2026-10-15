"""قالب گزارش فشرده‌ی فارسی برای سرمایه‌گذاران بزرگ."""
import html
from collections import defaultdict

# نام فارسی سرمایه‌گذاران (کد Dataroma -> نام فارسی)
FA_NAMES = {
    'ABI': 'ابرامز بایسون',
    'AKO': 'ای‌کی‌او کپیتال',
    'AIM': 'الکس روپرز',
    'AP': 'آلتاراک پارتنرز',
    'VAN': 'آرنولد ون دن برگ',
    'GFT': 'بنیاد گیتس',
    'psc': 'بیل آکمن',
    'LMM': 'بیل میلر',
    'HA': 'بیل نایگرن',
    'fairx': 'بروس برکوویتز',
    'OCL': 'برایان لارنس',
    'ic': 'کارل آیکان',
    'TGM': 'چیس کلمن',
    'tci': 'کریس هون',
    'SA': 'کریستوفر بلومسترن',
    'DAV': 'کریستوفر دیویس',
    'AC': 'چاک آکر',
    'CAS': 'کلیفورد سوسین',
    'tp': 'دانیل لوب',
    'abc': 'دیوید ابرامز',
    'GLRE': 'دیوید آینهورن',
    'MAVFX': 'دیوید کتز',
    'WP': 'دیوید رولف',
    'AM': 'دیوید تپر',
    'SP': 'دنیس هانگ',
    'DAC': 'داج اند کاکس',
    'HH': 'دوان یونگ‌پینگ',
    'FE': 'فرست ایگل',
    'FPA': 'فرست پسیفیک',
    'ca': 'فرانسیس چو',
}

ACTION_ICON = {'خرید جدید': '🟢', 'افزایش': '🔼', 'کاهش': '🔽', 'فروش کامل': '🔴'}


def fa_name(m):
    return FA_NAMES.get(m['code'], m['name'])


def consensus(snap, top=10):
    """سهم‌هایی که بیشترین تعداد سرمایه‌گذار بزرگ دارند."""
    count = defaultdict(int)
    pct_sum = defaultdict(float)
    for m in snap['managers']:
        for h in m['holdings']:
            count[h['ticker']] += 1
            pct_sum[h['ticker']] += h.get('pct') or 0
    ranked = sorted(count, key=lambda t: (-count[t], -pct_sum[t]))[:top]
    return [(t, count[t], pct_sum[t] / count[t]) for t in ranked]


def build_daily(date_str, prev_date, results, snap, top_changes=15):
    total = sum(len(r['changes']) for r in results)
    lines = [f"📈 <b>سرمایه‌گذاران بزرگ</b> — {date_str}"]
    if prev_date:
        lines.append(f"<i>مقایسه با {prev_date}</i>")
    lines.append(f"بیش از ۵٪ پورتفوی: <b>{total}</b> معامله از {len(results)} سرمایه‌گذار")
    lines.append("")

    flat = []
    for r in results:
        for c in r['changes']:
            flat.append((c['pct_of_portfolio'], r, c))
    flat.sort(key=lambda x: -x[0])
    if flat:
        lines.append("<b>🔥 مهم‌ترین معاملات</b>")
        for _, r, c in flat[:top_changes]:
            icon = ACTION_ICON.get(c['action'], '•')
            lines.append(f"{icon} {html.escape(r['fa'])}: {c['action']} <b>{c['ticker']}</b> ({c['pct_of_portfolio']}٪)")
        if len(flat) > top_changes:
            lines.append(f"… و {len(flat) - top_changes} معامله‌ی دیگر")
    else:
        lines.append("امروز معامله‌ی بالای ۵٪ ثبت نشد.")
    lines.append("")
    lines.append("<b>🏆 محبوب‌ترین سهم‌ها بین سرمایه‌گذاران</b>")
    for t, n, avg in consensus(snap):
        lines.append(f"• <b>{t}</b>: {n} نفر، میانگین {avg:.1f}٪")
    return lines


def build_first(snap, top_per_manager=3):
    lines = [f"🏦 <b>گزارش اولیه: سرمایه‌گذاران بزرگ</b> — {snap['date']}",
             f"{len(snap['managers'])} سرمایه‌گذار برتر", ""]
    lines.append("<b>🏆 محبوب‌ترین سهم‌ها</b>")
    for t, n, avg in consensus(snap):
        lines.append(f"• <b>{t}</b>: {n} نفر، میانگین {avg:.1f}٪")
    lines.append("")
    lines.append("<b>👤 بزرگ‌ترین سهم‌های هر سرمایه‌گذار</b>")
    for m in snap['managers']:
        top = sorted(m['holdings'], key=lambda h: -(h.get('pct') or 0))[:top_per_manager]
        tickers = '، '.join(f"{h['ticker']} ({h['pct']:.0f}٪)" for h in top if h.get('pct') is not None)
        lines.append(f"• <b>{html.escape(fa_name(m))}</b>: {tickers}")
    return lines
