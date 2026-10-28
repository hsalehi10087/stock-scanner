"""آزمون فهرست سهام کشورها با Yahoo screener."""
import json
import os

import yfinance as yf
from yfinance import EquityQuery as Q

out = {'version': yf.__version__}
for reg in ('kr', 'hk', 'gb', 'de', 'ca', 'au', 'us', 'in', 'jp', 'tw', 'cn'):
    syms, err = [], None
    try:
        q = Q('and', [Q('eq', ['region', reg]), Q('gt', ['intradaymarketcap', 300_000_000])])
        for off in range(0, 3000, 250):
            r = yf.screen(q, size=250, offset=off, sortField='intradaymarketcap', sortAsc=False)
            qs = r.get('quotes', [])
            syms += [(x['symbol'], x.get('shortName') or x.get('longName') or '', x.get('exchange')) for x in qs]
            if len(qs) < 250:
                break
    except Exception as e:
        err = repr(e)[:200]
    out[reg] = {'n': len(syms), 'err': err, 'sample': syms[:8], 'exchanges': sorted({s[2] for s in syms if s[2]})}
os.makedirs('data/strategy_lab', exist_ok=True)
json.dump(out, open('data/strategy_lab/screen_probe.json', 'w'), indent=1, ensure_ascii=False)
