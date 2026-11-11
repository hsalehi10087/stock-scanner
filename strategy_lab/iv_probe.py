"""بررسی پوشش ارزش ذاتی: سهم‌هایی که در نسخه‌ی قبلی خالی ماندند را با روش تازه دوباره حساب می‌کند."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'market_intel'))
import intrinsic as IV  # noqa: E402

old = json.load(open(IV.CACHE, encoding='utf-8'))
blank = [k for k, v in old.items() if not v.get('iv')]
out = {}
for t in blank:
    IV._load().pop(t, None)
    r = IV.value(t)
    out[t] = r
    print(t, r, IV.label(r))
cnt = Counter('iv' if r.get('iv') else r.get('reason') for r in out.values())
os.makedirs('data/strategy_lab/iv_probe', exist_ok=True)
json.dump({'before_blank': len(blank), 'after': cnt, 'rows': out}, open('data/strategy_lab/iv_probe/result.json', 'w'),
          ensure_ascii=False, indent=1)
print(cnt)
