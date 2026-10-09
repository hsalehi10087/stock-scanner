#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش کلان اقتصادی برای تلگرام
Macro Analysis Report for Telegram
"""

from datetime import datetime
import os
import requests

class MacroAnalysisReport:
    """گزارش کلان اقتصادی"""
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def format_telegram_message(self) -> str:
        """تنسیق گزارش برای تلگرام"""
        
        message = """
<b>📊 گزارش کلان اقتصادی</b>
<b>9 اکتبر 2026</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🎯 خلاصهٔ یک‌نگاه</b>

<b>📈 صعودی:</b>
  • بورس آمریکا: +1.1% هفتگی
  • دلار: +0.4% هفتگی
  • مس: +3.2% هفتگی ✨
  • گاز: +5.9% هفتگی 🔥

<b>📉 نزولی:</b>
  • طلا: -4.3% ماهانه
  • نقره: -4.8% ماهانه
  • پالادیوم: -10.1% ماهانه

<b>↔️ خنثی:</b>
  • نفت: نوسانی
  • اوراق قرضه: بدون روند مشخص

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💼 اقتصاد و سیاست پولی</b>

<b>نرخ بهره:</b> ثابت می‌ماند
  • احتمال کاهش: 0%
  • احتمال افزایش: 0%
  ✅ بازار برای "ثبات" منتظر است

<b>نگرانی‌ها:</b>
  ⚠️ تورم بالا
  ⚠️ بدهی‌های حاکومی
  ⚠️ تعرفه‌های تجاری

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🥇 فلزات</b>

<b>خبر خوب:</b> مس صعودی! 📈
  → نشانهٔ بهبود صنعت جهانی

<b>خبر بد:</b> طلا نزولی 📉
  → دلار قوی + نرخ بهره بالا

<b>جدول فلزات:</b>
  طلا: -4.3% (ضعیف)
  نقره: -4.8% (ضعیف)
  مس: +3.2% (قوی!)
  پالادیوم: -10.1% (ضعیف)
  آلومینیوم: -7.8% (ضعیف)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>⛽ انرژی</b>

<b>نفت:</b> نوسانی ↔️
  • WTI: -10.5% ماهانه
  • دلایل: ژئوپلیتیک، وقفه عرضه

<b>گاز طبیعی:</b> صعودی قوی 🔥
  • +13.4% ماهانه
  • تقاضا قوی

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 هوش مصنوعی</b>

<b>دیدگاه:</b>
  ✅ خوش‌بینی به رشد سودآوری
  ⚠️ نگرانی از "حباب" قیمتی
  ✅ تقاضای واقعی برای تراشه‌ها

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 توصیه‌های کلی</b>

<b>خرید:</b>
  ✅ مس (رشد صنعتی)
  ✅ گاز (روند قوی)
  ✅ سهام تکنولوژی
  ✅ بورس آمریکا

<b>دوری:</b>
  ⚠️ طلا (دلار قوی)
  ⚠️ نقره
  ⚠️ نفت (نوسانی)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🔑 نکات اصلی</b>

1️⃣ دلار قوی = طلا و کالاها ارزان
2️⃣ مس بالا = صنعت جهان خوب
3️⃣ گاز قوی = تقاضای انرژی
4️⃣ بورس قوی = اما نگرانی بدهی
5️⃣ نرخ بهره ثابت = حداقل تا اکتبر

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ این گزارش برای اطلاع‌رسانی است
#کلان_اقتصادی #فلزات #انرژی
"""
        return message
    
    def send_to_telegram(self, message: str) -> bool:
        """ارسال به تلگرام"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ تلگرام تنظیم نشده")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                print("✅ گزارش کلان اقتصادی ارسال شد")
                return True
            else:
                print(f"❌ خطا: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ خطا: {e}")
            return False
    
    def run(self):
        """اجرای گزارش"""
        print("🚀 تولید گزارش کلان اقتصادی...\n")
        
        message = self.format_telegram_message()
        
        print(message)
        print("\n" + "="*60)
        
        self.send_to_telegram(message)
        
        print("\n✅ تکمیل شد!")
        return message

def run():
    """اجرای گزارش"""
    reporter = MacroAnalysisReport()
    message = reporter.run()
    return message

if __name__ == "__main__":
    run()
