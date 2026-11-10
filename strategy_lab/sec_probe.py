"""آزمون دسترسی به SEC از GitHub: خلاصه‌ی عددهای رسمی چند سهم آمریکایی."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
import sec_check as SC  # noqa: E402

out = {t: SC.check(t) for t in ['AAPL', 'NVDA', 'EXPD', 'CROX', 'MRVL', 'BTSG']}
os.makedirs(os.path.join(ROOT, 'data', 'strategy_lab'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'data', 'strategy_lab', 'sec_probe.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
