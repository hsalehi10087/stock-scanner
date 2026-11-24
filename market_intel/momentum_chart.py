"""نمودار روزانه‌ی «بازدهی ۳ ماهه» شش دارایی + هشدار جابه‌جایی رتبه‌ی اول.

دارایی‌ها: طلا، نقره، بیت‌کوین، مس، نفت، دلار (شاخص دلار آمریکا).
بازدهی ۳ ماهه = قیمت امروز نسبت به قیمت ۹۱ روز پیش، به درصد.
هشدار: هر وقت دارایی‌ای که بالاترین بازدهی ۳ ماهه را دارد عوض شود.

خروجی‌ها: data/momentum/latest.png ، history.csv ، state.json ، و ارسال به تلگرام.
متغیرها: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  (بدونشان فقط فایل ساخته می‌شود)
اجرای آزمایشی با داده‌ی ساختگی (فقط برای دیدن شکل نمودار):  python3 market_intel/momentum_chart.py --demo
این نمودار توصیه‌ی خرید نیست؛ فقط نشان می‌دهد در ۳ ماه گذشته کدام دارایی جلوتر بوده است.
"""
import datetime as dt
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'momentum')
DAYS = 91            # ۳ ماه
SHOW = 90            # چند روز اخیر در نمودار خطی
# کلید: (نماد یاهو، نام فارسی، رنگ)
ASSETS = {
    'gold':    ('GC=F',     'طلا',      '#D4A017'),
    'silver':  ('SI=F',     'نقره',     '#7F8C9A'),
    'bitcoin': ('BTC-USD',  'بیت‌کوین', '#F7931A'),
    'copper':  ('HG=F',     'مس',       '#B5651D'),
    'oil':     ('CL=F',     'نفت',      '#2C3E50'),
    'dollar':  ('DX-Y.NYB', 'دلار',     '#2E8B57'),
}
GREEN, RED, INK, GREY = '#1B8A5A', '#C0392B', '#1F2937', '#6B7280'

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAVE_FA = True
except Exception:  # بدون کتابخانه‌ی فارسی‌ساز، برچسب‌ها انگلیسی می‌شوند
    HAVE_FA = False

EN = {'gold': 'Gold', 'silver': 'Silver', 'bitcoin': 'Bitcoin', 'copper': 'Copper', 'oil': 'Oil', 'dollar': 'US Dollar'}
plt.rcParams['font.family'] = 'DejaVu Sans'
# matplotlib ۳٫۱۱ به بالا با libraqm خودش شکل‌دهی و راست‌به‌چپ را انجام می‌دهد؛ نسخه‌های قدیمی‌تر به reshaper و bidi نیاز دارند
RAQM = tuple(int(x) for x in matplotlib.__version__.split('.')[:2]) >= (3, 11)
HAVE_FA = HAVE_FA or RAQM


def fa(s):
    """متن فارسی را برای matplotlib درست (راست‌به‌چپ و چسبیده) می‌کند."""
    return s if RAQM else (get_display(arabic_reshaper.reshape(s)) if HAVE_FA else s)


def name(k):
    return fa(ASSETS[k][1]) if HAVE_FA else EN[k]


def digits(s):
    return str(s).translate(str.maketrans('0123456789.-+%', '۰۱۲۳۴۵۶۷۸۹٫−+٪')) if HAVE_FA else str(s)


def pct(v, sign=True):
    t = digits(f"{v:+.1f}%" if sign else f"{v:.1f}%")
    return '\u202a' + t + '\u202c' if RAQM else t   # عدد همیشه چپ‌به‌راست خوانده شود


def fetch(demo=False):
    """جدول قیمت روزانه (ستون = دارایی) با پر شدن روزهای تعطیل از روز قبل."""
    if demo:
        rng = np.random.default_rng(7)
        idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=300)
        drift = {'gold': .0006, 'silver': .0002, 'bitcoin': -.0008, 'copper': .0009, 'oil': -.0004, 'dollar': .0001}
        vol = {'gold': .008, 'silver': .015, 'bitcoin': .025, 'copper': .012, 'oil': .016, 'dollar': .003}
        return pd.DataFrame({k: 100 * np.exp(np.cumsum(rng.normal(drift[k], vol[k], len(idx)))) for k in ASSETS}, index=idx)
    import yfinance as yf
    raw = yf.download([v[0] for v in ASSETS.values()], period='1y', interval='1d', progress=False, auto_adjust=True)['Close']
    inv = {v[0]: k for k, v in ASSETS.items()}
    raw = raw.rename(columns=inv)
    raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
    full = pd.date_range(raw.index.min(), raw.index.max())
    return raw.reindex(full).ffill()


def three_month(df):
    """بازدهی ۳ ماهه‌ی هر روز (٪)."""
    return (df / df.shift(DAYS) - 1) * 100


def draw(r3, path, last_change=None):
    now = r3.dropna(how='all').iloc[-1].dropna().sort_values(ascending=False)
    day = r3.dropna(how='all').index[-1]
    leader = now.index[0]
    fig = plt.figure(figsize=(11, 13), dpi=140, facecolor='white')
    gs = fig.add_gridspec(3, 1, height_ratios=[0.42, 1.5, 1.9], hspace=0.32, left=0.08, right=0.93, top=0.97, bottom=0.05)

    # ۱) عنوان و راهنمای ساده
    ax0 = fig.add_subplot(gs[0]); ax0.axis('off')
    ax0.text(0.5, 0.92, fa('کدام دارایی در ۳ ماه گذشته بیشتر سود داده؟'), ha='center', fontsize=25, fontweight='bold', color=INK)
    ax0.text(0.5, 0.50, fa('اگر ۳ ماه پیش این دارایی را خریده بودی، امروز چند درصد سود (سبز) یا زیان (قرمز) داشتی'),
             ha='center', fontsize=14, color=GREY)
    ax0.text(0.5, 0.12, digits(day.strftime('%Y-%m-%d')) + '  |  ' + fa('برترین الان: ') + name(leader) + ' ' + pct(now.iloc[0]),
             ha='center', fontsize=17, color=GREEN, fontweight='bold')
    if last_change:
        ax0.text(0.5, -0.22, fa(last_change), ha='center', fontsize=12, color=RED)

    # ۲) رتبه‌بندی امروز (میله‌ای)
    ax1 = fig.add_subplot(gs[1])
    order = list(now.index)[::-1]
    vals = [now[k] for k in order]
    bars = ax1.barh([name(k) for k in order], vals, color=[GREEN if v >= 0 else RED for v in vals], height=0.62)
    span = max(abs(min(vals + [0])), abs(max(vals + [0])), 1)
    ax1.set_xlim(min(vals + [0]) - span * .22, max(vals + [0]) + span * .22)
    for b, v in zip(bars, vals):
        ax1.text(v + (span * .03 if v >= 0 else -span * .03), b.get_y() + b.get_height() / 2, pct(v),
                 va='center', ha='left' if v >= 0 else 'right', fontsize=15, fontweight='bold', color=INK)
    ax1.axvline(0, color=INK, lw=1.2)
    ax1.set_title(fa('رتبه‌بندی امروز (بالا = بهتر)'), fontsize=16, color=INK, pad=10)
    ax1.tick_params(axis='y', labelsize=16, length=0); ax1.tick_params(axis='x', labelsize=11, colors=GREY)
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: digits(f'{v:.0f}%')))
    for s in ('top', 'right', 'left'):
        ax1.spines[s].set_visible(False)
    ax1.grid(axis='x', color='#E5E7EB')
    ax1.set_axisbelow(True)

    # ۳) روند ۹۰ روز اخیر
    ax2 = fig.add_subplot(gs[2])
    h = r3.dropna(how='all').iloc[-SHOW:]
    for k in ASSETS:
        if k not in h:
            continue
        lw = 3.6 if k == leader else 2.0
        ax2.plot(h.index, h[k], color=ASSETS[k][2], lw=lw, alpha=1 if k == leader else .85, solid_capstyle='round')
    ax2.axhline(0, color=INK, lw=1)
    # برچسب انتهای هر خط (با فاصله‌گذاری تا روی هم نیفتند)
    ends = sorted([(h[k].dropna().iloc[-1], k) for k in ASSETS if k in h and h[k].notna().any()])
    ymin, ymax = ax2.get_ylim(); gap = (ymax - ymin) * 0.07
    placed = []
    for v, k in ends:
        y = v if not placed or v - placed[-1] >= gap else placed[-1] + gap
        placed.append(y)
        ax2.annotate(name(k) + ' ' + pct(v), xy=(h.index[-1], v), xytext=(h.index[-1] + pd.Timedelta(days=2), y),
                     fontsize=12, color=ASSETS[k][2], fontweight='bold', va='center', annotation_clip=False)
    ax2.set_xlim(h.index[0], h.index[-1] + pd.Timedelta(days=24))
    ax2.set_title(fa('بازدهی ۳ ماهه در ۹۰ روز اخیر (هر خط = یک دارایی)'), fontsize=16, color=INK, pad=10)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: digits(f'{v:.0f}%')))
    ax2.tick_params(labelsize=11, colors=GREY)
    ax2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%m/%d'))
    ax2.set_xticks([t for t in ax2.get_xticks() if t <= matplotlib.dates.date2num(h.index[-1])])
    for s in ('top', 'right'):
        ax2.spines[s].set_visible(False)
    ax2.grid(color='#E5E7EB'); ax2.set_axisbelow(True)
    fig.text(0.5, 0.012, fa('فقط تاریخچه را نشان می‌دهد و توصیه‌ی خرید یا فروش نیست. «دلار» = شاخص دلار آمریکا.'),
             ha='center', fontsize=10.5, color=GREY)
    fig.savefig(path, facecolor='white'); plt.close(fig)
    return leader, now


def send(token, chat, method, **kw):
    import requests
    r = requests.post(f'https://api.telegram.org/bot{token}/{method}', timeout=60, **kw)
    ok = r.status_code == 200 and '"ok":true' in r.text
    if not ok:
        print(f'❌ telegram {method}: {r.status_code} {r.text[:200]}', file=sys.stderr)
    return ok


def main():
    demo = '--demo' in sys.argv
    os.makedirs(OUT, exist_ok=True)
    df = fetch(demo)
    r3 = three_month(df)
    last = r3.dropna(how='all')
    if last.empty or last.iloc[-1].notna().sum() < 3:
        print('❌ داده‌ی کافی نیست', file=sys.stderr)
        return 1
    st_path = os.path.join(OUT, 'state.json')
    st = {}
    if os.path.exists(st_path) and not demo:
        st = json.load(open(st_path, encoding='utf-8'))
    prev = st.get('leader')
    png = os.path.join(OUT, 'demo.png' if demo else 'latest.png')
    leader, now = draw(r3, png)
    changed = bool(prev) and prev != leader
    if changed:  # دوباره با یادداشت تغییر نمودار را بکش
        note = f"هشدار: برترین دارایی از «{ASSETS[prev][1]}» به «{ASSETS[leader][1]}» عوض شد"
        draw(r3, png, last_change=note)
    if demo:
        print('demo', png, leader, now.round(1).to_dict())
        return 0
    day = last.index[-1].strftime('%Y-%m-%d')
    ranking = '\n'.join(f"{i + 1}. {ASSETS[k][1]}: {v:+.1f}٪" for i, (k, v) in enumerate(now.items()))
    # تاریخچه‌ی روزانه برای ثبت
    row = {'date': day, **{k: round(float(now.get(k, np.nan)), 2) for k in ASSETS}, 'leader': leader}
    hp = os.path.join(OUT, 'history.csv')
    hist = pd.read_csv(hp) if os.path.exists(hp) else pd.DataFrame(columns=list(row))
    hist = pd.concat([hist[hist['date'] != day], pd.DataFrame([row])]).sort_values('date')
    hist.to_csv(hp, index=False)
    json.dump({'leader': leader, 'date': day, 'prev_leader': prev if changed else st.get('prev_leader'),
               'last_change_date': day if changed else st.get('last_change_date')},
              open(st_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chats = [c.strip() for c in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if c.strip()]
    if not token or not chats:
        print('ℹ️ توکن تلگرام نیست؛ فقط فایل‌ها ساخته شد')
        return 0
    cap = (f'<b>📊 بازدهی ۳ ماهه‌ی دارایی‌ها — {day}</b>\n\n{ranking}\n\n'
           f'🏆 برترین الان: <b>{ASSETS[leader][1]}</b>\n<i>فقط تاریخچه است، توصیه‌ی خرید نیست.</i>')
    ok = True
    for c in chats:
        with open(png, 'rb') as f:
            ok &= send(token, c, 'sendPhoto', data={'chat_id': c, 'caption': cap, 'parse_mode': 'HTML'}, files={'photo': f})
        if changed:
            msg = (f'🔔 <b>هشدار: رتبه‌ی اول عوض شد</b>\n\nبازدهی ۳ ماهه‌ی <b>{ASSETS[leader][1]}</b> '
                   f'({now[leader]:+.1f}٪) از <b>{ASSETS[prev][1]}</b> ({now.get(prev, float("nan")):+.1f}٪) بالاتر رفت.\n'
                   f'یعنی در ۳ ماه گذشته الان {ASSETS[leader][1]} جلوتر از بقیه است.\n\n'
                   f'<i>این هشدار تغییر رتبه است، نه توصیه‌ی خرید. قبل از تصمیم، ریسک و نظر تحلیلگران را هم ببین.</i>')
            ok &= send(token, c, 'sendMessage', data={'chat_id': c, 'text': msg, 'parse_mode': 'HTML'})
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
