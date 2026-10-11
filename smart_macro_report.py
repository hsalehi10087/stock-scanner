#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم هوشمند گزارش کلان‌اقتصادی
Smart Macro Economic Report System
"""

import os
import requests
from datetime import datetime
from typing import Dict, List

class SmartMacroReport:
    """گزارش هوشمند کلان‌اقتصاد"""
    
    # دستی extract شده
    macro_data = {
        'stocks': {'S&P 500': {'+1W%': 1.2, '+1M%': 2.9, 'RSI': 60, 'trend': '⬆️'}},
        'yields': {'US 10Y': {'+1W%': -0.6, '+1M%': 6.1, 'RSI': 66, 'trend': '↔️'}},
        'dollar': {'DXY': {'+1W%': 0.3, '+1M%': 3.1, 'RSI': 69, 'trend': '⬆️'}},
        'fear': {'VIX': {'+1W%': -3.1, '+1M%': -16.8, 'RSI': 45, 'trend': '⬇️'}},
        'metals': {
            'Gold': {'+1W%': 1.3, '+1M%': -4.3, 'trend': '⬇️'},
            'Silver': {'+1W%': 1.8, '+1M%': -5.0, 'trend': '⬇️'},
            'Copper': {'+1W%': 3.1, '+1M%': 3.5, 'trend': '⬆️'},
        },
        'energy': {
            'WTI': {'+1W%': 0.8, '+1M%': -10.4, 'trend': '↔️'},
            'Natural Gas': {'+1W%': 6.1, '+1M%': 13.6, 'trend': '↔️'},
        }
    }
    
    # خبرها
    sentiment = {
        'Fed/Rates': {'Up': 13, 'Down': 15, 'Neutral': 73},
        'US Economy': {'Up': 5, 'Down': 11, 'Neutral': 84},
        'Oil': {'Up': 23, 'Down': 9, 'Neutral': 67},
        'Gold/Metals': {'Up': 22, 'Down': 7, 'Neutral': 70},
        'Tech/AI': {'Up': 24, 'Down': 11, 'Neutral': 65},
    }
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def get_macro_alerts(self) -> List[str]:
        """دریافت هشدارهای اقتصادی"""
        alerts = []
        
        # Alert 1: دلار قوی + طلا کاهشی
        alerts.append("🔴 ALERT: دلار قوی (RSI 69) + طلا نزولی (-4.3%) = فشار بر طلا")
        
        # Alert 2: VIX پایین
        alerts.append("🟢 POSITIVE: VIX پایین (-16.8%) = آرام‌تری بازار")
        
        # Alert 3: مس صعودی
        alerts.append("📈 SIGNAL: مس صعودی (+3.5%) = رشد صنعتی")
        
        # Alert 4: گاز طبیعی
        alerts.append("⚡ WATCH: گاز طبیعی (+13.6%) = تقاضا بالا")
        
        # Alert 5: فدرال رزرو
        alerts.append("❄️ FROZEN: کاهش نرخ 0٪ احتمال = نرخ‌های بالا ادامه")
        
        return alerts
    
    def generate_report(self) -> str:
        """تولید گزارش هوشمند"""
        alerts = self.get_macro_alerts()
        
        message = f"""
<b>🌍 گزارش کلان‌اقتصادی هوشمند</b>
<b>Smart Macro Report - AI Filtered</b>

<b>🎯 الرت‌های فوری:</b>
"""
        
        for alert in alerts[:3]:
            message += f"{alert}\n"
        
        message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 وضعیت دارایی‌ها:</b>

<b>📈 بورس</b>
S&P 500: {self.macro_data['stocks']['S&P 500']['trend']} +1.2% هفته‌ای
RSI: {self.macro_data['stocks']['S&P 500']['RSI']} (متوازن)

<b>💵 دلار</b>
DXY: {self.macro_data['dollar']['DXY']['trend']} +3.1% ماهانه
قدرت: قوی (RSI 69)

<b>🥇 فلزات</b>
Gold: {self.macro_data['metals']['Gold']['trend']} -4.3% ماهانه (تحت فشار)
Copper: {self.macro_data['metals']['Copper']['trend']} +3.5% ماهانه (صعودی)

<b>⚡ انرژی</b>
Natural Gas: {self.macro_data['energy']['Natural Gas']['trend']} +13.6% ماهانه (HOT)
WTI: {self.macro_data['energy']['WTI']['trend']} -10.4% ماهانه (عدم قطعیت)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📰 نظر کارشناسان:</b>

🔴 <b>نگرانی‌ها:</b>
• اعتماد مصرف‌کننده کاهش
• تورم دوباره فعال
• رشد ضعیف اشتغال

🟢 <b>فرصت‌ها:</b>
• تقاضای هوش مصنوعی قوی
• نفت صعودی (ژئوپلیتیک)
• طلا حمایتی در 4,100 دلار

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🎲 پیش‌بینی‌ها (Polymarket):</b>
• کاهش نرخ فدرال: <b>0%</b> احتمال ❄️
• افزایش نرخ: <b>ممکن</b> در پایان سال
• دلار: <b>ادامه قوت</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ تحلیل نیست، اطلاعاتی است
✅ منبع: Macro + Sentiment Analysis
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
                print("⚠️ Telegram proxy (GitHub Actions می‌فرستد)")

# اجرا
if __name__ == "__main__":
    reporter = SmartMacroReport()
    reporter.send_telegram()
