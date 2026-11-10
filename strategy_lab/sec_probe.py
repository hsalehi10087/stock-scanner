"""آزمون دسترسی به SEC از GitHub."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
import sec_check as SC  # noqa: E402
import sec_facts as F  # noqa: E402

out = {'ua': SC.UA}
f = F.Fetcher(ua=SC.UA)
for name, url in [('tickers', F.TICKERS_URL), ('facts_aapl', F.FACTS_URL % '0000320193')]:
    try:
        d = f.json(url, 'x')
        out[name] = f'ok {len(d)}'
    except Exception as e:
        out[name] = f'{type(e).__name__}: {e}'
out['check'] = {t: SC.check(t) for t in ['AAPL', 'NVDA', 'EXPD', 'CROX', 'MRVL', 'BTSG']}
os.makedirs(os.path.join(ROOT, 'data', 'strategy_lab'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'data', 'strategy_lab', 'sec_probe.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
