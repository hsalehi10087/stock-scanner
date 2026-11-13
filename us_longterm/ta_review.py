"""اجرای TradingAgents روی سیگنال‌های رشد آمریکا و ارسال نتیجه به تلگرام.
فقط دستی اجرا می‌شود. TELEGRAM_CHAT_ID=none یعنی فقط چاپ، بدون ارسال.
"""
import json, os, sys, datetime as dt
import requests

MAX_N = int(os.getenv('TA_MAX', '3'))
tick_in = os.getenv('TA_TICKERS', '').strip()
chat = os.getenv('TELEGRAM_CHAT_ID', '75439320').strip()
token = os.getenv('TELEGRAM_BOT_TOKEN', '')
dry = chat == 'none'

if tick_in:
    tickers = [t.strip().upper() for t in tick_in.replace(',', ' ').split() if t.strip()]
else:
    d = json.load(open('data/growth_signal/today.json', encoding='utf-8'))
    sig = d.get('markets', {}).get('us', {}).get('signals', [])
    sig = sorted(sig, key=lambda s: -(s.get('profit_streak') or 0))
    tickers = [s['ticker'] for s in sig]
tickers = tickers[:MAX_N]
if not tickers:
    print('no tickers'); sys.exit(0)

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
cfg = DEFAULT_CONFIG.copy()
date = dt.date.today().isoformat()

out = []
for t in tickers:
    try:
        ta = TradingAgentsGraph(debug=False, config=cfg)
        state, rating = ta.propagate(t, date)
        txt = str(state.get('final_trade_decision', ''))[:900]
        out.append(f"📌 {t}: {rating}\n{txt}")
    except Exception as e:
        out.append(f"📌 {t}: ❌ خطا ({type(e).__name__}: {str(e)[:150]})")
    print(out[-1][:300], flush=True)

msg = (f"🤖 بررسی TradingAgents ({date})\n"
       "روی سیگنال‌های رشد آمریکا؛ فقط نظر مدل است، توصیه‌ی مالی و تأییدشده نیست.\n\n"
       + "\n\n".join(out))
print('=== MESSAGE ===\n' + msg + '\n=== END ===')
if dry or not token:
    print('dry-run: not sent'); sys.exit(0)
for i in range(0, len(msg), 3800):
    r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage',
                      data={'chat_id': chat, 'text': msg[i:i+3800]}, timeout=30)
    print('telegram', r.status_code)
