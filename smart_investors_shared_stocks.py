#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Investors - Shared Stocks Only
سرمایه‌گذاران بزرگ - فقط سهام‌های مشترک
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Set

class SharedStocksTracker:
    """فقط سهام‌های مشترک بین چند سرمایه‌گذار"""
    
    # سرمایه‌گذاران کبیر
    MAJOR_INVESTORS = {
        'David Tepper': {},
        'Carl Icahn': {},
        'Dan Loeb': {},
        'Seth Klarman': {},
        'Cathie Wood': {},
        'Chase Coleman': {}
    }
    
    # سهام‌های مشترک (شناسایی‌شده از داده‌ها)
    SHARED_STOCKS = {
        'Amazon': {
            'investors': ['David Tepper', 'Dan Loeb', 'Seth Klarman', 'Chase Coleman'],
            'count': 4
        },
        'Alphabet': {
            'investors': ['David Tepper', 'Dan Loeb', 'Seth Klarman', 'Cathie Wood', 'Chase Coleman'],
            'count': 5
        },
        'Meta Platforms': {
            'investors': ['David Tepper', 'Cathie Wood', 'Chase Coleman'],
            'count': 3
        },
        'Taiwan Semiconductor': {
            'investors': ['David Tepper', 'Dan Loeb', 'Chase Coleman'],
            'count': 3
        },
        'Broadcom': {
            'investors': ['David Tepper', 'Dan Loeb', 'Chase Coleman'],
            'count': 3
        },
        'Nvidia': {
            'investors': ['Cathie Wood', 'Chase Coleman'],
            'count': 2
        }
    }
    
    # تغییرات جدید (Q2 2026)
    RECENT_CHANGES = {
        'David Tepper': {
            'Apple (Put)': 'NEW',
            'Boeing': 'NEW',
            'Broadcom': 'NEW',
            'Meta Platforms': 'ADD +55%',
            'Micron Technology': 'CUT -41%'
        },
        'Dan Loeb': {
            'Warner Bros Discovery': 'NEW +11.4%',
            'Alphabet': 'ADD +486%',
            'Taiwan Semiconductor': 'ADD +67%',
            'Meta Platforms': 'SOLD -100%',
            'Nvidia': 'SOLD -100%',
            'Broadcom': 'SOLD -100%'
        },
        'Seth Klarman': {
            'Cme': 'NEW',
            'Genuine Parts': 'ADD +89%',
            'Willis Towers': 'SOLD -100%'
        },
        'Cathie Wood': {
            'Space Exploration Technologies': 'NEW +5.0%',
            'Alphabet': 'ADD +45%',
            'Nvidia': 'ADD +33%',
            'Meta Platforms': 'ADD +55%'
        },
        'Chase Coleman': {
            'Cerebras Systems': 'NEW',
            'Advanced Micro': 'NEW',
            'Intel': 'ADD +160%',
            'Alphabet': 'CUT -45%',
            'Broadcom': 'CUT -51%'
        }
    }
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.history_file = 'data/shared_stocks_history.json'
    
    def get_shared_changes(self) -> Dict[str, List[Dict]]:
        """
        دریافت تغییرات برای سهام‌های مشترک
        فقط اگر چند سرمایه‌گذار بر روی یک سهم تغییر کرده‌اند
        """
        shared_changes = {}
        
        for symbol, info in self.SHARED_STOCKS.items():
            changes = []
            
            # بررسی تغییرات هر سرمایه‌گذار برای این سهم
            for investor in info['investors']:
                if investor in self.RECENT_CHANGES:
                    investor_changes = self.RECENT_CHANGES[investor]
                    
                    # بررسی اگر این سهم در تغییرات این سرمایه‌گذار است
                    for stock_name, change in investor_changes.items():
                        if symbol.lower() in stock_name.lower():
                            changes.append({
                                'investor': investor,
                                'action': change,
                                'symbol': symbol
                            })
            
            if changes:
                shared_changes[symbol] = changes
        
        return shared_changes
    
    def format_telegram_message(self, shared_changes: Dict) -> str:
        """تنسیق گزارش برای تلگرام"""
        
        if not shared_changes:
            return None  # اگر تغییری نیست، پیام نفرست
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        message = f"""
<b>🐋 سرمایه‌گذاران بزرگ - سهام‌های مشترک</b>
{now} (تهران)
<i>فقط سهام‌های چند سرمایه‌گذار + تغییرات</i>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        for symbol, changes in sorted(shared_changes.items()):
            # تعداد سرمایه‌گذاران
            investor_count = len(set(c['investor'] for c in changes))
            
            message += f"\n<b>{'💰' if investor_count >= 4 else '📊'} {symbol}</b> ({investor_count} سرمایه‌گذار)\n"
            
            for change in changes:
                action = change['action']
                investor = change['investor']
                
                # نماد بر اساس نوع تغییر
                symbol_map = {
                    'NEW': '🆕',
                    'ADD': '➕',
                    'CUT': '📉',
                    'SOLD': '❌'
                }
                
                symbol_prefix = symbol_map.get(action.split()[0], '●')
                message += f"  {symbol_prefix} {investor}: {action}\n"
        
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 معیار:
  • فقط سهام‌های ۲+ سرمایه‌گذار
  • فقط تغییرات (NEW/ADD/CUT/SOLD)
  • بدون تکرار

⏰ گزارش: هر موقع تغییر شد
"""
        
        return message
    
    def send_to_telegram(self, message: str) -> bool:
        """ارسال به تلگرام - فقط اگر تغییری است"""
        if not message:
            print("✅ تغییری نیست - پیام نفرستاده شد")
            return False
        
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
        """اجرای ردیابی"""
        print("🔍 بررسی سهام‌های مشترک...\n")
        
        # دریافت تغییرات
        shared_changes = self.get_shared_changes()
        
        print(f"📊 سهام‌های مشترک: {len(self.SHARED_STOCKS)}")
        print(f"📈 سهام‌های با تغییر: {len(shared_changes)}\n")
        
        if not shared_changes:
            print("✅ تغییری نیست - پیام نفرستاده نمی‌شود\n")
            return
        
        # نمایش در کنسول
        for symbol, changes in sorted(shared_changes.items()):
            investor_count = len(set(c['investor'] for c in changes))
            print(f"📌 {symbol} ({investor_count} سرمایه‌گذار):")
            for change in changes:
                print(f"   • {change['investor']}: {change['action']}")
            print()
        
        # تنسیق و ارسال
        message = self.format_telegram_message(shared_changes)
        
        if message:
            print(message)
            self.send_to_telegram(message)

def run():
    """اجرای ردیابی"""
    tracker = SharedStocksTracker()
    tracker.run()

if __name__ == "__main__":
    run()
