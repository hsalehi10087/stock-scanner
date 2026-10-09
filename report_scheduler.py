#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report Scheduler - کنترل ارسال روزانه
یک‌بار روزی = یک‌بار در 24 ساعت
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List

class ReportScheduler:
    """کنترل زمان‌بندی و تکرار گزارش‌ها"""
    
    HISTORY_FILE = 'data/report_history.json'
    
    REPORTS = {
        'daily_comprehensive': {
            'name': 'گزارش روزانهٔ جامع',
            'time': '10:00',  # 10 صبح تهران
            'frequency': 'daily',
            'description': 'رژیم + سهام + سیگنال + عملکرد + کلان‌اقتصادی'
        },
        'strong_signals': {
            'name': 'سیگنال‌های قوی (RSI/MACD)',
            'frequency': 'on_change',
            'condition': 'تغییر بیشتر از 3 سیگنال',
            'description': 'فقط اگر تغییری در سیگنال‌ها شود'
        },
        'shared_stocks': {
            'name': 'سرمایه‌گذاران بزرگ - سهام مشترک',
            'frequency': 'on_change',
            'condition': 'تغییر در NEW/ADD/CUT/SOLD',
            'description': 'فقط اگر سرمایه‌گذار کبیری معامله کرد'
        },
        'ai_basket': {
            'name': 'سبدِ هوش مصنوعی - انتخابی',
            'frequency': 'on_change',
            'condition': 'تغییر در بهترین سهام',
            'description': 'فقط اگر سهام از شرایط خارج شد'
        }
    }
    
    def __init__(self):
        self.history = self.load_history()
    
    def load_history(self) -> Dict:
        """بارگیری تاریخچهٔ ارسال"""
        if os.path.exists(self.HISTORY_FILE):
            with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_history(self):
        """ذخیرهٔ تاریخچهٔ ارسال"""
        os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)
        with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def should_send_daily(self, report_key: str) -> bool:
        """بررسی آیا گزارش روزانه باید ارسال شود"""
        last_sent = self.history.get(report_key, {}).get('last_sent')
        
        if not last_sent:
            return True  # اول‌بار → ارسال کن
        
        # بررسی: آیا 24 ساعت گذشته؟
        last_sent_date = datetime.fromisoformat(last_sent).date()
        today = datetime.now().date()
        
        if last_sent_date < today:
            return True  # روز جدید → ارسال کن
        else:
            return False  # همان روز → نفرست
    
    def should_send_on_change(self, report_key: str, has_changes: bool) -> bool:
        """بررسی آیا گزارش تغییری باید ارسال شود"""
        if not has_changes:
            return False  # تغییری نیست → نفرست
        
        # اگر تغییر دارد، بررسی: آخرین ارسال کب بود؟
        last_sent = self.history.get(report_key, {}).get('last_sent')
        
        if not last_sent:
            return True  # اول‌بار → ارسال کن
        
        # اگر کمتر از ۱ ساعت گذشته، نفرست (جلوگیری از spam)
        last_sent_time = datetime.fromisoformat(last_sent)
        if datetime.now() - last_sent_time < timedelta(hours=1):
            return False
        
        return True
    
    def mark_sent(self, report_key: str, status: str = 'sent'):
        """علامت‌گذاری: گزارش ارسال شد"""
        if report_key not in self.history:
            self.history[report_key] = {}
        
        self.history[report_key]['last_sent'] = datetime.now().isoformat()
        self.history[report_key]['status'] = status
        self.save_history()
    
    def get_report_status(self) -> Dict[str, Dict]:
        """دریافت وضعیت تمام گزارش‌ها"""
        status = {}
        
        for key, info in self.REPORTS.items():
            history = self.history.get(key, {})
            last_sent = history.get('last_sent', 'هیچ‌وقت')
            
            if last_sent != 'هیچ‌وقت':
                last_sent_time = datetime.fromisoformat(last_sent)
                hours_ago = (datetime.now() - last_sent_time).total_seconds() / 3600
                last_sent_display = f"{hours_ago:.1f} ساعت پیش"
            else:
                last_sent_display = 'هیچ‌وقت'
            
            status[key] = {
                'name': info['name'],
                'frequency': info['frequency'],
                'last_sent': last_sent_display,
                'status': history.get('status', 'نامشخص')
            }
        
        return status
    
    def print_report_status(self):
        """نمایش وضعیت گزارش‌ها"""
        print("\n" + "="*70)
        print("📊 وضعیت گزارش‌های روزانه")
        print("="*70 + "\n")
        
        status = self.get_report_status()
        
        for key, info in status.items():
            print(f"📌 {info['name']}")
            print(f"   نوع: {info['frequency']}")
            print(f"   آخرین ارسال: {info['last_sent']}")
            print()

def check_all_reports():
    """بررسی شرایط ارسال تمام گزارش‌ها"""
    scheduler = ReportScheduler()
    
    print("\n" + "="*70)
    print("🔍 بررسی شرایط ارسال امروز")
    print("="*70 + "\n")
    
    for key, info in scheduler.REPORTS.items():
        if info['frequency'] == 'daily':
            should_send = scheduler.should_send_daily(key)
            status = "✅ ارسال شود" if should_send else "❌ ارسال نشود"
            print(f"{info['name']}")
            print(f"   {status}")
            print()
        
        elif info['frequency'] == 'on_change':
            print(f"{info['name']}")
            print(f"   شرط: {info['condition']}")
            print(f"   وضعیت: منتظر تغییر...")
            print()
    
    # نمایش تاریخچهٔ کامل
    scheduler.print_report_status()

if __name__ == "__main__":
    check_all_reports()
