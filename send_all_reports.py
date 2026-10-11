#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ارسال تمام گزارش‌ها به تلگرام"""

import os
import subprocess
import time

def send_report(script_name, report_name):
    """اجرا و ارسال گزارش"""
    print(f"\n{'='*70}")
    print(f"🚀 Sending: {report_name}")
    print(f"{'='*70}\n")
    
    try:
        result = subprocess.run(
            ['python3', script_name],
            env={**os.environ, 
                 'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN', ''),
                 'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID', '')},
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # نمایش آخر پیام
        lines = result.stdout.split('\n')
        for line in lines[-20:]:
            if line.strip():
                print(line)
        
        time.sleep(2)  # تاخیر بین ارسال‌ها
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:100]}")

# اجرا
reports = [
    ('daily_summary_report.py', '📰 Daily Summary'),
    ('smart_macro_report.py', '🌍 Macro Analysis'),
    ('smart_signal_filter.py', '🔥 Smart Signal Filter'),
]

print("""
╔════════════════════════════════════════════════════════════╗
║     🚀 Sending All Reports to Telegram                    ║
║     فرستادن تمام گزارش‌ها به تلگرام                      ║
╚════════════════════════════════════════════════════════════╝
""")

for script, name in reports:
    send_report(script, name)

print(f"\n{'='*70}")
print("✅ تمام گزارش‌ها فرستاده شدند!")
print(f"{'='*70}\n")
