"""ایجنت «احتمال رشد تکنیکال و بنیادی — بورس ایران» (بخش پایتونی؛ بخش داده در مرورگر کامپیوتر ایران اجرا می‌شود).

مرورگر (iran/browser/*.js) داده‌ی tsetmc و کدال را می‌گیرد؛ این اسکریپت:
  plan   results.json            ← فهرست نمادهایی که رشد کدالشان باید گرفته شود (کش ۳۰ روزه؛ نمادهای ناموفق بعد از ۷ روز)
  merge  results.json codal.json track.json
                                 ← کش کدال را به‌روز می‌کند، صافی رشد را اعمال می‌کند، سیگنال تازه را در تاریخچه می‌نویسد
                                   و پیام روزانه (سیگنال‌ها + بهترین/بدترین از روز سیگنال) را می‌سازد.
قاعده‌ی بنیادی: P/E پیش‌بینی ≤ P/E گروه (از tsetmc)  و  رشد فروش > ۱۰٪  و  رشد سود خالص > ۱۵٪ (کدال، آخرین صورت مالی،
با تطبیق «درصد تغییر» خود کدال). اگر داده‌ی کدال نیامد، سهم «ناقص» حساب می‌شود و سیگنال نمی‌شود (عدد نمی‌سازیم).
"""
import csv
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'iran_growth')
HIST = os.path.join(OUT, 'history.csv')
CACHE = os.path.join(OUT, 'codal_cache.json')
TRACK = os.path.join(OUT, 'track.json')
MSG = os.path.join(OUT, 'today_message.txt')
COLS = ['date', 'ticker', 'name', 'price', 'setups', 'pe', 'sector_pe', 'chart', 'chart_score', 'sector', 'insCode',
        'rev_growth', 'np_growth']
SETUP_FA = {'longpat': 'الگوی نموداری بلندمدت', 'breakout': 'شکست با حجم', 'trend': 'روند صعودی منظم',
            'vcp': 'فشردگی نزدیک سقف', 'pullback': 'برگشت به میانگین ۵۰'}
MIN_REV, MIN_NP = 10.0, 15.0
OK_DAYS, MISS_DAYS = 30, 7
FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def nz(t):
    """نرمال‌سازی حروف عربی tsetmc به فارسی (ي→ی، ك→ک) تا با تاریخچه و کدال یکی شود."""
    return t.replace('ي', 'ی').replace('ك', 'ک').strip() if isinstance(t, str) else t


def norm_res(res):
    for x in res.get('final', []):
        for k in ('sym', 'name', 'sector', 'cp'):
            x[k] = nz(x.get(k))
    return res


def fa(x):
    return str(x).translate(FA)


def jload(p, default):
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return default


def need_fetch(cache, sym, today):
    c = cache.get(sym)
    if not c:
        return True
    age = (today - dt.date.fromisoformat(c['fetched'])).days
    return age >= (MISS_DAYS if c.get('none') else OK_DAYS)


def status(c):
    """pass / fail / missing"""
    if not c or c.get('none') or c.get('rev_growth') is None or c.get('np_growth') is None or not c.get('verified'):
        return 'missing'
    return 'pass' if c['rev_growth'] > MIN_REV and c['np_growth'] > MIN_NP else 'fail'


def plan(res_path):
    res = norm_res(jload(res_path, {'final': []}))
    cache = jload(CACHE, {})
    today = dt.date.today()
    syms = [x['sym'] for x in res['final'] if need_fetch(cache, x['sym'], today)]
    print(json.dumps({'syms': syms, 'total': len(res['final']), 'cached': len(res['final']) - len(syms)}, ensure_ascii=False))


def read_hist():
    if not os.path.exists(HIST):
        return []
    return list(csv.DictReader(open(HIST, encoding='utf-8')))


def merge(res_path, codal_path, track_path):
    res = norm_res(jload(res_path, {'meta': {}, 'final': []}))
    cod = jload(codal_path, {'res': {}, 'status': 'none'})
    trk = jload(track_path, [])
    today = dt.date.today()
    cache = jload(CACHE, {})
    for sym, rec in (cod.get('res') or {}).items():
        sym = nz(sym)
        rec = dict(rec)
        if rec.get('none') or rec.get('np_growth') is None:
            rec['none'] = rec.get('none') or 'no_data'
        rec['fetched'] = str(today)
        cache[sym] = rec
    os.makedirs(OUT, exist_ok=True)
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    passed, failed, missing = [], [], []
    for x in res['final']:
        c = cache.get(x['sym'])
        s = status(c)
        {'pass': passed, 'fail': failed, 'missing': missing}[s].append((x, c))

    hist = read_hist()
    have = {h['ticker'] for h in hist}
    new = []
    for x, c in passed:
        if x['sym'] in have:
            continue
        row = {'date': str(today), 'ticker': x['sym'], 'name': x['name'], 'price': x['last'], 'setups': '|'.join(x['st']),
               'pe': round(x['fpe'], 2), 'sector_pe': x['spe'], 'chart': x['cp'], 'chart_score': x['cps'],
               'sector': x.get('sector') or '', 'insCode': x['code'], 'rev_growth': c['rev_growth'], 'np_growth': c['np_growth']}
        hist.append(row)
        new.append(x['sym'])
    with open(HIST, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for h in hist:
            w.writerow({k: h.get(k, '') for k in COLS})
    json.dump({'date': str(today), 'items': trk}, open(TRACK, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    m = res.get('meta', {})
    L = ['📈 احتمال رشد تکنیکال و بنیادی — بورس ایران',
         f"آخرین جلسه: {m.get('date', '؟')} | {fa(m.get('total', '؟'))} سهم بررسی شد، {fa(m.get('liquid', '؟'))} تا نقدشوندگی کافی داشتند، "
         f"{fa(m.get('tech', '؟'))} تا از صافی تکنیکال گذشتند، {fa(len(res['final']))} تا از P/E؛ "
         f"از این‌ها رشد فروش و سود کدال: {fa(len(passed))} قبول، {fa(len(failed))} رد، {fa(len(missing))} ناقص.", '']
    if passed:
        L.append(f"سیگنال‌های امروز ({fa(len(passed))} سهم؛ {fa(len(new))} تازه):")
        for i, (x, c) in enumerate(sorted(passed, key=lambda p: (-len(p[0]['st']), -p[0]['rank']))[:12], 1):
            st = '، '.join(SETUP_FA.get(s, s) for s in x['st'])
            tag = ' 🆕' if x['sym'] in new else ''
            L += [f"{fa(i)}. {x['sym']} — {x['name'].strip()} | قیمت {x['last']:,.0f} ریال{tag}",
                  f"   📊 {st}", f"   🗺 {({'up': 'روند صعودی', 'down': 'روند نزولی', 'range': 'خنثی'}).get(x['cp'], x['cp'])} (امتیاز نمودار {fa(x['cps'])} از ۳)",
                  f"   ✅ P/E پیش‌بینی {x['fpe']:.2f} در برابر گروه {x['spe']} | رشد فروش {c['rev_growth']:+.1f}٪، رشد سود {c['np_growth']:+.1f}٪"
                  f" ({'تلفیقی' if c.get('consolidated') else 'شرکتی'}، دوره {c.get('period', '؟')})"]
    else:
        L.append('امروز سهمی از هر سه صافی (تکنیکال، P/E، رشد کدال) نگذشت.')
    if missing:
        L += ['', f"⚠️ رشد کدال برای {fa(len(missing))} سهم هنوز خوانده نشده (کدال محدودیت دارد؛ به‌تدریج تکمیل می‌شود): "
                  + '، '.join(x['sym'] for x, _ in missing[:15]) + (' …' if len(missing) > 15 else '')]
    ok = [t for t in trk if t.get('ret_pct') is not None]
    old = [t for t in ok if (today - dt.date.fromisoformat(t['date'])).days >= 1]
    if old:
        rk = sorted(old, key=lambda t: -t['ret_pct'])
        k = min(5, max(1, len(rk) // 2))
        L += ['', '🏆 بهترین سیگنال‌ها از روز سیگنال تا امروز']
        L += [f"{fa(i)}. {t['ticker']} (از {t['date'][5:].replace('-', '/')}): {t['ret_pct']:+.1f}٪ (بیشترین {t['max_pct']:+.1f}٪، کمترین {t['min_pct']:+.1f}٪)"
              for i, t in enumerate(rk[:k], 1)]
        L += ['⚠️ بدترین سیگنال‌ها از روز سیگنال تا امروز']
        L += [f"{fa(i)}. {t['ticker']} (از {t['date'][5:].replace('-', '/')}): {t['ret_pct']:+.1f}٪ (بیشترین {t['max_pct']:+.1f}٪، کمترین {t['min_pct']:+.1f}٪)"
              for i, t in enumerate(reversed(rk[-k:]), 1)]
        L.append('بازده با قیمت تعدیل‌شده‌ی tsetmc (افزایش سرمایه و سود نقدی) حساب شده؛ مقایسه با شاخص بورس هنوز ندارد.')
    L += ['', 'همه‌ی سیگنال‌های تازه در تاریخچه ثبت می‌شود و سود/زیانشان از روز سیگنال پیگیری می‌شود. صرفاً برای بررسی بیشتر؛ توصیه‌ی خرید نیست.']
    open(MSG, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    print(json.dumps({'new': new, 'pass': len(passed), 'fail': len(failed), 'missing': len(missing)}, ensure_ascii=False), file=sys.stderr)


OPT_MSG = os.path.join(OUT, 'options_message.txt')
OPT_JSON = os.path.join(OUT, 'options_today.json')
MAX_RATIO = 2.0  # قراردادی که نوسان ضمنی‌اش بیش از دو برابر نوسان واقعی پایه است «گران» حساب می‌شود و نمی‌آید


def options(res_path):
    """پیام «موقعیت های آپشن ایران» را از خروجی iran/browser/options_screen.js می‌سازد (فقط همان عددها)."""
    d = jload(res_path, None)
    if not d or d.get('error') or 'cov' not in d:
        sys.exit('options: نتیجه‌ی معتبر نیست: ' + json.dumps(d, ensure_ascii=False)[:200])
    os.makedirs(OUT, exist_ok=True)
    json.dump(d, open(OPT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    c = d['cov']

    def row(i, x, sign):
        return [f"{fa(i)}. {x['sym']} — {x['und']} (قیمت {x['S']:,.0f}) | اعمال {x['K']:,.0f} | سررسید {x['exp'][5:]} ({fa(x['dte'])} روز)",
                f"   قیمت آپشن {x['prem']:,.0f} ریال | سربه‌سر: پایه باید {abs(x['be']):.1f}٪ {sign} برود | {fa(x['trades'])} معامله",
                f"   نوسان ضمنی {fa(x['iv'])}٪ در برابر واقعی {fa(x['hv'])}٪ ({x['ratio']:.1f} برابر) | بازده ۲۰ روزه‌ی پایه {x['ret20']:+.1f}٪"]

    L = ['🎯 موقعیت های آپشن ایران',
         f"آخرین جلسه: {d.get('date', '؟')} | {fa(c['total'])} قرارداد، {fa(c['traded'])} تا معامله شدند روی {fa(d['unds'])} دارایی پایه؛ "
         f"{fa(d['liq'])} تا نقدشونده بودند ({fa(d['liqCalls'])} کال، {fa(d['liqPuts'])} پوت).", '']
    calls = [x for x in d.get('calls', []) if x['ratio'] <= MAX_RATIO]
    puts = [x for x in d.get('puts', []) if x['ratio'] <= MAX_RATIO]
    if calls:
        L.append('📈 کال (پایه بالای میانگین ۵۰ روزه؛ از ارزان به گران):')
        for i, x in enumerate(calls, 1):
            L += row(i, x, 'بالا')
    else:
        L.append('📈 کال: امروز کال نقدشونده‌ای با قیمت قابل‌قبول روی پایه‌ی صعودی نبود.')
    L.append('')
    if puts:
        L.append('📉 پوت (پایه زیر میانگین ۵۰ روزه؛ از ارزان به گران):')
        for i, x in enumerate(puts, 1):
            L += row(i, x, 'پایین')
    else:
        dn = d.get('undsDown') or []
        L.append('📉 پوت: امروز پوت نقدشونده‌ای با قیمت قابل‌قبول روی پایه‌ی نزولی نبود'
                 + (f" (پایه‌های زیر میانگین ۵۰ روزه: {'، '.join(dn[:8])})." if dn else '.'))
    L += ['', f"نوسان ضمنی با نرخ بهره‌ی {fa(d['rate'])}٪ حساب شده (میانه‌ی {fa(d['ratePairs'])} جفت کال/پوت بازار؛ نیمی از جفت‌ها بین {fa(d['rateLo'])} تا {fa(d['rateHi'])}٪)، پس تقریبی است. "
              'قیمت‌ها قیمت پایانی جلسه است.']
    skipped = c.get('unparsed', 0) + c.get('noUnd', 0) + c.get('noDate', 0)
    if skipped:
        L.append(f"⚠️ {fa(skipped)} قرارداد خوانده نشد (نام یا تاریخ ناشناخته).")
    L += ['صرفاً غربال‌گری برای بررسی بیشتر؛ توصیه‌ی خرید نیست. خریدار آپشن ممکن است کل مبلغ پرداختی را از دست بدهد.']
    open(OPT_MSG, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'plan':
        plan(sys.argv[2])
    elif cmd == 'merge':
        merge(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'options':
        options(sys.argv[2])
    else:
        sys.exit('plan | merge | options')
