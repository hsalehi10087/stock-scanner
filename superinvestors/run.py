"""گزارش سرمایه‌گذاران بزرگ (Dataroma)

حالت‌ها:
  python superinvestors/run.py --fetch            # دریافت پورتفوی‌ها، ذخیره‌ی عکس امروز، و ارسال گزارش
  python superinvestors/run.py --fetch --first    # گزارش اولیه: ۱۰ سرمایه‌گذار برتر با ۵ سهم اول هرکدام
  python superinvestors/run.py --date 2026-10-14  # ارسال تغییرات همان روز (از عکس‌های ذخیره‌شده)

قانون تغییر: معامله‌ای که ارزشش بیش از 5٪ کل پورتفوی همان سرمایه‌گذار باشد.
  ارزش معامله = (تغییر تعداد سهم) × (قیمت فعلی سهم)، قیمت = value / shares.
"""
import argparse
import datetime as dt
import html
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from parse import parse_managers, parse_holdings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_DIR = os.path.join(ROOT, 'data', 'superinvestors')
BASE = 'https://www.dataroma.com'
TOP_N = 30          # تعداد سرمایه‌گذاران بررسی‌شده
THRESHOLD_PCT = 5.0 # درصد از کل پورتفوی
UA = {'User-Agent': 'Mozilla/5.0 (compatible; superinvestors-report/1.0)'}


def fetch_snapshot(top_n=TOP_N):
    r = requests.get(f'{BASE}/m/managers.php', headers=UA, timeout=30)
    r.raise_for_status()
    managers = parse_managers(r.text)[:top_n]
    snap = {'date': dt.date.today().isoformat(), 'managers': []}
    for mg in managers:
        time.sleep(1.0)
        try:
            rr = requests.get(f"{BASE}/m/holdings.php?m={mg['code']}", headers=UA, timeout=30)
            rr.raise_for_status()
            holdings = parse_holdings(rr.text)
        except Exception as e:  # ادامه با بقیه
            print(f"⚠️ {mg['code']}: {e}", file=sys.stderr)
            continue
        snap['managers'].append({**mg, 'holdings': holdings})
    return snap


def save_snapshot(snap):
    os.makedirs(SNAP_DIR, exist_ok=True)
    path = os.path.join(SNAP_DIR, f"{snap['date']}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    return path


def load_snapshot(date_str):
    with open(os.path.join(SNAP_DIR, f'{date_str}.json'), encoding='utf-8') as f:
        return json.load(f)


def previous_snapshot_date(date_str):
    if not os.path.isdir(SNAP_DIR):
        return None
    dates = sorted(f[:-5] for f in os.listdir(SNAP_DIR) if f.endswith('.json') and f[:-5] < date_str)
    return dates[-1] if dates else None


def _price(h):
    if h.get('shares'):
        return (h.get('value_usd') or 0) / h['shares']
    return 0.0


def portfolio_value(holdings):
    return sum((h.get('value_usd') or 0) for h in holdings) or 0.0


def diff_snapshots(prev, cur):
    """تغییرات معاملاتی بالای آستانه، به تفکیک سرمایه‌گذار."""
    prev_map = {m['code']: m for m in prev['managers']} if prev else {}
    results = []
    for m in cur['managers']:
        pm = prev_map.get(m['code'])
        if not pm:
            continue
        pv = portfolio_value(pm['holdings']) or portfolio_value(m['holdings'])
        if not pv:
            continue
        old = {h['ticker']: h for h in pm['holdings']}
        new = {h['ticker']: h for h in m['holdings']}
        changes = []
        for t in set(old) | set(new):
            o, n = old.get(t), new.get(t)
            o_sh = (o or {}).get('shares') or 0
            n_sh = (n or {}).get('shares') or 0
            if o_sh == n_sh:
                continue
            price = _price(n) if n else _price(o)
            trade_value = (n_sh - o_sh) * price
            pct = abs(trade_value) / pv * 100
            if pct < THRESHOLD_PCT:
                continue
            if o_sh == 0:
                action = 'خرید جدید'
            elif n_sh == 0:
                action = 'فروش کامل'
            elif n_sh > o_sh:
                action = 'افزایش'
            else:
                action = 'کاهش'
            changes.append({'ticker': t, 'name': (n or o).get('name', ''), 'action': action,
                            'shares_delta': n_sh - o_sh, 'pct_of_portfolio': round(pct, 1)})
        if changes:
            changes.sort(key=lambda c: -c['pct_of_portfolio'])
            results.append({'manager': m['name'], 'code': m['code'], 'changes': changes})
    return results


def first_report_lines(snap, top_managers=10, top_holdings=5):
    lines = [f"📊 <b>گزارش اولیه: سرمایه‌گذاران بزرگ</b> ({snap['date']})", ""]
    for m in snap['managers'][:top_managers]:
        lines.append(f"<b>{html.escape(m['name'])}</b>")
        top = sorted(m['holdings'], key=lambda h: -(h.get('pct') or 0))[:top_holdings]
        for h in top:
            lines.append(f"  • {h['ticker']} ({html.escape(h['name'])}): {h['pct']}%")
        lines.append("")
    return lines


def changes_lines(date_str, prev_date, results):
    head = f"📈 <b>تغییرات بزرگ سرمایه‌گذاران</b> ({date_str})"
    if prev_date:
        head += f"\nمقایسه با: {prev_date}"
    if not results:
        return [head, "", "تغییر بالای ۵٪ پورتفوی ثبت نشد."]
    lines = [head, ""]
    for r in results:
        lines.append(f"<b>{html.escape(r['manager'])}</b>")
        for c in r['changes']:
            lines.append(f"  • {c['action']}: {c['ticker']} ({html.escape(c['name'])}) — {c['pct_of_portfolio']}٪ پورتفوی")
        lines.append("")
    return lines


def chunks(lines, limit=3800):
    out, cur = [], ''
    for ln in lines:
        if len(cur) + len(ln) + 1 > limit:
            out.append(cur)
            cur = ''
        cur += ln + '\n'
    if cur.strip():
        out.append(cur)
    return out


def send(text_chunks, token, chat_ids):
    ok = True
    for cid in chat_ids:
        for ch in text_chunks:
            r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                              data={'chat_id': cid, 'text': ch, 'parse_mode': 'HTML'}, timeout=20)
            if r.status_code != 200 or '"ok":true' not in r.text:
                print(f'❌ ارسال به {cid} ناموفق: {r.status_code} {r.text[:200]}', file=sys.stderr)
                ok = False
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true')
    ap.add_argument('--first', action='store_true')
    ap.add_argument('--date', help='YYYY-MM-DD: ارسال تغییرات همان تاریخ')
    args = ap.parse_args()

    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_ids = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chat_ids:
        print('❌ TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده', file=sys.stderr)
        return 1

    if args.fetch:
        snap = fetch_snapshot()
        path = save_snapshot(snap)
        print(f'✅ عکس ذخیره شد: {path} ({len(snap["managers"])} سرمایه‌گذار)')
        date_str = snap['date']
    else:
        date_str = args.date or dt.date.today().isoformat()
        snap = load_snapshot(date_str)

    if args.first:
        lines = first_report_lines(snap)
    else:
        prev_date = previous_snapshot_date(date_str)
        prev = load_snapshot(prev_date) if prev_date else None
        results = diff_snapshots(prev, snap)
        lines = changes_lines(date_str, prev_date, results)

    return 0 if send(chunks(lines), token, chat_ids) else 2


if __name__ == '__main__':
    sys.exit(main())
