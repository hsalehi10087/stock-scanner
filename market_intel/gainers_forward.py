"""ثبت بازده آینده‌ی سیگنال‌های «رشد بیش از ۱۰٪» (فقط ثبت و آمار؛ چیزی به تلگرام نمی‌فرستد).

برای هر سیگنال در data/gainers/*.csv:
  - gap      : فاصله‌ی قیمت بازشدن روز بعد با بسته‌شدن روز سیگنال (هزینه‌ی «دنبال‌کردن جهش»)
  - o1/o5/o10: بازده از قیمت بازشدن روز T+1 (ورود واقع‌بینانه) تا بسته‌شدن روز T+1 / T+5 / T+10
  - c1/c5/c10: بازده از بسته‌شدن روز سیگنال (روش قبلی ردیاب) تا بسته‌شدن T+1 / T+5 / T+10
  - nth      : چندمین سیگنال همان سهم (۱ = اولین بار)
  - passes   : آیا سیگنال از فیلتر فعلی (قیمت، حجم، کیفیت ≥ ۱) رد می‌شد؟
خروجی: data/gainers_forward/forward.csv و summary.md (آمار جدا برای فیلترشده/فیلترنشده، به تفکیک تکرار و کیفیت).
"""
import glob
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST_DIR = os.path.join(ROOT, 'data', 'gainers')
OUT_DIR = os.path.join(ROOT, 'data', 'gainers_forward')
MIN_PRICE = 5.0
MIN_VOLUME = 100_000
HORIZONS = (1, 5, 10)


def load_signals(hist_dir=HIST_DIR):
    frames = []
    for f in sorted(glob.glob(os.path.join(hist_dir, '20*.csv'))):
        try:
            frames.append(pd.read_csv(f))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])
    df = df.drop_duplicates(['ticker', 'date']).sort_values(['ticker', 'date']).reset_index(drop=True)
    df['nth'] = df.groupby('ticker').cumcount() + 1
    qs = df['qs'] if 'qs' in df else pd.Series(0, index=df.index)
    df['passes'] = (df['price'] >= MIN_PRICE) & (df['volume'] >= MIN_VOLUME) & (qs.fillna(0) >= 1)
    return df


def fetch_bars(tickers, start, chunk=200):
    """{ticker: DataFrame(Open, Close) با ایندکس تاریخ} از Yahoo."""
    import yfinance as yf
    out = {}
    tl = sorted(tickers)
    for i in range(0, len(tl), chunk):
        part = tl[i:i + chunk]
        try:
            df = yf.download(part, start=str(start), interval='1d', group_by='ticker', threads=True,
                             progress=False, auto_adjust=False)
        except Exception as e:
            print(f'⚠️ gainers_forward دسته {i}: {e}', file=sys.stderr)
            continue
        for t in part:
            try:
                b = (df[t] if len(part) > 1 else df)[['Open', 'Close']].dropna()
                if len(b):
                    out[t] = b
            except Exception:
                continue
    return out


def compute(signals, bars):
    rows = []
    for r in signals.itertuples():
        b = bars.get(r.ticker)
        rec = {'ticker': r.ticker, 'date': r.date.date(), 'nth': r.nth, 'passes': bool(r.passes),
               'qs': getattr(r, 'qs', None), 'price': r.price, 'chg': r.chg}
        if b is not None:
            idx = b.index.searchsorted(r.date)
            if idx < len(b) and b.index[idx] == r.date and idx + 1 < len(b):
                c0 = float(b['Close'].iloc[idx])
                o1 = float(b['Open'].iloc[idx + 1])
                rec['gap'] = (o1 / c0 - 1) * 100
                for k in HORIZONS:
                    if idx + k < len(b):
                        ck = float(b['Close'].iloc[idx + k])
                        rec[f'o{k}'] = (ck / o1 - 1) * 100
                        rec[f'c{k}'] = (ck / c0 - 1) * 100
        rows.append(rec)
    return pd.DataFrame(rows)


def _stat(s):
    s = s.dropna()
    if s.empty:
        return None
    return len(s), s.median(), s.mean(), (s > 0).mean() * 100


def summarize(fw):
    def block(title, g):
        lines = [f'### {title}', '', '| گروه | تعداد | میانه | میانگین | مثبت٪ |', '|---|---|---|---|---|']
        for name, d in g:
            st = _stat(d)
            if st:
                lines.append(f'| {name} | {st[0]} | {st[1]:+.1f} | {st[2]:+.1f} | {st[3]:.0f} |')
        return lines + ['']

    out = [f'# آمار بازده سیگنال‌های رشد >۱۰٪ آمریکا (به‌روز: {pd.Timestamp.now().date()})', '',
           'o = بازده از بازشدن روز بعد (ورود واقع‌بینانه)، c = بازده از بسته‌شدن روز جهش (روش قبلی). همه به ٪.', '']
    for col in ('o1', 'o5', 'o10', 'c5'):
        if col not in fw or fw[col].dropna().empty:
            continue
        out.append(f'## {col}')
        out += block('به تفکیک فیلتر', [('فیلترشده (قیمت≥۵، حجم، کیفیت≥۱)', fw[fw.passes][col]),
                                       ('فیلترنشده/قدیمی', fw[~fw.passes][col])])
        p = fw[fw.passes]
        out += block('فیلترشده — به تفکیک چندمین سیگنال', [(f'سیگنال {n if n < 3 else "۳+"}', d[col])
                                                         for n, d in p.assign(n=p.nth.clip(upper=3)).groupby('n')])
        out += block('فیلترشده — به تفکیک کیفیت', [(f'کیفیت {int(q)}', d[col]) for q, d in p.groupby('qs')])
    if 'gap' in fw:
        out += ['## فاصله‌ی بازشدن روز بعد با بسته‌شدن روز جهش (٪)', '']
        out += block('همه', [('فیلترشده', fw[fw.passes].gap), ('فیلترنشده', fw[~fw.passes].gap)])
    return '\n'.join(out)


def update():
    sig = load_signals()
    if sig.empty:
        print('gainers_forward: سیگنالی نیست')
        return None
    bars = fetch_bars(sig['ticker'].unique(), sig['date'].min() - pd.Timedelta(days=7))
    fw = compute(sig, bars)
    os.makedirs(OUT_DIR, exist_ok=True)
    fw.to_csv(os.path.join(OUT_DIR, 'forward.csv'), index=False, encoding='utf-8')
    with open(os.path.join(OUT_DIR, 'summary.md'), 'w', encoding='utf-8') as f:
        f.write(summarize(fw))
    print(f'gainers_forward: {len(fw)} سیگنال، {fw["o5"].notna().sum() if "o5" in fw else 0} با بازده ۵روزه')
    return fw


if __name__ == '__main__':
    update()
