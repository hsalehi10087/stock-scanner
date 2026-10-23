"""آزمون سریع امتیاز کیفیت روی چند سهم از هر بازار (بدون تلگرام)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'market_intel'))
import quality as Q  # noqa: E402

T = {'us': ['NVDA', 'KLAC', 'INOD', 'FMC', 'APLD'], 'jp': ['6857.T', '7318.T', '8035.T', '5802.T', '3997.T', '4063.T'], 'cn': ['300308.SZ', '600519.SS'],
     'tw': ['2330.TW', '3017.TW'], 'in': ['TCS.NS', 'HEXT.NS']}
out = {m: {t: Q.score(t, m) for t in ts} for m, ts in T.items()}
os.makedirs('data/strategy_lab', exist_ok=True)
json.dump(out, open('data/strategy_lab/quality_probe.json', 'w'), indent=1, default=str)
for m, d in out.items():
    for t, r in d.items():
        print(m, t, r['score'], r['known'], r['flags'], r['badges'])
