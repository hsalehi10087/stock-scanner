"""تجزیه‌ی صفحات Dataroma (فهرست سرمایه‌گذاران و پورتفوی هر کدام)."""
import re

_TD = re.compile(r'<td[^>]*>(.*?)</td>', re.S)
_TR = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_TAGS = re.compile(r'<[^>]+>')


def _text(html_fragment: str) -> str:
    return re.sub(r'\s+', ' ', _TAGS.sub(' ', html_fragment)).replace('&nbsp;', ' ').strip()


def _num(s: str):
    s = s.replace(',', '').replace('$', '').replace('%', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_managers(html: str):
    """برمی‌گرداند: [{'code','name'}] به ترتیب صفحه (معمولاً بر اساس ارزش پورتفوی)."""
    seen, out = set(), []
    for code, name in re.findall(r'href="/m/holdings\.php\?m=([A-Za-z0-9]+)"[^>]*>([^<]+)</a>', html):
        if code in seen:
            continue
        seen.add(code)
        out.append({'code': code, 'name': name.strip()})
    return out


def parse_holdings(html: str):
    """برمی‌گرداند: [{'ticker','name','pct','shares','value_usd'}] از جدول grid."""
    m = re.search(r'<table[^>]*id="grid".*?</table>', html, re.S)
    if not m:
        return []
    out = []
    for row in _TR.findall(m.group(0)):
        cells = _TD.findall(row)
        if len(cells) < 7:
            continue  # ردیف سرستون یا خالی
        stock = cells[1]
        sym = re.search(r'sym=([A-Za-z0-9.\-]+)', stock)
        if not sym:
            continue
        name_m = re.search(r'<span>\s*-\s*(.*?)</span>', stock, re.S)
        out.append({
            'ticker': sym.group(1).upper(),
            'name': _text(name_m.group(1)) if name_m else '',
            'pct': _num(_text(cells[2])),
            'shares': _num(_text(cells[4])),
            'value_usd': _num(_text(cells[6])),
        })
    return out
