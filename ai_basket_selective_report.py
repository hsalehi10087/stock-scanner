#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Basket Selective Report
گزارش سبد هوش مصنوعی - فقط سهام‌های با خبرهای مثبت زیاد
"""

import os
import json
from datetime import datetime
import requests
import yfinance as yf
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
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.filtered_stocks = []
    
    def score_stock(self, symbol: str) -> Tuple[int, int, List[str], List[str]]:
        """
        نمره‌دهی سهم بر اساس:
        - نوسان و بازده اخیر
        - اطلاعات بنیادی
        - نمودار فنی
        
        برمی‌گرداند: (positive_score, negative_score, pros, cons)
        """
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period='6mo')
            
            pros = []
            cons = []
            
            # ✅ نشانه‌های مثبت
            
            # 1. بازده مثبت (۶ ماهه)
            if len(hist) > 1:
                six_month_return = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100
                if six_month_return > 10:
                    pros.append(f"📈 بازده ۶ ماهه: +{six_month_return:.1f}%")
                elif six_month_return > 0:
                    pros.append(f"📈 بازده مثبت: +{six_month_return:.1f}%")
            
            # 2. حجم معاملات بالا
            avg_volume = info.get('averageVolume', 0)
            if avg_volume > 5_000_000:
                pros.append(f"💰 حجم معاملات: {avg_volume/1e6:.1f}M (نقدینگی خوب)")
            
            # 3. نسبت PE کم
            pe = info.get('trailingPE', None)
            if pe and pe < 30:
                pros.append(f"💎 P/E: {pe:.1f} (نسبی کم)")
            elif pe and pe > 0:
                pros.append(f"📊 P/E: {pe:.1f}")
            
            # 4. رشد درآمد
            revenue_growth = info.get('revenueGrowth', None)
            if revenue_growth and revenue_growth > 0.2:
                pros.append(f"🚀 رشد درآمد: {revenue_growth*100:.0f}%+")
            
            # 5. نرخ سود
            profit_margin = info.get('profitMargins', None)
            if profit_margin and profit_margin > 0.15:
                pros.append(f"✅ سود خالص: {profit_margin*100:.1f}%")
            
            # ❌ نشانه‌های منفی
            
            # 1. بدهی بالا
            debt_to_equity = info.get('debtToEquity', None)
            if debt_to_equity and debt_to_equity > 2.0:
                cons.append(f"⚠️ نسبت بدهی: {debt_to_equity:.1f} (بالا)")
            
            # 2. بازده منفی شدید
            if len(hist) > 1 and six_month_return < -30:
                cons.append(f"🔴 افت شدید: {six_month_return:.1f}%")
            
            # 3. نقدینگی کم
            if avg_volume < 500_000:
                cons.append(f"❌ حجم معاملات کم: {avg_volume/1e3:.0f}K")
            
            # 4. سود منفی
            if profit_margin and profit_margin < -0.1:
                cons.append(f"❌ سود منفی: {profit_margin*100:.1f}%")
            
            # حساب امتیاز
            pos_score = len(pros)
            neg_score = len(cons)
            
            return pos_score, neg_score, pros, cons
            
        except Exception as e:
            print(f"⚠️ خطا در {symbol}: {e}")
            return 0, 0, [], []
    
    def filter_stocks(self) -> List[Dict]:
        """
        فیلتر کردن سهام‌ها بر اساس:
        - حداقل ۳ نشانهٔ مثبت
        - حداکثر ۱ نشانهٔ منفی
        """
        print("🔍 در حال بررسی سهام‌ها...\n")
        
        selected = []
        
        for symbol in self.AI_BASKET:
            print(f"📊 {symbol}...", end=" ", flush=True)
            
            pos_score, neg_score, pros, cons = self.score_stock(symbol)
            
            # معیار انتخاب
            if pos_score >= self.MIN_POSITIVE_SCORE and neg_score <= self.MAX_NEGATIVE_SCORE:
                print(f"✅ ({pos_score} مثبت, {neg_score} منفی)")
                selected.append({
                    'symbol': symbol,
                    'positive_score': pos_score,
                    'negative_score': neg_score,
                    'pros': pros,
                    'cons': cons
                })
            else:
                reason = []
                if pos_score < self.MIN_POSITIVE_SCORE:
                    reason.append(f"خبرهای مثبت کم ({pos_score})")
                if neg_score > self.MAX_NEGATIVE_SCORE:
                    reason.append(f"نقاط ضعف ({neg_score})")
                print(f"❌ ({', '.join(reason)})")
        
        self.filtered_stocks = selected
        return selected
    
    def format_telegram_message(self, stocks: List[Dict]) -> str:
        """تنسیق گزارش برای تلگرام"""
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        if not stocks:
            message = f"""
<b>🤖 سبد هوش مصنوعی - گزارش انتخابی</b>
{now}

❌ هیچ سهمی شرایط را کامل نکرد.
معیار: حداقل ۳ خبر مثبت + حداکثر ۱ نقطهٔ ضعیف

📌 این به معنای احتیاط سیستم است.
منتظر فرصت‌های بهتر...
"""
        else:
            message = f"""
<b>🤖 سبد هوش مصنوعی - گزارش انتخابی</b>
{now}
<i>فقط سهام با خبرهای مثبت زیاد</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            for stock in sorted(stocks, key=lambda x: x['positive_score'], reverse=True):
                symbol = stock['symbol']
                pos = stock['positive_score']
                
                message += f"\n<b>✅ {symbol}</b> ({pos} نشانهٔ مثبت)\n"
                
                for pro in stock['pros']:
                    message += f"  {pro}\n"
                
                if stock['cons']:
                    message += f"  <i>نکات: {', '.join([c.replace('⚠️ ', '').replace('❌ ', '') for c in stock['cons']])}</i>\n"
            
            message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 معیارهای انتخاب:
  ✅ حداقل ۳ خبر مثبت
  ✅ حداکثر ۱ نقطهٔ ضعیف
  
📊 کل سهام: {len(stocks)}/{len(self.AI_BASKET)}

⏰ بروز‌رسانی: هر روز (خودکار)
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
                print("✅ گزارش ارسال شد")
                return True
            else:
                print(f"❌ خطا: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ خطا: {e}")
            return False
    
    def run(self):
        """اجرای گزارش"""
        print("🚀 شروع گزارش سبدِ انتخابی...\n")
        
        # فیلتر کردن
        selected = self.filter_stocks()
        
        print(f"\n✅ {len(selected)} سهم از {len(self.AI_BASKET)} انتخاب شد\n")
        
        # تنسیق
        message = self.format_telegram_message(selected)
        print(message)
        
        # ارسال
        self.send_to_telegram(message)
        
        return selected

def run():
    """اجرای گزارش"""
    reporter = AIBasketSelectiveReport()
    selected = reporter.run()
    return selected

if __name__ == "__main__":
    run()
