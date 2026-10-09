#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ارسال Codal Report به تلگرام
استفاده: python3 send_codal_to_telegram.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from codal_pipeline import run_pipeline

def send_to_telegram(message: str, token: str, chat_id: str) -> bool:
    """ارسال پیام HTML به تلگرام"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            msg_id = response.json().get('result', {}).get('message_id')
            print(f"✅ پیام ارسال شد! Message ID: {msg_id}")
            return True
        else:
            print(f"❌ خطا {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ خطا در ارسال: {e}")
        return False

def main():
    # دریافت credentials
    HERE = os.path.dirname(os.path.abspath(__file__))
    cfg = {}
    
    if os.path.exists(os.path.join(HERE, "config.txt")):
        for line in open(os.path.join(HERE, "config.txt"), encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or cfg.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or cfg.get("TELEGRAM_CHAT_ID", "")
    
    if not TOKEN or not CHAT_ID:
        print("❌ خطا: TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده")
        print("\nراه‌حل:")
        print("  1. Environment variables:")
        print("     export TELEGRAM_BOT_TOKEN='your_token'")
        print("     export TELEGRAM_CHAT_ID='your_chat_id'")
        print("\n  2. یا config.txt:")
        print("     echo 'TELEGRAM_BOT_TOKEN=...' >> config.txt")
        print("     echo 'TELEGRAM_CHAT_ID=...' >> config.txt")
        return 1
    
    print("=" * 60)
    print("🚀 SENDING CODAL REPORT TO TELEGRAM")
    print("=" * 60)
    
    # تولید گزارش
    print("\n[1/2] تولید گزارش Codal...")
    blocks = run_pipeline()
    message = "\n".join(blocks)
    
    print(f"   پیام: {len(message)} کاراکتر")
    
    # ارسال
    print("\n[2/2] ارسال به تلگرام...")
    success = send_to_telegram(message, TOKEN, CHAT_ID)
    
    if success:
        print("\n✅ تکمیل شد!")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
