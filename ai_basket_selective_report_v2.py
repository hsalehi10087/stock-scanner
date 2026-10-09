#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Basket Selective Report v2
گزارش سبد هوش مصنوعی - فقط سهام‌های با خبرهای مثبت زیاد

چه‌طور کار می‌کند:
- هر سهم را بر اساس نشانه‌های مثبت/منفی نمره‌گذاری می‌کند
- فقط سهام‌های "خوب" را در گزارش آورد
- سهام‌های با نقاط ضعیف را حذف کند
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Tuple

class AIBasketSelectiveReport:
    """تنها سهام‌های خوب را گزارش می‌کند"""
    
    # سبدِ اصلی - ۲۰ سهم
    AI_BASKET = [
        'PLTR', 'RXRX', 'APP', 'LITE', 'CRDO',
        'ALAB', 'OKLO', 'SERV', 'SOUN', 'APLD',
        'TEM', 'COHR', 'QBTS', 'CRWV', 'NBIS',
        'RGTI', 'IONQ', 'ARM', 'NVTS', 'IREN'
    ]
    
    # معیارهای انتخاب
    MIN_POSITIVE_SCORE = 3  # حداقل ۳ نشانهٔ مثبت
    MAX_NEGATIVE_SCORE = 1  # حداکثر ۱ نشانهٔ منفی
    
    # نمونهٔ داده - خبرهای ساختگی برای نمایش منطق
    SAMPLE_DATA = {
        'PLTR': {
            'pros': [
                '📈 بازده ۶ ماهه: +9.1%',
                '💰 حجم معاملات: 45.2M (نقدینگی عالی)',
                '🚀 رشد درآمد: 28%',
                '✅ عقد دفاعی جدید اعلام شد'
            ],
            'cons': []
        },
        'RXRX': {
            'pros': [
                '📈 بازده ۶ ماهه: +7.3%',
                '💎 P/E: 12.5 (نسبی کم)',
                '🚀 تجربهٔ بالینی موفق'
            ],
            'cons': ['⚠️ تمدید دارو منتظر']
        },
        'ARM': {
            'pros': [
                '📈 حجم معاملات: 62M (عالی)',
                '✅ نمو چیپ جدید معرفی شد'
            ],
            'cons': [
                '⚠️ فروش روسیه محدود',
                '❌ P/E: 45 (بالا)',
                '❌ منازعهٔ چینی'
            ]
        },
        'NVTS': {
            'pros': [
                '📈 تکنولوژی جدید'
            ],
            'cons': [
                '❌ سود منفی: -12%',
                '❌ بدهی بالا',
                '⚠️ رقابت شدید'
            ]
        },
        'LITE': {
            'pros': [
                '📈 بازده: +2.7%',
                '💰 حجم معاملات: 8M',
                '🚀 توسعهٔ تولید'
            ],
            'cons': []
        }
    }
    
    def __init__(self, use_sample=True):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.filtered_stocks = []
        self.use_sample = use_sample
    
    def get_stock_analysis(self, symbol: str) -> Tuple[List[str], List[str]]:
        """
        دریافت تجزیهٔ سهم
        (در نسخهٔ واقعی: یاهو، تویتر، سکک‌وری فایلرز، ...)
        """
        if self.use_sample and symbol in self.SAMPLE_DATA:
            data = self.SAMPLE_DATA[symbol]
            return data['pros'], data['cons']
        return [], []
    
    def score_stock(self, symbol: str) -> Tuple[int, int, List[str], List[str]]:
        """نمره‌دهی سهم"""
        pros, cons = self.get_stock_analysis(symbol)
        return len(pros), len(cons), pros, cons
    
    def filter_stocks(self) -> List[Dict]:
        """فیلتر کردن سهام‌ها"""
        print("🔍 در حال بررسی سهام‌ها...\n")
        
        selected = []
        
        for symbol in self.AI_BASKET:
            pos_score, neg_score, pros, cons = self.score_stock(symbol)
            
            print(f"📊 {symbol}: {pos_score} ✅ | {neg_score} ❌", end=" → ")
            
            # معیار انتخاب
            if pos_score >= self.MIN_POSITIVE_SCORE and neg_score <= self.MAX_NEGATIVE_SCORE:
                print("✅ نیست")
                selected.append({
                    'symbol': symbol,
                    'positive_score': pos_score,
                    'negative_score': neg_score,
                    'pros': pros,
                    'cons': cons
                })
            else:
                reasons = []
                if pos_score < self.MIN_POSITIVE_SCORE:
                    reasons.append(f"خبر کم ({pos_score}<{self.MIN_POSITIVE_SCORE})")
                if neg_score > self.MAX_NEGATIVE_SCORE:
                    reasons.append(f"نقطهٔ ضعیف ({neg_score}>{self.MAX_NEGATIVE_SCORE})")
                print(f"❌ {', '.join(reasons)}")
        
        self.filtered_stocks = selected
        return selected
    
    def format_telegram_message(self, stocks: List[Dict]) -> str:
        """تنسیق گزارش برای تلگرام"""
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        if not stocks:
            message = f"""
<b>🤖 سبد هوش مصنوعی - گزارش انتخابی</b>
{now} (تهران)

❌ <b>هیچ سهمی شرایط را کامل نکرد</b>

<i>معیارهای انتخاب:</i>
  ✅ حداقل ۳ خبر مثبت
  ✅ حداکثر ۱ نقطهٔ ضعیف

📌 این به معنای احتیاط سیستم است.
منتظر فرصت‌های بهتر...

📊 وضعیت سبد:
  کل: {len(self.AI_BASKET)} سهم
  انتخاب شده: ۰
  درصد: 0%
"""
        else:
            message = f"""
<b>🤖 سبد هوش مصنوعی - گزارش انتخابی</b>
{now} (تهران)
<i>فقط سهام با خبرهای مثبت زیاد</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            for stock in sorted(stocks, key=lambda x: x['positive_score'], reverse=True):
                symbol = stock['symbol']
                pos = stock['positive_score']
                
                message += f"\n<b>✅ {symbol}</b> ({pos} خبر مثبت)\n"
                
                for pro in stock['pros']:
                    message += f"  {pro}\n"
                
                if stock['cons']:
                    message += f"  <i>نکات: {', '.join([c.replace('⚠️ ', '').replace('❌ ', '') for c in stock['cons']])}</i>\n"
            
            message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📋 خلاصهٔ انتخاب:</b>
  کل: {len(self.AI_BASKET)} سهم
  انتخاب شده: {len(stocks)} سهم
  درصد: {len(stocks)*100//len(self.AI_BASKET)}%

<b>📌 معیارهای انتخاب:</b>
  ✅ حداقل ۳ خبر مثبت
  ✅ حداکثر ۱ نقطهٔ ضعیف
  
<b>📊 منطق فیلتر:</b>
  • اگر خبر مثبت کم ← حذف
  • اگر نقاط ضعیف زیاد ← حذف
  • اگر معیار برآورده شد ← شامل شود

⏰ گزارش: روزی یک‌بار (خودکار)
"""
        
        return message
    
    def print_report(self, stocks: List[Dict]):
        """چاپ گزارش در کنسول"""
        print("\n" + "="*60)
        print("🤖 گزارش سبد هوش مصنوعی - فقط سهام‌های خوب")
        print("="*60 + "\n")
        
        if stocks:
            print(f"✅ {len(stocks)} سهم انتخاب شد:\n")
            
            for stock in sorted(stocks, key=lambda x: x['positive_score'], reverse=True):
                print(f"  {stock['symbol']} ({stock['positive_score']} خبر مثبت)")
                for pro in stock['pros']:
                    print(f"    {pro}")
                if stock['cons']:
                    print(f"    نکات: {', '.join([c.replace('⚠️ ', '').replace('❌ ', '') for c in stock['cons']])}")
                print()
        else:
            print("❌ هیچ سهمی شرایط را کامل نکرد\n")
        
        print(f"📊 کل سهام: {len(self.AI_BASKET)}")
        print(f"✅ انتخاب شده: {len(stocks)}")
        print(f"📈 درصد: {len(stocks)*100//len(self.AI_BASKET)}%\n")
    
    def run(self):
        """اجرای گزارش"""
        print("🚀 شروع گزارش سبدِ انتخابی...\n")
        
        # فیلتر کردن
        selected = self.filter_stocks()
        
        print()
        
        # نمایش در کنسول
        self.print_report(selected)
        
        # تنسیق تلگرام
        message = self.format_telegram_message(selected)
        print(message)

def run():
    """اجرای گزارش"""
    reporter = AIBasketSelectiveReport(use_sample=True)
    reporter.run()

if __name__ == "__main__":
    run()
