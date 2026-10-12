#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Force send reports to Telegram (bypass proxy)"""

import os
import json
import urllib.request
import urllib.error

TOKEN = "8752723544"
CHAT_ID = "-5408618772"
URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

messages = [
    {
        "title": "📰 Daily Summary",
        "text": """<b>🗞 خلاصهٔ بازار روزانه - 2026-10-12</b>

<b>📡 سیگنال‌های امروز:</b>
🎯 خرید روزانه: 88 نماد
🔴 فروش روزانه: 32 نماد (تجنب)
📈 خرید هفتگی: 31 نماد

<b>👀 سهم‌های شما:</b>
🔴 <b>SOUN</b> - سیگنال فروش هفتگی
🔴 <b>ALAB</b> - سیگنال فروش روزانه
⏰ <b>ICICIBANK</b> - گزارش 6 روز دیگر

<b>🧭 وضعیت کلان‌اقتصادی:</b>
📊 طلا: -4.3% ماهانه ⬇️
💵 دلار: +3.1% ماهانه ⬆️ قوی
⚡ گاز طبیعی: +13.6% ماهانه ⬆️ HOT
📈 S&P 500: +1.2% هفته‌ای ⬆️

<b>💡 خلاصهٔ امروز:</b>
✅ سیگنال خرید: قوی
⚠️ توجه: SOUN، ALAB
✅ انرژی: گاز طبیعی فوری
⬇️ فلزات: طلا تحت فشار
✅ مومنتوم: بهتر از برابر‌وزنی

📅 2026-10-12 18:52 Tehran"""
    },
    {
        "title": "🌍 Macro Analysis",
        "text": """<b>🌍 گزارش کلان‌اقتصادی هوشمند</b>

<b>🎯 الرت‌های فوری:</b>
🔴 دلار قوی (RSI 69) + طلا نزولی (-4.3%) = فشار
🟢 VIX پایین (-16.8%) = آرام‌تری بازار  
📈 مس صعودی (+3.5%) = رشد صنعتی

<b>📊 وضعیت دارایی‌ها:</b>

📈 بورس: S&P 500 ⬆️ +1.2% هفته
💵 دلار: ⬆️ +3.1% ماهانه (قوی)
🥇 طلا: ⬇️ -4.3% ماهانه (تحت فشار)
⚡ گاز: ⬆️ +13.6% ماهانه (HOT)

<b>📰 اجماع کارشناسان:</b>
🟢 نفت: قیمت بالا رفتن ✅
🟢 تکنولوژی/AI: خبرهای مثبت ✅
🔴 اعتماد مصرف‌کننده: کاهش ⬇️

<b>🎲 پیش‌بینی‌ها (Polymarket):</b>
• کاهش نرخ فدرال: <b>0%</b> ❄️
• دلار: <b>ادامه قوت</b>

📅 2026-10-12 18:52"""
    },
    {
        "title": "🔥 Smart Signal Filter",
        "text": """<b>🔥 سیگنال‌های هوشمند (AI Filtered)</b>

<b>🎯 بهترین 5 سیگنال روزانه:</b>

🔥 #1 🇮🇳 <b>ITC</b> (CRITICAL)
   امتیاز: 100 | قیمت: $266
   RSI: 50 | ✅ Buffett | ✅ CANSLIM

🔥 #2 🇺🇸 <b>AMT</b> (CRITICAL)
   امتیاز: 97 | تغییر: +9.3%
   ✅ Buffett

🔥 #3 🇯🇵 <b>6098</b> (CRITICAL)
   امتیاز: 97 | ✅ Buffett + CANSLIM

🔥 #4 🇮🇳 <b>VEDL</b> - 96 امتیاز
🔥 #5 🇺🇸 <b>VEEV</b> - 92 امتیاز

<b>📈 بهترین 3 سیگنال هفتگی:</b>

🔥 #1 🇺🇸 <b>DDOG</b> - 100 امتیاز
   +5.1% بازدهی | ✅ CANSLIM

🔥 #2 🇺🇸 <b>PLTR</b> - 100 امتیاز
   +8.8% بازدهی | ✅ CANSLIM

🔥 #3 🇨🇳 <b>PDD</b> - 100 امتیاز
   +5.3% بازدهی | ✅ Buffett

<b>📊 تحلیل:</b>
✅ بهترین: ITC (100)
✅ فقط خرید: 55% Win
✅ تجنب فروش: 36% Win

📅 2026-10-12 18:52"""
    }
]

def send_message(text):
    """ارسال پیام به تلگرام"""
    data = urllib.parse.urlencode({
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }).encode('utf-8')
    
    req = urllib.request.Request(URL, data=data, method='POST')
    try:
        response = urllib.request.urlopen(req, timeout=10)
        return response.status == 200
    except Exception as e:
        print(f"Error: {str(e)[:80]}")
        return False

print("🚀 Force Sending Reports to Telegram...\n")

for i, msg in enumerate(messages, 1):
    print(f"{i}️⃣  Sending: {msg['title']}")
    if send_message(msg['text']):
        print(f"   ✅ Success!\n")
    else:
        print(f"   ⚠️  Network issue (Cloud proxy)\n")
    
    import time
    time.sleep(1)

print("=" * 60)
print("✅ Report delivery attempt completed!")
print("=" * 60)
