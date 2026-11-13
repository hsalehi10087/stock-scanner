"""سنجش عملکرد تصمیم‌های TradingAgents نسبت به SPY.
بازده هر سهم از قیمت بسته‌ی روز تصمیم (یا اولین بسته‌ی بعد از آن) تا امروز؛ به تفکیک امتیاز.
TELEGRAM_CHAT_ID=none = فقط چاپ."""
import csv, os, sys, datetime as dt
import pandas as pd, yfinance as yf, requests

LOG = 'data/ta_review/history.csv'
if not os.path.exists(LOG):
    print('no history yet'); sys.exit(0)
rows = list(csv.DictReader(open(LOG, encoding='utf-8')))
if not rows: sys.exit(0)
tk = sorted({r['ticker'] for r in rows} | {'SPY'})
start = min(r['date'] for r in rows)
px = pd.concat([yf.download(t, start=start, auto_adjust=True, progress=False, threads=False)['Close'].squeeze().rename(t)
                for t in tk], axis=1).dropna(how='all')
assert 'SPY' in px and len(px) > 1, 'no price data'
res = []
for r in rows:
    t, d = r['ticker'], pd.Timestamp(r['date'])
    s = px[t].dropna() if t in px else None
    if s is None or s[s.index > d].empty: continue
    p0 = s[s.index > d].iloc[0]            # اولین بسته‌ی بعد از روز تصمیم
    d0 = s[s.index > d].index[0]
    b = px['SPY'].dropna(); b0 = b[b.index >= d0].iloc[0]
    ret = s.iloc[-1] / p0 - 1; bm = b.iloc[-1] / b0 - 1
    res.append({'ticker': t, 'rating': r['rating'], 'date': r['date'], 'days': (s.index[-1] - d0).days,
                'ret': ret * 100, 'alpha': (ret - bm) * 100})
if not res:
    print('not enough data'); sys.exit(0)
df = pd.DataFrame(res)
lines = [f"📊 عملکرد TradingAgents تا {px.index[-1].date()} (نسبت به SPY، از اولین بسته‌ی بعد از تصمیم)",
         f"تعداد تصمیم: {len(df)}"]
for g, x in df.groupby('rating'):
    lines.append(f"• {g}: {len(x)} مورد، میانگین بازده {x.ret.mean():+.1f}٪، اضافه‌بازده نسبت به SPY {x.alpha.mean():+.1f}٪")
buy = df[df.rating.isin(['Buy', 'Overweight'])]
if len(buy):
    lines.append(f"خرید/اضافه‌وزن در کل: اضافه‌بازده میانگین {buy.alpha.mean():+.1f}٪، موفق {int((buy.alpha>0).sum())} از {len(buy)}")
lines.append("⚠️ نمونه کوچک است؛ تا چند ده تصمیم و چند ماه نتیجه‌گیری نکن.")
df.to_csv('data/ta_review/track.csv', index=False)
msg = "\n".join(lines); print(msg)
chat = os.getenv('TELEGRAM_CHAT_ID', '75439320'); tok = os.getenv('TELEGRAM_BOT_TOKEN', '')
if chat != 'none' and tok:
    r = requests.post(f'https://api.telegram.org/bot{tok}/sendMessage', data={'chat_id': chat, 'text': msg}, timeout=30)
    print('telegram', r.status_code)
