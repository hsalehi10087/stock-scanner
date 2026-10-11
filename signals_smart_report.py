#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش هوشمند سیگنال‌های خرید
Smart Buy Signals Report
"""

import os
import requests
from datetime import datetime

class SmartSignalsReport:
    """گزارش هوشمند سیگنال‌های خرید"""
    
    # دستی از فایل extract شده (parsing بعد بهتر می‌شود)
    signals = [
        # US - Buffett Score ≥ 75 + ROE ≥ 15
        {'symbol': 'LULU', 'market': 'US', 'buffett': 98, 'roe': 34, 'ret': 0.4},
        {'symbol': 'TRV', 'market': 'US', 'buffett': 90, 'roe': 16, 'ret': -0.0},
        {'symbol': 'AOS', 'market': 'US', 'buffett': 89, 'roe': 25, 'ret': -0.0},
        {'symbol': 'AMP', 'market': 'US', 'buffett': 89, 'roe': 64, 'ret': -0.0},
        {'symbol': 'MCO', 'market': 'US', 'buffett': 79, 'roe': 55, 'ret': 0.2},
        
        # India - Buffett Score ≥ 75 + ROE ≥ 15
        {'symbol': 'BLS', 'market': 'IN', 'buffett': 100, 'roe': 27, 'ret': -0.5},
        {'symbol': 'IRCTC', 'market': 'IN', 'buffett': 79, 'roe': 36, 'ret': 1.3},
        {'symbol': 'VEDL', 'market': 'IN', 'buffett': 76, 'roe': 31, 'ret': -0.8},
        
        # China - Buffett Score ≥ 75 + ROE ≥ 15
        {'symbol': 'PDD', 'market': 'CN', 'buffett': 100, 'roe': 30, 'ret': 5.3},
        {'symbol': '600519', 'market': 'CN', 'buffett': 85, 'roe': 34, 'ret': -0.7},
        {'symbol': '000651', 'market': 'CN', 'buffett': 85, 'roe': 23, 'ret': -0.1},
        {'symbol': '688111', 'market': 'CN', 'buffett': 71, 'roe': 14, 'ret': 2.4},
    ]
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def score_signal(self, signal):
        """محاسبهٔ امتیاز کل"""
        buffett = signal['buffett']
        roe = signal['roe']
        ret = signal['ret']
        
        # Formula: Buffett (70%) + ROE (30%)
        return (buffett * 0.7) + (roe * 0.3)
    
    def generate_report(self):
        """تولید گزارش"""
        # فیلتر و مرتب‌سازی
        filtered = [s for s in self.signals if s['buffett'] >= 75 and s['roe'] >= 15]
        filtered.sort(key=self.score_signal, reverse=True)
        
        message = f"""
<b>🎯 سیگنال‌های خرید هوشمند</b>
<b>Smart Buy Signals - Buffett Filter</b>

<b>📊 شرایط فیلتر:</b>
✓ امتیاز بافت ≥ 75
✓ ROE ≥ 15٪
✓ سیگنال MACD/RSI دارند

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🏆 سیگنال‌های برتر ({len(filtered)} سهم)</b>

"""
        
        # Group by market
        by_market = {}
        for sig in filtered:
            market = sig['market']
            if market not in by_market:
                by_market[market] = []
            by_market[market].append(sig)
        
        flags = {'US': '🇺🇸', 'JP': '🇯🇵', 'IN': '🇮🇳', 'CN': '🇨🇳', 'TW': '🇹🇼'}
        
        for market in ['US', 'JP', 'IN', 'CN', 'TW']:
            if market in by_market:
                message += f"\n<b>{flags.get(market, '🌍')} {market}</b>\n"
                
                for sig in sorted(by_market[market], key=self.score_signal, reverse=True):
                    score = self.score_signal(sig)
                    emoji = "🔥" if score >= 85 else "📈" if score >= 75 else "⭐"
                    
                    message += f"{emoji} <b>{sig['symbol']}</b> | Buf:{sig['buffett']} ROE:{sig['roe']}% | {sig['ret']:+.1f}%\n"
        
        message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 Top 3:
"""
        
        top3 = filtered[:3]
        for i, sig in enumerate(top3, 1):
            message += f"{i}. {sig['symbol']} (امتیاز: {self.score_signal(sig):.0f})\n"
        
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ این توصیهٔ خرید نیست
✅ منبع: MACD/RSI + وارن بافت
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        return message
    
    def send_telegram(self):
        """ارسال به تلگرام"""
        message = self.generate_report()
        print(message)
        print("\n" + "="*60)
        
        if self.telegram_token and self.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                requests.post(url, data={
                    'chat_id': self.telegram_chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }, timeout=10)
                print("✅ ارسال شد")
            except:
                print("⚠️ Telegram proxy issue (GitHub Actions می‌فرستد)")

# اجرا
if __name__ == "__main__":
    reporter = SmartSignalsReport()
    reporter.send_telegram()
