#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load environment variables from .env or GitHub Secrets
سیستم پشتیبان محافظ برای Secrets
"""

import os
from pathlib import Path

def load_env_file():
    """بارگیری .env فایل اگر موجود باشد"""
    env_path = Path(__file__).parent / '.env'
    
    if env_path.exists():
        print(f"📝 بارگیری {env_path}...")
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
                        print(f"   ✅ {key.strip()}")
    else:
        print(f"⚠️  {env_path} موجود نیست")
        print("    💡 برای توسعهٔ محلی .env بساز (یا GitHub Secrets استفاده شود)")

def check_secrets():
    """بررسی Secrets موجود است"""
    required = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing = []
    
    for key in required:
        if not os.getenv(key):
            missing.append(key)
    
    if missing:
        print(f"\n⚠️  موارد گمشده: {', '.join(missing)}")
        print("   اقدام:")
        print("   1️⃣  .env فایل را بسازید (محلی)")
        print("   2️⃣  یا GitHub Secrets را تنظیم کنید")
        print("   3️⃣  SECRETS_SECURITY.md را بخوانید")
        return False
    
    print(f"\n✅ تمام Secrets موجود است")
    return True

if __name__ == "__main__":
    print("🔐 بارگیری Secrets...\n")
    load_env_file()
    check_secrets()
