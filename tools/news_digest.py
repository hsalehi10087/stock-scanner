"""ورودی آماده برای کار روزانه‌ی «خبرخوان بازار» (Claude).

خبرهای N ساعت اخیر را از سه فایل آخر data/news می‌خواند، تکراری‌ها را حذف می‌کند و برای هر دارایی
فهرستی فشرده (id، ناشر، تیتر، خلاصه یا ابتدای متن) چاپ می‌کند. هر خبر فقط زیر دارایی‌های «primary»
خودش می‌آید (دارایی‌ای که در تیتر آمده)، تا یک خبر بیت‌کوین در شمارش نرخ بهره هم حساب نشود.

استفاده:
  python3 tools/news_digest.py                 # ۳۶ ساعت اخیر، همه‌ی دارایی‌ها
  python3 tools/news_digest.py --hours 36 --asset oil --chars 1200
  python3 tools/news_digest.py --stats         # فقط تعداد خبرها و تازه‌ترین زمان جمع‌آوری
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
from news_collect import apply_blocklist, load_blocklist, split_publisher, tags, title_key  # noqa: E402

ASSETS = ['gold', 'silver', 'bitcoin', 'copper', 'oil', 'rates']


def parse_time(s):
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        try:
            t = parsedate_to_datetime(s)
        except (TypeError, ValueError):
            return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def load(hours, now=None, news_dir=None, dedupe=True):
    """خبرهای پنجره‌ی زمانی، بدون تکرار، به ترتیب زمان (جدیدترها اول)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    news_dir = news_dir or os.path.join(ROOT, 'data', 'news')
    cut = now - dt.timedelta(hours=hours)
    files = sorted(glob.glob(os.path.join(news_dir, '20*.jsonl')))[-3:]
    seen_id, seen_title, out = set(), set(), []
    block = load_blocklist()
    for f in files:
        for ln in open(f, encoding='utf-8'):
            try:
                n = json.loads(ln)
            except ValueError:
                continue
            t = parse_time(n.get('published')) or parse_time(n.get('collected'))
            if not t or t < cut or t > now + dt.timedelta(hours=2):
                continue
            tk = title_key(n.get('title', ''))
            if n.get('id') in seen_id or (dedupe and tk and tk in seen_title):
                continue
            seen_id.add(n.get('id'))
            seen_title.add(tk)
            if 'primary' not in n:      # خبرهای قدیمی‌تر از این تغییر
                n['primary'] = [a for a in tags(split_publisher(n.get('title', ''))[0]) if a in n.get('assets', [])] \
                    or n.get('assets', [])
            if not n.get('publisher'):
                n['publisher'] = split_publisher(n.get('title', ''))[1] or n.get('source', '')
            kept = apply_blocklist(n, n.get('assets', []), block)    # خبرهای قدیمی‌تر از فهرست سیاه
            if not kept:
                continue
            n['assets'], n['primary'] = kept, [x for x in n['primary'] if x in kept] or kept
            n['_t'] = t
            out.append(n)
    out.sort(key=lambda n: n['_t'], reverse=True)
    return out, files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hours', type=float, default=36)
    ap.add_argument('--asset', choices=ASSETS)
    ap.add_argument('--chars', type=int, default=400, help='حداکثر طول متن هر خبر')
    ap.add_argument('--stats', action='store_true')
    a = ap.parse_args()
    items, files = load(a.hours)
    newest = max((parse_time(n.get('collected')) for n in items if n.get('collected')), default=None)
    print(f'files={[os.path.basename(f) for f in files]} unique_items={len(items)} '
          f'with_body={sum(bool(n.get("body")) for n in items)} newest_collected={newest}')
    for asset in ([a.asset] if a.asset else ASSETS):
        rows = [n for n in items if asset in n['primary']]
        print(f'\n===== {asset} ({len(rows)})')
        if a.stats:
            continue
        for n in rows:
            text = (n.get('body') or n.get('summary') or '').strip()
            tag = 'BODY' if n.get('body') else 'SUM'
            title = split_publisher(n['title'])[0] if n.get('source', '').startswith('googlenews') else n['title']
            print(f"[{n['id']}] {n['_t']:%m-%d %H:%M} | {n['publisher']} | {title}")
            if text and not text.lower().startswith(title.lower()[:60]):
                print(f'    {tag}: {text[:a.chars]}')


if __name__ == '__main__':
    main()
