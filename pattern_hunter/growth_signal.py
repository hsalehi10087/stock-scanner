"""«احتمال رشد تکنیکال و بنیادی» — دو صافی پشت سر هم روی همه‌ی سهام ۱۱ بازار، هر روز.

صافی ۱ (تکنیکال: نمودار و حجم):
  الف) الگوی آماری قبل از رشد (مدل الگویاب، رتبه‌ی صدکی در همان بازار)
  ب) الگوهای کلاسیک:
     • شکست با حجم: بسته‌شدن بالای بالاترین قیمت ۵۰ روز قبل، با حجم دست‌کم ۱٫۵ برابر میانگین ۵۰ روزه
     • روند صعودی منظم: قیمت > میانگین ۵۰ > ۱۵۰ > ۲۰۰ روزه، میانگین ۲۰۰ رو به بالا، ≥۳۰٪ بالای کف و ≤۲۵٪ زیر سقف ۵۲ هفته
     • فشردگی نزدیک سقف: نوسان ۲۰ روزه کمتر از ۶۰٪ نوسان ۶۰ روزه، حجم رو به کاهش، تا ۱۰٪ زیر سقف ۵۲ هفته
     • برگشت به میانگین ۵۰ در روند: روند منظم برقرار، قیمت تا ۳٪ از میانگین ۵۰ روزه، حجم ۵ روز اخیر کم
  قبولی: دست‌کم ۲ الگوی کلاسیک، یا ۱ الگوی کلاسیک + رتبه‌ی الگوی آماری در ۲۰٪ بالای بازار
صافی ۲ (بنیادی): دست‌کم یکی از صورت مالی سالم، کن‌اسلیم، وارن بافت (pattern_hunter/fundamentals) یا امتیاز کیفیت رشد ⭐۴ و ⭐۵.
فقط سهم‌هایی که از هر دو بگذرند فرستاده و در تاریخچه ثبت می‌شوند؛ رشد یا نزول هر سیگنال تا امروز پیگیری می‌شود.
"""
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fundamentals as FU  # noqa: E402
import chart_patterns as CP  # noqa: E402
from common import OUT as PH_OUT  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'market_intel'))
import quality as Q  # noqa: E402

OUT = os.path.join(ROOT, 'data', 'growth_signal')
HIST = os.path.join(OUT, 'history.csv')
POOL = 30        # چند نامزد تکنیکال برتر به صافی بنیادی می‌روند
MAX_SEND = 8     # حداکثر سیگنال در هر بازار در روز
COOLDOWN = 20    # سهمی که در ۲۰ روز اخیر سیگنال شده، دوباره سیگنال تازه حساب نمی‌شود
SETUP_FA = {'longpat': 'الگوی نموداری بلندمدت', 'breakout': 'شکست با حجم', 'trend': 'روند صعودی منظم', 'vcp': 'فشردگی نزدیک سقف', 'pullback': 'برگشت به میانگین ۵۰'}
COLS = ['date', 'market', 'ticker', 'name', 'price', 'index_price', 'setups', 'fundamentals', 'quality', 'tech_rank',
        'chart', 'chart_score']


def history_tickers():
    if not os.path.exists(HIST):
        return {}
    h = pd.read_csv(HIST)
    return {m: set(g.ticker) for m, g in h.groupby('market')}


def setups(c, v):
    """الگوهای کلاسیک روی سری قیمت و حجم یک سهم (فقط داده تا امروز)."""
    if len(c) < 260:
        return []
    r = c.pct_change()
    s50, s150, s200 = c.rolling(50).mean(), c.rolling(150).mean(), c.rolling(200).mean()
    hi52, lo52 = c.rolling(252).max().iloc[-1], c.rolling(252).min().iloc[-1]
    p = c.iloc[-1]
    v50 = v.rolling(50).mean().iloc[-2]
    out = []
    trend = (p > s50.iloc[-1] > s150.iloc[-1] > s200.iloc[-1] and s200.iloc[-1] > s200.iloc[-22]
             and p >= 1.3 * lo52 and p >= 0.75 * hi52)
    if p > c.iloc[-51:-1].max() and v50 > 0 and v.iloc[-1] >= 1.5 * v50:
        out.append('breakout')
    if trend:
        out.append('trend')
    sd20, sd60 = r.iloc[-20:].std(), r.iloc[-60:].std()
    if sd60 > 0 and sd20 < 0.6 * sd60 and p >= 0.90 * hi52 and v.iloc[-20:].mean() < v.iloc[-50:].mean():
        out.append('vcp')
    if trend and abs(p / s50.iloc[-1] - 1) <= 0.03 and v50 > 0 and v.iloc[-5:].mean() < 0.8 * v50:
        out.append('pullback')
    return out


class Collector:
    def __init__(self):
        self.today = str(dt.date.today())
        self.hist = pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame(columns=COLS)
        for col in COLS:
            if col not in self.hist:
                self.hist[col] = None
        self.hist = self.hist[COLS]
        self.hist = self.hist[self.hist.date != self.today]   # اجرای دوباره در همان روز جایگزین می‌شود
        self.markets, self.track = {}, {}

    def process(self, m, C, V, idx, X, names, en_name):
        """X: ویژگی‌ها و احتمال مدل (ستون p) برای سهم‌های امروز این بازار."""
        rank = X['p'].rank(pct=True)
        tech, charts = [], {}
        for t in X.index:
            c = C[t].dropna()
            st = setups(c, V[t].reindex(c.index).fillna(0))
            cp = CP.detect(c)                       # الگوهای نموداری بلندمدت (scipy.find_peaks)
            if cp['score'] <= -1:                   # الگوی نزولی فعال ← کنار گذاشته می‌شود
                continue
            if cp['score'] >= 1.5:
                st = st + ['longpat']
            charts[t] = cp
            ok = len(st) >= 2 or (len(st) >= 1 and rank[t] >= 0.80)
            if ok:
                tech.append((t, st, float(rank[t])))
        tech.sort(key=lambda x: (-len(x[1]), -x[2]))
        recent = set(self.hist[(self.hist.market == m) &
                               (self.hist.date >= str(dt.date.today() - dt.timedelta(days=COOLDOWN)))].ticker)
        mkt_up = bool(idx.dropna().iloc[-1] > idx.dropna().rolling(200).mean().iloc[-1])
        sent, checked = [], 0
        for t, st, rk in tech[:POOL]:
            if len(sent) >= MAX_SEND:
                break
            if t in recent:
                continue
            checked += 1
            r = X.loc[t]
            try:
                fu = FU.check(t, {'from_hi': float(r.from_hi), 'rs6m': float(r.rs6m), 'volu_ratio': float(r.volu_ratio)}, mkt_up)
            except Exception:
                fu = {'passed': []}
            try:
                qs = Q.score(t, m)
            except Exception:
                qs = None
            passed = list(fu.get('passed') or [])
            if qs and qs['score'] >= 4:
                passed.append('کیفیت رشد')
            if not passed:
                continue
            nm = names.get(t, '')
            if m in ('cn', 'jp', 'tw', 'kr', 'hk') or not nm:
                nm = en_name(t) or ''
            price = float(C[t].dropna().iloc[-1])
            sent.append({'ticker': t, 'name': nm, 'price': round(price, 3), 'setups': st, 'tech_rank': round(rk, 3),
                         'fundamentals': passed, 'quality': Q.label(qs) if qs else '',
                         'chart': CP.label(charts[t]), 'chart_score': charts[t]['score']})
            self.hist.loc[len(self.hist)] = [self.today, m, t, nm, round(price, 4), round(float(idx.dropna().iloc[-1]), 4),
                                             '|'.join(st), '|'.join(passed), qs['score'] if qs else None, round(rk, 3),
                                             CP.label(charts[t]), charts[t]['score']]
        self.markets[m] = {'data_date': str(C.index[-1].date()), 'scored': int(len(X)), 'technical': len(tech),
                           'checked': checked, 'signals': sent}
        # پیگیری: همه‌ی سیگنال‌های قبلی این بازار
        items = []
        first = self.hist[self.hist.market == m].sort_values('date').drop_duplicates('ticker', keep='first')
        ix_now = float(idx.dropna().iloc[-1])
        for _, h in first.iterrows():
            if h.ticker not in C or h.date == self.today:
                continue
            c = C[h.ticker].dropna()
            since = c[c.index >= pd.Timestamp(h.date)]
            if since.empty or not h.price:
                continue
            cur = float(c.iloc[-1])
            items.append({'date': h.date, 'ticker': h.ticker, 'name': h['name'] if isinstance(h['name'], str) else '',
                          'ret_pct': round((cur / h.price - 1) * 100, 1),
                          'max_pct': round((float(since.max()) / h.price - 1) * 100, 1),
                          'min_pct': round((float(since.min()) / h.price - 1) * 100, 1),
                          'index_pct': round((ix_now / h.index_price - 1) * 100, 1) if h.index_price else None})
        self.track[m] = items

    def finish(self):
        os.makedirs(OUT, exist_ok=True)
        self.hist.to_csv(HIST, index=False)
        Q.save()
        json.dump({'date': self.today, 'markets': self.markets}, open(os.path.join(OUT, 'today.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        json.dump({'date': self.today, 'markets': self.track}, open(os.path.join(OUT, 'track.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
