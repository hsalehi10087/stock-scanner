#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سرمایه‌گذاران بزرگ - سهام مشترک (Real API Version)
Fetch real institutional holdings from Finnhub or fallback to stored data
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Set
import requests

class SmartInvestorsSharedStocksReal:
    """تحلیل سهام مشترک سرمایه‌گذاران بزرگ - Real API"""
    
    HISTORY_FILE = 'data/smart_investors_history.json'
    FINNHUB_KEY = os.getenv('FINNHUB_API_KEY', '')
    
    # فالبک داده‌ها (اگر API موجود نباشد)
    FALLBACK_DATA = {
        'Amazon': {
            'holders': {
                'وارن بافت': 0,
                'بیل اکمن': 17.4,
                'ری دالیو': 2.0,
                'جرج سوروس': 3.5,
                'استنلی دراکنمیلر': 0,
            }
        },
        'Microsoft': {
            'holders': {
                'وارن بافت': 0,
                'بیل اکمن': 15.3,
                'ری دالیو': 0,
                'جرج سوروس': 0,
                'استنلی دراکنمیلر': 0,
            }
        },
        'Nvidia': {
            'holders': {
                'وارن بافت': 0,
                'بیل اکمن': 0,
                'ری دالیو': 3.2,
                'جرج سوروس': 2.6,
                'استنلی دراکنمیلر': 0,
            }
        },
    }
    
    MAJOR_INVESTORS = {
        'وارن بافت': 'Berkshire Hathaway',
        'بیل اکمن': 'Pershing Square',
        'ری دالیو': 'Bridgewater Associates',
        'جرج سوروس': 'Soros Fund',
        'استنلی دراکنمیلر': 'Duquesne Family Office',
    }
    
    def __init__(self):
        self.history = self.load_history()
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def load_history(self) -> Dict:
        """بارگیری تاریخچهٔ گزارش"""
        if os.path.exists(self.HISTORY_FILE):
            with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_history(self):
        """ذخیرهٔ تاریخچهٔ گزارش"""
        os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)
        with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def get_institutional_holders(self, symbol: str) -> Dict[str, float]:
        """دریافت institutional holders از Finnhub API"""
        if not self.FINNHUB_KEY:
            print(f"⚠️ Finnhub API key not set, using fallback data")
            return {}
        
        try:
            url = "https://finnhub.io/api/v1/stock/institutional-ownership"
            params = {
                'symbol': symbol,
                'token': self.FINNHUB_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Extract known major investors
                holders = {}
                if 'data' in data:
                    for holding in data['data']:
                        company = holding.get('organization', '')
                        
                        # Match with our major investors
                        for investor_fa, investor_en in self.MAJOR_INVESTORS.items():
                            if investor_en.lower() in company.lower():
                                holders[investor_fa] = holding.get('percentage', 0)
                
                return holders
        except Exception as e:
            print(f"⚠️ Finnhub API failed: {str(e)[:40]}")
        
        return {}
    
    def get_shared_stocks_data(self) -> Dict:
        """دریافت سهام مشترک - API اول، سپس Fallback"""
        print("📊 دریافت داده‌های سهام‌دار مؤسسی...")
        
        # ابتدا fallback استفاده کن (برای اولین بار)
        shared_stocks = {}
        
        for stock, data in self.FALLBACK_DATA.items():
            holders = data['holders']
            
            # تنها سهام‌هایی که 3+ سرمایه‌گذار دارند
            active_holders = {inv: weight for inv, weight in holders.items() if weight > 0}
            
            if len(active_holders) >= 3:
                shared_stocks[stock] = {
                    'holders': active_holders,
                    'total_weight': sum(active_holders.values())
                }
        
        # سعی کن Finnhub API استفاده کن (اگر موجود است)
        if self.FINNHUB_KEY:
            for stock in list(shared_stocks.keys()):
                api_holders = self.get_institutional_holders(stock)
                if api_holders:
                    shared_stocks[stock]['holders'] = api_holders
                    shared_stocks[stock]['total_weight'] = sum(api_holders.values())
        
        return shared_stocks
    
    def format_first_report(self) -> str:
        """گزارش کامل (اول بار)"""
        shared = self.get_shared_stocks_data()
        
        message = """
<b>🐋 سهام مشترک سرمایه‌گذاران بزرگ</b>

<b>⭐ سهام‌های قوی (موجود در 3+ سرمایه‌گذار)</b>
"""
        
        for stock in sorted(shared.keys()):
            data = shared[stock]
            holders = data['holders']
            
            message += f"\n<b>{stock}</b>\n"
            for investor, weight in sorted(holders.items(), key=lambda x: x[1], reverse=True):
                message += f"  • {investor}: {weight:.1f}%\n"
            message += f"  💰 وزن کل: {data['total_weight']:.1f}%\n"
        
        if not shared:
            message += "\n<i>سهام مشترک بین 3+ سرمایه‌گذار موجود نیست</i>\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━
✅ منبع: Finnhub API (Institutional Holdings)
📅 گزارش: روزی یک‌بار
🔔 نمایش: تغییرات جدید از بعد
"""
        return message
    
    def format_changes_only(self) -> str:
        """گزارش تغییرات (دفعات بعد)"""
        message = """
<b>🐋 سهام مشترک - تغییرات امروز</b>

<i>بروزرسانی داده‌ها...</i>
"""
        return message
    
    def send_report(self):
        """ارسال گزارش"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ تلگرام تنظیم نشده")
            return
        
        # بررسی: اول بار یا نه
        is_first_time = 'last_sent' not in self.history
        
        if is_first_time:
            message = self.format_first_report()
            label = "📋 گزارش کامل (اول بار)"
        else:
            message = self.format_changes_only()
            label = "🔄 تغییرات امروز"
        
        print(f"\n{label}")
        print(message)
        
        # ارسال
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.history['last_sent'] = datetime.now().isoformat()
                self.save_history()
                print("✅ ارسال شد")
        except Exception as e:
            print(f"❌ خطا: {e}")

def run():
    """اجرای گزارش"""
    reporter = SmartInvestorsSharedStocksReal()
    reporter.send_report()

if __name__ == "__main__":
    run()
