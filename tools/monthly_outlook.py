"""چشم‌انداز یک‌ماهه: از برچسب‌های یکتای همه‌ی فایل‌های data/analyst_views/<date>.json
سهم خبرهای صعودی/نزولی/خنثی را برای هر دارایی می‌شمارد (هر خبر یک بار) و در
data/analyst_outlook/<date>.json می‌نویسد. این «سهم خبرها»ست، نه پیش‌بینی قیمت."""
import json, glob, collections, datetime as dt, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = ['gold', 'silver', 'bitcoin', 'copper', 'oil', 'rates']
fs = sorted(glob.glob(os.path.join(ROOT, 'data/analyst_views/2026-*.json')))
lab = {a: {} for a in A}
for f in fs:
    d = json.load(open(f))
    for l in d.get('labels', []):
        lab[l['asset']][l['id']] = (l['label'], d['date'])
cut = (dt.date.today() - dt.timedelta(days=7)).isoformat()
def share(items):
    c = collections.Counter(items); n = sum(c.values())
    return {'n': n, **{k: round(100 * c[k] / n) if n else 0 for k in ('bull', 'bear', 'neutral')}}
out = {'date': dt.date.today().isoformat(), 'days_covered': len(fs), 'assets': {}}
for a in A:
    out['assets'][a] = {'month': share([v[0] for v in lab[a].values()]),
                        'last7d': share([v[0] for v in lab[a].values() if v[1] >= cut])}
os.makedirs(os.path.join(ROOT, 'data/analyst_outlook'), exist_ok=True)
p = os.path.join(ROOT, f"data/analyst_outlook/{out['date']}.json")
json.dump(out, open(p, 'w'), ensure_ascii=False, indent=1)
print(p)
