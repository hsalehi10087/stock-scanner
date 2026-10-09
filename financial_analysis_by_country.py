#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحلیل صورتهای مالی کشورمحور
Financial Analysis by Country - Top 10 من هر کشور
"""

import os
import json
from datetime import datetime
from typing import Dict, List

class FinancialAnalysisByCountry:
    """تحلیل مالی بر اساس کشور"""
    
    # داده‌های مالی - درآمد سالانه (میلیارد دلار)
    COMPANIES = {
        'USA': [
            {'symbol': 'AMZN', 'revenue': 776, 'prev_revenue': 750, 'pe': 45, 'growth': '+15%'},
            {'symbol': 'MSFT', 'revenue': 332, 'prev_revenue': 310, 'pe': 32, 'growth': '+12%'},
            {'symbol': 'AAPL', 'revenue': 467, 'prev_revenue': 450, 'pe': 28, 'growth': '+8%'},
            {'symbol': 'GOOGL', 'revenue': 446, 'prev_revenue': 420, 'pe': 24, 'growth': '+10%'},
            {'symbol': 'META', 'revenue': 228, 'prev_revenue': 200, 'pe': 22, 'growth': '+14%'},
            {'symbol': 'NVDA', 'revenue': 303, 'prev_revenue': 250, 'pe': 68, 'growth': '+22%'},
            {'symbol': 'TSLA', 'revenue': 104, 'prev_revenue': 95, 'pe': 88, 'growth': '+9%'},
            {'symbol': 'JPM', 'revenue': 186, 'prev_revenue': 180, 'pe': 12, 'growth': '+5%'},
            {'symbol': 'WMT', 'revenue': 736, 'prev_revenue': 710, 'pe': 38, 'growth': '+6%'},
            {'symbol': 'JNJ', 'revenue': 98, 'prev_revenue': 96, 'pe': 25, 'growth': '+3%'},
        ],
        'China': [
            {'symbol': '9988.HK', 'name': 'Alibaba', 'revenue': 1045, 'prev_revenue': 1000, 'pe': 15, 'growth': '+4%'},
            {'symbol': '0700.HK', 'name': 'Tencent', 'revenue': 788, 'prev_revenue': 750, 'pe': 18, 'growth': '+5%'},
            {'symbol': '1398.HK', 'name': 'ICBC', 'revenue': 682, 'prev_revenue': 670, 'pe': 5, 'growth': '+2%'},
            {'symbol': '1288.HK', 'name': 'China State', 'revenue': 627, 'prev_revenue': 615, 'pe': 6, 'growth': '+2%'},
            {'symbol': '0001.HK', 'name': 'HSBC', 'revenue': 277, 'prev_revenue': 270, 'pe': 8, 'growth': '+3%'},
            {'symbol': '2318.HK', 'name': 'Ping An', 'revenue': 210, 'prev_revenue': 205, 'pe': 7, 'growth': '+2%'},
            {'symbol': '3988.HK', 'name': 'Baidu', 'revenue': 180, 'prev_revenue': 175, 'pe': 20, 'growth': '+3%'},
            {'symbol': '0175.HK', 'name': 'Geely', 'revenue': 145, 'prev_revenue': 140, 'pe': 8, 'growth': '+4%'},
            {'symbol': '1211.HK', 'name': 'BYD', 'revenue': 160, 'prev_revenue': 150, 'pe': 35, 'growth': '+7%'},
            {'symbol': '6862.HK', 'name': 'ZTO Express', 'revenue': 95, 'prev_revenue': 90, 'pe': 25, 'growth': '+6%'},
        ],
        'Taiwan': [
            {'symbol': '2330.TW', 'name': 'TSMC', 'revenue': 220, 'prev_revenue': 200, 'pe': 18, 'growth': '+10%'},
            {'symbol': '2303.TW', 'name': 'MediaTek', 'revenue': 85, 'prev_revenue': 78, 'pe': 28, 'growth': '+9%'},
            {'symbol': '2454.TW', 'name': 'MediaTek', 'revenue': 45, 'prev_revenue': 42, 'pe': 22, 'growth': '+7%'},
            {'symbol': '2317.TW', 'name': 'Quanta', 'revenue': 62, 'prev_revenue': 58, 'pe': 15, 'growth': '+7%'},
            {'symbol': '2883.TW', 'name': 'Zscan', 'revenue': 38, 'prev_revenue': 36, 'pe': 32, 'growth': '+6%'},
            {'symbol': '2912.TW', 'name': 'Delta', 'revenue': 48, 'prev_revenue': 45, 'pe': 20, 'growth': '+7%'},
            {'symbol': '3045.TW', 'name': 'Taiwan Mask', 'revenue': 12, 'prev_revenue': 11, 'pe': 25, 'growth': '+8%'},
            {'symbol': '4904.TW', 'name': 'Faraday', 'revenue': 8, 'prev_revenue': 7, 'pe': 45, 'growth': '+15%'},
            {'symbol': '2108.TW', 'name': 'Wistron', 'revenue': 32, 'prev_revenue': 30, 'pe': 12, 'growth': '+7%'},
            {'symbol': '3162.TW', 'name': 'Unimicron', 'revenue': 28, 'prev_revenue': 26, 'pe': 18, 'growth': '+8%'},
        ],
        'Japan': [
            {'symbol': '7203.T', 'name': 'Toyota', 'revenue': 380, 'prev_revenue': 370, 'pe': 8, 'growth': '+3%'},
            {'symbol': '6758.T', 'name': 'Sony', 'revenue': 280, 'prev_revenue': 270, 'pe': 18, 'growth': '+4%'},
            {'symbol': '6861.T', 'name': 'Keyence', 'revenue': 65, 'prev_revenue': 60, 'pe': 45, 'growth': '+8%'},
            {'symbol': '9432.T', 'name': 'Nintendo', 'revenue': 18, 'prev_revenue': 17, 'pe': 25, 'growth': '+6%'},
            {'symbol': '9684.T', 'name': 'Rakuten', 'revenue': 28, 'prev_revenue': 26, 'pe': 15, 'growth': '+8%'},
            {'symbol': '6981.T', 'name': 'Murata', 'revenue': 38, 'prev_revenue': 36, 'pe': 22, 'growth': '+6%'},
            {'symbol': '6502.T', 'name': 'Taiyo Yuden', 'revenue': 22, 'prev_revenue': 21, 'pe': 20, 'growth': '+5%'},
            {'symbol': '6594.T', 'name': 'Nidec', 'revenue': 45, 'prev_revenue': 43, 'pe': 28, 'growth': '+5%'},
            {'symbol': '7741.T', 'name': 'Hoya', 'revenue': 35, 'prev_revenue': 33, 'pe': 25, 'growth': '+6%'},
            {'symbol': '8035.T', 'name': 'Tokyo Electron', 'revenue': 42, 'prev_revenue': 40, 'pe': 35, 'growth': '+5%'},
        ]
    }
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def calculate_revenue_change(self, revenue: float, prev_revenue: float) -> str:
        """محاسبهٔ درصد تغییر درآمد"""
        if prev_revenue == 0:
            return '+0%'
        change = ((revenue - prev_revenue) / prev_revenue) * 100
        return f"{change:+.1f}%"
    
    def get_top_10_by_country(self) -> Dict[str, List]:
        """دریافت بهترین 10 سهم از هر کشور"""
        top_10 = {}
        
        for country, companies in self.COMPANIES.items():
            # مرتب‌سازی بر اساس رشد
            sorted_companies = sorted(
                companies,
                key=lambda x: float(x['growth'].replace('%', '').replace('+', '')),
                reverse=True
            )[:10]
            
            top_10[country] = sorted_companies
        
        return top_10
    
    def format_telegram_message(self) -> str:
        """تنسیق گزارش برای تلگرام"""
        top_10 = self.get_top_10_by_country()
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        message = f"""
<b>📊 تحلیل صورتهای مالی کشورمحور</b>
{now} (تهران)
<i>بهترین 10 سهم + درصد تغییر درآمد</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        country_names = {
            'USA': '🇺🇸 آمریکا',
            'China': '🇨🇳 چین',
            'Taiwan': '🇹🇼 تایوان',
            'Japan': '🇯🇵 ژاپن'
        }
        
        for country, companies in top_10.items():
            message += f"\n<b>{country_names[country]}</b>\n"
            message += "<code>"
            message += "نماد      | درآمد  | تغییر | رشد\n"
            message += "─" * 40 + "\n"
            
            for i, company in enumerate(companies, 1):
                symbol = company['symbol']
                revenue = company['revenue']
                change = self.calculate_revenue_change(
                    company['revenue'],
                    company['prev_revenue']
                )
                growth = company['growth']
                
                message += f"{symbol:8} | ${revenue:5}M | {change:>5} | {growth:>5}\n"
            
            message += "</code>\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 توضیح ستون‌ها:</b>
  • درآمد: میلیارد دلار سالانه
  • تغییر: درصد تغییر نسبت به گزارش قبل
  • رشد: درصد رشد حاصل‌شده

<b>🎯 معیار انتخاب:</b>
  ✅ بهترین 10 بر اساس رشد
  ✅ درصد تغییر درآمد
  ✅ جدا برای هر کشور
"""
        
        return message
    
    def print_console_report(self):
        """نمایش گزارش در کنسول"""
        top_10 = self.get_top_10_by_country()
        
        print("\n" + "="*70)
        print("📊 تحلیل صورتهای مالی کشورمحور")
        print("="*70 + "\n")
        
        country_names = {
            'USA': '🇺🇸 آمریکا',
            'China': '🇨🇳 چین',
            'Taiwan': '🇹🇼 تایوان',
            'Japan': '🇯🇵 ژاپن'
        }
        
        for country, companies in top_10.items():
            print(f"\n{country_names[country]}")
            print("─" * 70)
            print(f"{'نماد':<10} {'درآمد':<15} {'تغییر':<12} {'رشد':<10}")
            print("─" * 70)
            
            for company in companies:
                symbol = company['symbol']
                revenue = f"${company['revenue']}M"
                change = self.calculate_revenue_change(
                    company['revenue'],
                    company['prev_revenue']
                )
                growth = company['growth']
                
                print(f"{symbol:<10} {revenue:<15} {change:<12} {growth:<10}")
    
    def send_to_telegram(self, message: str) -> bool:
        """ارسال به تلگرام"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ تلگرام تنظیم نشده")
            return False
        
        try:
            import requests
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
        """اجرای تحلیل"""
        print("🔍 تحلیل صورتهای مالی...\n")
        
        # نمایش در کنسول
        self.print_console_report()
        
        # تنسیق و ارسال
        message = self.format_telegram_message()
        print(message)
        
        self.send_to_telegram(message)

def run():
    """اجرای تحلیل"""
    analyzer = FinancialAnalysisByCountry()
    analyzer.run()

if __name__ == "__main__":
    run()
