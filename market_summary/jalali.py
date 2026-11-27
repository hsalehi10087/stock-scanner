"""تبدیل تاریخ میلادی به شمسی برای همه‌ی گزارش‌های تلگرام (بدون وابستگی خارجی).

shamsi_text(text) هر تاریخ میلادی کامل (۲۰۲۶-۱۱-۲۷ یا 2026/11/27، با رقم لاتین یا فارسی) را در متن
به شمسی با رقم فارسی تبدیل می‌کند؛ مثلاً 2026-11-27 ← ۱۴۰۵/۰۹/۰۶. تاریخ‌های داخل نشانی اینترنتی دست نمی‌خورند
و تاریخ شمسی دوباره تبدیل نمی‌شود (فقط سال‌های ۱۹۰۰ تا ۲۱۰۰ میلادی).
"""
import datetime as _dt
import re

FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
_TO_ASCII = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_D = '[0-9۰-۹٠-٩]'
_DATE_RE = re.compile(rf'(?<![0-9۰-۹٠-٩])({_D}{{4}})([-/])({_D}{{1,2}})\2({_D}{{1,2}})(?![0-9۰-۹٠-٩])')
_URL_RE = re.compile(r'(?:https?://|www\.)[^\s"\'<>]+')


def g2j(gy, gm, gd):
    """میلادی ← شمسی؛ خروجی (سال، ماه، روز)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
            + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def to_shamsi(d=None, fa_digits=True):
    """date/datetime/'YYYY-MM-DD' ← '۱۴۰۵/۰۹/۰۶'. بدون ورودی: امروز (به وقت تهران)."""
    if d is None:
        d = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=3, minutes=30))).date()
    if isinstance(d, str):
        d = _dt.date.fromisoformat(d.translate(_TO_ASCII)[:10].replace('/', '-'))
    s = '%04d/%02d/%02d' % g2j(d.year, d.month, d.day)
    return s.translate(FA_DIGITS) if fa_digits else s


def _convert_plain(text):
    def rep(m):
        y, mo, d = (int(x.translate(_TO_ASCII)) for x in (m.group(1), m.group(3), m.group(4)))
        if not 1900 <= y <= 2100:
            return m.group(0)
        try:
            _dt.date(y, mo, d)
        except ValueError:
            return m.group(0)
        return ('%04d/%02d/%02d' % g2j(y, mo, d)).translate(FA_DIGITS)
    return _DATE_RE.sub(rep, text)


def shamsi_text(text):
    """همه‌ی تاریخ‌های میلادی متن را شمسی می‌کند (به‌جز داخل نشانی‌های اینترنتی)."""
    if not text or not isinstance(text, str):
        return text
    out, pos = [], 0
    for m in _URL_RE.finditer(text):
        out.append(_convert_plain(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_convert_plain(text[pos:]))
    return ''.join(out)


def shamsi_payload(data):
    """فیلدهای متنی پیام تلگرام (text و caption) را شمسی می‌کند؛ بقیه دست نمی‌خورد."""
    if isinstance(data, dict):
        for k in ('text', 'caption'):
            if isinstance(data.get(k), str):
                data[k] = shamsi_text(data[k])
    return data


if __name__ == '__main__':
    assert to_shamsi('2026-11-27', False) == '1405/09/06'
    assert to_shamsi('2026-03-21', False) == '1405/01/01'
    assert to_shamsi('2025-03-20', False) == '1403/12/30'
    assert to_shamsi('2024-03-20', False) == '1403/01/01'
    s = shamsi_text('گزارش — 2026-11-27 و ۲۰۲۶/۱۱/۲۶ 21:53 <a href="https://x.com/2026-11-27/a">لینک</a> ۱۴۰۵/۰۹/۰۶ 2026-13-40')
    assert s == 'گزارش — ۱۴۰۵/۰۹/۰۶ و ۱۴۰۵/۰۹/۰۵ 21:53 <a href="https://x.com/2026-11-27/a">لینک</a> ۱۴۰۵/۰۹/۰۶ 2026-13-40', s
    print('ok', s)
