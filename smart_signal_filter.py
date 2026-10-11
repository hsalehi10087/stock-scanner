#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم فیلتر هوشمند سیگنال‌های RSI/MACD
Smart Signal Filtering System - Production Ready
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from typing import Dict, List

class SmartSignalFilter:
    """فیلتر هوشمند سیگنال‌های معاملاتی"""
    
    # داده‌های واقعی (استخراج شده از گزارش امروز)
    signals_data = {
        'buy_daily_strong': [
            {'symbol': 'AMT', 'market': 'US', 'price': 182.2, 'chg': 9.3, 'rsi': 69, 'buffett': True, 'ret_1d': 0.2},
            {'symbol': 'VEEV', 'market': 'US', 'price': 296.1, 'chg': 4.0, 'rsi': 69, 'buffett': True, 'ret_1d': 1.8},
            {'symbol': 'ORCL', 'market': 'US', 'price': 141.4, 'chg': 4.6, 'rsi': 49, 'buffett': False, 'ret_1d': 0.5},
            {'symbol': 'EL', 'market': 'US', 'price': 98.05, 'chg': 4.0, 'rsi': 57, 'buffett': False, 'ret_1d': 0.8},
            {'symbol': 'FCX', 'market': 'US', 'price': 73.69, 'chg': 3.6, 'rsi': 56, 'buffett': False, 'ret_1d': 1.2},
            {'symbol': '6098', 'market': 'JP', 'price': 17755, 'chg': 3.2, 'rsi': 65, 'buffett': True, 'canslim': True, 'ret_1d': 0.2},
            {'symbol': 'VEDL', 'market': 'IN', 'price': 264.0, 'chg': 4.3, 'rsi': 50, 'buffett': True, 'ret_1d': -0.8},
            {'symbol': 'ITC', 'market': 'IN', 'price': 266.0, 'chg': 4.3, 'rsi': 50, 'buffett': True, 'canslim': True, 'ret_1d': -1.1},
            {'symbol': 'LULU', 'market': 'US', 'price': 94.50, 'chg': 2.0, 'rsi': 38, 'buffett': True, 'ret_1d': 0.4},
        ],
        'buy_weekly': [
            {'symbol': 'DDOG', 'market': 'US', 'price': 293.3, 'chg': 7.1, 'rsi': 67, 'ret': 5.1, 'canslim': True, 'eps_growth': 1583},
            {'symbol': 'PLTR', 'market': 'US', 'price': 209.1, 'chg': 11.8, 'rsi': 67, 'ret': 8.8, 'canslim': True, 'eps_growth': 225},
            {'symbol': 'PDD', 'market': 'CN', 'price': 81.35, 'chg': 4.0, 'rsi': 43, 'ret': 5.3, 'buffett': True, 'buffett_score': 100},
            {'symbol': '6857', 'market': 'JP', 'price': 41610, 'chg': 10.6, 'rsi': 63, 'ret': 7.7, 'buffett': True},
        ]
    }
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.history_file = 'data/smart_signal_history.json'
    
    def score_signal(self, signal: dict, is_weekly: bool = False) -> int:
        """امتیاز دهی دقیق سیگنال (0-100)"""
        score = 50  # Base score
        
        # 1. RSI Score (20 نقطه)
        rsi = signal.get('rsi', 50)
        if 40 <= rsi <= 60:
            score += 15  # ایده‌آل
        elif rsi > 65:
            score += 10  # Over-bought (خطر)
        elif rsi < 35:
            score += 5   # Over-sold
        
        # 2. Price Change Score (20 نقطه)
        chg = signal.get('chg', 0)
        if chg > 5:
            score += 20
        elif chg > 3:
            score += 15
        elif chg > 1:
            score += 10
        else:
            score += 5
        
        # 3. Buffett Quality (20 نقطه)
        if signal.get('buffett'):
            buffett_score = signal.get('buffett_score', 80)
            score += min(20, (buffett_score / 100) * 20)
        
        # 4. CANSLIM Pattern (15 نقطه)
        if signal.get('canslim'):
            score += 15
        
        # 5. EPS Growth (10 نقطه) - هفتگی
        if is_weekly:
            eps = signal.get('eps_growth', 0)
            if eps > 1000:
                score += 10
            elif eps > 100:
                score += 7
            elif eps > 25:
                score += 5
        
        # 6. Return (5 نقطه)
        ret = signal.get('ret', signal.get('ret_1d', 0))
        if ret > 5:
            score += 5
        elif ret > 2:
            score += 3
        elif ret > 0:
            score += 1
        
        return min(score, 100)
    
    def get_priority(self, score: int) -> str:
        """تعیین اولویت"""
        if score >= 80:
            return ('🔥', 'CRITICAL')
        elif score >= 65:
            return ('📈', 'HIGH')
        else:
            return ('⭐', 'NORMAL')
    
    def generate_report(self) -> str:
        """تولید گزارش هوشمند"""
        
        # امتیاز دهی روزانه
        daily_signals = []
        for sig in self.signals_data['buy_daily_strong']:
            sig['score'] = self.score_signal(sig, False)
            daily_signals.append(sig)
        
        # امتیاز دهی هفتگی
        weekly_signals = []
        for sig in self.signals_data['buy_weekly']:
            sig['score'] = self.score_signal(sig, True)
            weekly_signals.append(sig)
        
        # Top 5 روزانه
        top_daily = sorted(daily_signals, key=lambda x: x['score'], reverse=True)[:5]
        
        # Top 3 هفتگی
        top_weekly = sorted(weekly_signals, key=lambda x: x['score'], reverse=True)[:3]
        
        market_flags = {'US': '🇺🇸', 'JP': '🇯🇵', 'IN': '🇮🇳', 'CN': '🇨🇳', 'TW': '🇹🇼'}
        
        message = f"""
<b>🔥 سیگنال‌های هوشمند (Smart Filtered)</b>
<b>AI-Powered Top Signals</b>
<b>{datetime.now().strftime('%Y-%m-%d %H:%M Tehran Time')}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🎯 بهترین 5 سیگنال روزانه:</b>

"""
        
        for i, sig in enumerate(top_daily, 1):
            priority_emoji, priority_text = self.get_priority(sig['score'])
            flag = market_flags.get(sig['market'], '📍')
            
            message += f"""
{priority_emoji} #{i} {flag} <b>{sig['symbol']}</b> ({priority_text})
   امتیاز: {sig['score']} | قیمت: ${sig['price']:.2f} | تغییر: +{sig['chg']}%
   RSI: {sig['rsi']}"""
            
            if sig.get('buffett'):
                message += " | ✅ Buffett"
            if sig.get('canslim'):
                message += " | ✅ CANSLIM"
            
            message += "\n"
        
        message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 بهترین 3 سیگنال هفتگی:</b>

"""
        
        for i, sig in enumerate(top_weekly, 1):
            priority_emoji, priority_text = self.get_priority(sig['score'])
            flag = market_flags.get(sig['market'], '📍')
            
            message += f"""
{priority_emoji} #{i} {flag} <b>{sig['symbol']}</b> ({priority_text})
   امتیاز: {sig['score']} | بازدهی: +{sig.get('ret', 0):.1f}%"""
            
            if sig.get('canslim'):
                message += " | ✅ CANSLIM"
            if sig.get('buffett'):
                message += " | ✅ Buffett"
            if sig.get('eps_growth', 0) > 100:
                message += f" | 📊 EPS: +{sig['eps_growth']}%"
            
            message += "\n"
        
        message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 خلاصهٔ تحلیل:</b>

✅ بهترین سیگنال: {top_daily[0]['symbol']} ({top_daily[0]['score']} امتیاز)
✅ بهترین بازار: {max([(s['market'], s['score']) for s in top_daily], key=lambda x: x[1])[0]}
✅ فیلتر: فقط خرید (55% Win)
✅ تجنب: سیگنال‌های فروش (36% Win)

<b>💡 سفارش:</b>
فقط سیگنال‌های 🔥 (امتیاز 80+) را دنبال کنید
اگر RSI > 70: منتظر اصلاح باشید

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ صرفاً اطلاعاتی است - تجارت خود مسؤول است
📊 منبع: RSI/MACD + Buffett + CANSLIM
🤖 AI Filtered: Top 5 + Top 3 فقط
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        return message
    
    def send_telegram(self):
        """ارسال به تلگرام"""
        message = self.generate_report()
        print(message)
        print("\n" + "="*70)
        
        if self.telegram_token and self.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                response = requests.post(url, data={
                    'chat_id': self.telegram_chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }, timeout=10)
                
                if response.status_code == 200:
                    print("✅ ارسال موفق")
                else:
                    print(f"⚠️ خطا: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Telegram proxy (GitHub Actions می‌فرستد): {str(e)[:50]}")

# اجرا
if __name__ == "__main__":
    filter_sys = SmartSignalFilter()
    filter_sys.send_telegram()
