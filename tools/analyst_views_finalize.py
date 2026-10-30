"""پیش‌نویس «خبرخوان بازار» را بررسی و کامل می‌کند و در latest.json و فایل تاریخ‌دار می‌نویسد.

کار روزانه‌ی Claude فقط درک خبر را انجام می‌دهد: stance، summary_fa، views، watch_fa و برچسب هر خبر
(labels). چیزهایی که باید قطعی و قابل‌حسابرسی باشند را این اسکریپت می‌سازد:
  - counts      از روی labels شمرده می‌شود (نه تخمین)
  - confidence  از تعداد خبرهای جهت‌دار و تعداد ناشرهای مستقل
  - change_fa   مقایسه‌ی stance با آخرین فایل تاریخ‌دار قبلی
  - date        تاریخ گزارش ساعت ۰۱:۳۰ UTC بعدی (اگر الان قبل از ۰۱:۳۰ است، امروز؛ وگرنه فردا)
  - generated_at
و اگر چیزی ناقص یا نامعتبر باشد با کد خطا خارج می‌شود و هیچ فایلی نمی‌نویسد.

استفاده:
  python3 tools/analyst_views_finalize.py draft.json            # بررسی و نوشتن
  python3 tools/analyst_views_finalize.py draft.json --check    # فقط بررسی
ساختار پیش‌نویس: مثل latest.json، به‌علاوه‌ی
  "labels": [{"id": "<id خبر از news_digest>", "asset": "gold", "label": "bull|bear|neutral"}, ...]
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from news_digest import load  # noqa: E402

OUTDIR = os.path.join(ROOT, 'data', 'analyst_views')
ASSETS = ['gold', 'silver', 'bitcoin', 'copper', 'oil', 'rates']
STANCES = {'صعودی', 'نزولی', 'خنثی', 'دوگانه'}
LABELS = {'bull', 'bear', 'neutral'}
NO_NEWS = 'امروز خبر یا نظر قابل‌اتکایی نبود'


def report_date(now):
    cut = now.replace(hour=1, minute=30, second=0, microsecond=0)
    return (now.date() if now < cut else now.date() + dt.timedelta(days=1)).isoformat()


def confidence(n_dir, n_pubs):
    if n_dir >= 8 and n_pubs >= 5:
        return 'بالا'
    if n_dir >= 3 and n_pubs >= 2:
        return 'متوسط'
    return 'پایین'


def previous(date):
    files = sorted(f for f in glob.glob(os.path.join(OUTDIR, '20??-??-??.json'))
                   if os.path.basename(f)[:10] < date)
    for f in reversed(files):
        try:
            return json.load(open(f, encoding='utf-8'))
        except ValueError:
            continue
    return None


def finalize(draft, now=None, news=None):
    """(نتیجه، فهرست خطاها) را برمی‌گرداند."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if news is None:
        news, _ = load(60, now=now, dedupe=False)
    by_id = {n['id']: n for n in news}
    errs = []
    v = {'date': report_date(now), 'generated_at': now.isoformat(timespec='seconds'),
         'articles_read': draft.get('articles_read') or len(news), 'method': draft.get('method', ''),
         'assets': {}, 'watch_fa': (draft.get('watch_fa') or '').strip()}
    labels = draft.get('labels') or []
    good = []
    for i, lb in enumerate(labels):
        if lb.get('asset') not in ASSETS or lb.get('label') not in LABELS:
            errs.append(f'labels[{i}]: asset/label نامعتبر {lb}')
        elif lb.get('id') not in by_id:
            errs.append(f'labels[{i}]: id {lb.get("id")} در خبرهای ۶۰ ساعت اخیر نیست')
        else:
            good.append(lb)
    uniq = {(lb['id'], lb['asset']): lb for lb in good}           # هر خبر برای هر دارایی یک بار
    prev = previous(v['date'])
    for a in ASSETS:
        d = (draft.get('assets') or {}).get(a) or {}
        mine = [lb for lb in uniq.values() if lb['asset'] == a]
        counts = {k: sum(lb['label'] == k for lb in mine) for k in ('bull', 'bear', 'neutral')}
        directional = [lb for lb in mine if lb['label'] != 'neutral']
        pubs = {by_id[lb['id']].get('publisher') or by_id[lb['id']].get('source') for lb in directional}
        stance = d.get('stance') or 'خنثی'
        summary = (d.get('summary_fa') or '').strip()
        if stance not in STANCES:
            errs.append(f'{a}: stance نامعتبر «{stance}»')
        if not mine and not summary:
            summary = NO_NEWS
        if not summary:
            errs.append(f'{a}: summary_fa خالی است')
        views = d.get('views') or []
        if len(views) > 2:
            errs.append(f'{a}: بیش از ۲ view')
        for j, w in enumerate(views):
            if not (w.get('who') and w.get('view_fa') and str(w.get('url', '')).startswith('http')):
                errs.append(f'{a}.views[{j}]: who/view_fa/url ناقص')
        out = {'stance': stance, 'counts': counts, 'confidence': confidence(len(directional), len(pubs)),
               'summary_fa': summary, 'views': views[:2]}
        old = ((prev or {}).get('assets') or {}).get(a, {}).get('stance')
        out['prev_stance'] = old
        out['change_fa'] = f'از «{old}» به «{stance}»' if old and old != stance else ''
        v['assets'][a] = out
    if not v['watch_fa']:
        errs.append('watch_fa خالی است')
    v['labels'] = sorted(uniq.values(), key=lambda lb: (lb['asset'], lb['id']))
    return v, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('draft')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    v, errs = finalize(json.load(open(a.draft, encoding='utf-8')))
    for e in errs:
        print('ERROR', e)
    for k, x in v['assets'].items():
        print(f"{k:8s} {x['stance']:7s} conf={x['confidence']:5s} counts={x['counts']} {x['change_fa']}")
    if errs:
        sys.exit(1)
    if a.check:
        return
    s = json.dumps(v, ensure_ascii=False, indent=1) + '\n'
    for name in ('latest.json', f"{v['date']}.json"):
        open(os.path.join(OUTDIR, name), 'w', encoding='utf-8').write(s)
    print('written', v['date'])


if __name__ == '__main__':
    main()
