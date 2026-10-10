#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سرمایه‌گذاران بزرگ - سهام مشترک (بهینه‌شده)
Only show stocks held by 3+ major investors (strongest signal)
First time: full details | Subsequent: changes only
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Set
import requests

class SmartInvestorsSharedStocks:
    """تحلیل سهام مشترک سرمایه‌گذاران بزرگ"""
    
    HISTORY_FILE = 'data/smart_investors_history.json'
    
    # سرمایه‌گذاران بزرگ و سهام‌های آنها (Q2 2026)
    INVESTORS_DATA = {
        'وارن بافت': {
            'holdings': {
                'Apple': 22.0,
                'American Express': 17.1,
                'Coca Cola': 10.9,
                'Alphabet': 9.4,
                'Bank Of America': 9.2,
            },
            'changes': {
                'ADD': [
                    {'stock': 'Alphabet', 'change_pct': 45},
                    {'stock': 'Delta Air Line', 'change_pct': 44},
                ]
            }
        },
        'بیل اکمن': {
            'holdings': {
                'Brookfield': 17.6,
                'Amazon': 17.4,
                'Uber Technologies': 15.7,
                'Microsoft': 15.3,
                'Restaurant Brands': 12.2,
            },
            'changes': {
                'NEW': [{'stock': 'Microsoft'}],
                'CUT': [{'stock': 'Alphabet'}],
                'SOLD': [{'stock': 'Hilton Worldwide'}],
            }
        },
        'ری دالیو': {
            'holdings': {
                'State Street SPY': 16.3,
                'iShares': 9.2,
                'Nvidia': 3.2,
                'Broadcom': 2.0,
                'Amazon': 2.0,
            },
            'changes': {
                'ADD': [{'stock': 'Vanguard Index', 'change_pct': 189}],
                'CUT': [
                    {'stock': 'Broadcom', 'change_pct': -28},
                    {'stock': 'Amazon', 'change_pct': -54},
                ]
            }
        },
        'جرج سوروس': {
            'holdings': {
                'Amazon': 3.5,
                'Taiwan Semiconductors': 3.1,
                'Global Payments': 2.7,
                'Alphabet': 2.6,
                'Nvidia': 2.6,
            },
            'changes': {
                'NEW': [
                    {'stock': 'Super Micro Computer'},
                    {'stock': 'Nebius'},
                ],
                'ADD': [
                    {'stock': 'Entergy', 'change_pct': 1084},
                    {'stock': 'Digital Realty', 'change_pct': 840},
                ],
                'CUT': [
                    {'stock': 'Amazon', 'change_pct': -39},
                    {'stock': 'Taiwan Semiconductors', 'change_pct': -55},
                ]
            }
        },
        'استنلی دراکنمیلر': {
            'holdings': {
                'Natera': 16.6,
                'Taiwan Semiconductors': 5.4,
                'STMicroelectronics': 4.5,
                'Invesco': 3.4,
                'Insmed': 2.9,
            },
            'changes': {
                'NEW': [
                    {'stock': 'Alphabet'},
                    {'stock': 'Amazon', 'change_pct': 1083},
                ],
                'SOLD': [
                    {'stock': 'Broadcom'},
                ]
            }
        },
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
    
    def find_shared_stocks(self, min_investors: int = 3) -> Dict[str, List[str]]:
        """یافتن سهام مشترک بین N+ سرمایه‌گذار"""
        from collections import defaultdict
        
        stock_investors = defaultdict(list)
        
        # شمارش سهام در هر سرمایه‌گذار
        for investor, data in self.INVESTORS_DATA.items():
            for stock in data['holdings'].keys():
                stock_investors[stock].append(investor)
        
        # فیلتر: تنها سهام‌های مشترک بین min_investors+
        shared = {}
        for stock, investors in stock_investors.items():
            if len(investors) >= min_investors:
                shared[stock] = investors
        
        return shared
    
    def get_stock_details(self, stock_name: str) -> Dict:
        """دریافت جزئیات یک سهم در همهٔ سرمایه‌گذاران"""
        details = {'holders': {}, 'total_weight': 0}
        
        for investor, data in self.INVESTORS_DATA.items():
            if stock_name in data['holdings']:
                weight = data['holdings'][stock_name]
                changes = []
                
                # جستجو برای تغییرات
                for change_type, change_list in data['changes'].items():
                    for change in change_list:
                        if change['stock'] == stock_name:
                            change_pct = change.get('change_pct', '-')
                            changes.append(f"{change_type} ({change_pct}%)")
                
                details['holders'][investor] = {
                    'weight': weight,
                    'changes': changes
                }
                details['total_weight'] += weight
        
        return details
    
    def format_first_report(self) -> str:
        """گزارش کامل (اول بار)"""
        shared = self.find_shared_stocks(min_investors=3)
        
        message = """
<b>🐋 سهام مشترک سرمایه‌گذاران بزرگ</b>

<b>⭐ سهام‌های قوی (موجود در 3+ سرمایه‌گذار)</b>
"""
        
        for stock in sorted(shared.keys()):
            details = self.get_stock_details(stock)
            holders = details['holders']
            
            message += f"\n<b>{stock}</b>\n"
            for investor, info in holders.items():
                message += f"  • {investor}: {info['weight']}%"
                if info['changes']:
                    message += f" [{', '.join(info['changes'])}]"
                message += "\n"
            message += f"  💰 وزن کل: {details['total_weight']:.1f}%\n"
        
        if not shared:
            message += "\n<i>سهام مشترک بین 3+ سرمایه‌گذار موجود نیست</i>\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━
📅 گزارش: روزی یک‌بار
🔔 نمایش: تغییرات جدید از بعد
"""
        return message
    
    def format_changes_only(self) -> str:
        """گزارش تغییرات (دفعات بعد)"""
        shared = self.find_shared_stocks(min_investors=3)
        
        message = """
<b>🐋 سهام مشترک - تغییرات امروز</b>

"""
        
        has_changes = False
        for stock in sorted(shared.keys()):
            details = self.get_stock_details(stock)
            has_any_change = any(
                details['holders'][inv]['changes'] 
                for inv in details['holders']
            )
            
            if has_any_change:
                has_changes = True
                message += f"<b>{stock}</b>\n"
                for investor, info in details['holders'].items():
                    if info['changes']:
                        message += f"  • {investor}: {', '.join(info['changes'])}\n"
                message += "\n"
        
        if not has_changes:
            message += "<i>تغییری در سهام مشترک نداشته است</i>\n"
        
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
    reporter = SmartInvestorsSharedStocks()
    reporter.send_report()

if __name__ == "__main__":
    run()
