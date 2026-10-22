"""شکارچی روش — آزمون همه‌ی روش‌های پیاده‌شده (specs/*.yaml) و به‌روز کردن جدول نتایج."""
import datetime as dt
import glob
import json
import os
import sys
import traceback

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = os.path.join(ROOT, 'strategy_hunter', 'specs')
OUT = os.path.join(ROOT, 'data', 'strategy_hunter')


def main():
    os.makedirs(OUT, exist_ok=True)
    results, cache = {}, {}
    for f in sorted(glob.glob(os.path.join(SPECS, '*.yaml'))):
        spec = yaml.safe_load(open(f, encoding='utf-8'))
        sid = spec['id']
        meta = {k: spec.get(k) for k in ('name', 'name_fa', 'source', 'source_url', 'claim', 'claimed_return',
                                          'asset_class', 'symbols', 'added', 'status', 'reason_not_testable')}
        meta['added'] = str(meta['added'])
        if spec.get('status') != 'implemented':
            results[sid] = {**meta, 'verdict': 'غیرقابل آزمون: ' + (spec.get('reason_not_testable') or '')}
            continue
        try:
            key = (tuple(spec['symbols']), spec.get('timeframe', '1d'), spec.get('start', '2010-01-01'))
            if key not in cache:
                cache[key] = E.load_prices(*([list(key[0])] + list(key[1:])))
            res = E.run_spec(spec, cache[key])
            results[sid] = {**meta, **res}
        except Exception as e:
            traceback.print_exc()
            results[sid] = {**meta, 'verdict': f'خطای آزمون: {e!r}'[:200]}
    json.dump({'updated': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'results': results},
              open(os.path.join(OUT, 'results.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    for sid, r in results.items():
        print(sid, r.get('verdict'), r.get('out_sample'), r.get('forward_usd'))


if __name__ == '__main__':
    main()
