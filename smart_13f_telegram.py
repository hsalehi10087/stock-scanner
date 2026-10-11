#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سیستم هوشمند 13F + Telegram
Smart 13F + Telegram Reporter
"""

import os
import re
import json
import requests
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

class Smart13FTelegramReporter:
    """گزارش تغییرات 13F به Telegram"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.investors = {}
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.parse_file()
    
    def parse_file(self):
        """پارس فایل"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract investor blocks
        blocks = re.split(r'([^\n]+) — فصل', content)
        
        for i in range(1, len(blocks), 2):
            if i+1 < len(blocks):
                investor = blocks[i].strip()
                block_content = blocks[i+1]
                self.parse_investor(investor, block_content)
    
    def parse_investor(self, investor: str, content: str):
        """Parse investor data"""
        stocks = set()
        changes = {}
        
        lines = content.split('\n')
        
        for line in lines:
            # Extract holdings
            if '│' in line and any(x in line for x in ['22.0', '17.1', '10.9', '9.4', '15.7', '66.0']):
                parts = line.split('│')
                if len(parts) >= 2:
                    stock = parts[0].strip()
                    if stock and stock not in ['Top holdings']:
                        stocks.add(stock)
            
            # Extract changes
            for action in ['ADD', 'NEW', 'CUT', 'SOLD']:
                if action in line and '│' in line:
                    parts = [p.strip() for p in line.split('│')]
                    if len(parts) >= 2:
                        stock = parts[1] if len(parts) > 1 else ''
                        change = parts[2] if len(parts) > 2 else ''
                        if stock:
                            changes[stock] = {'action': action, 'change': change}
                            stocks.add(stock)
        
        self.investors[investor] = {'stocks': stocks, 'changes': changes}
    
    def find_shared_stocks(self, min_investors=3):
        """Find shared stocks"""
        stock_map = defaultdict(list)
        
        for investor, data in self.investors.items():
            for stock in data['stocks']:
                stock_map[stock].append(investor)
        
        return {s: inv for s, inv in stock_map.items() if len(inv) >= min_investors}
    
    def format_telegram_message(self) -> str:
        """Format message for Telegram"""
        shared = self.find_shared_stocks(3)
        
        if not shared:
            return "❌ سهام مشترک یافت نشد"
        
        message = """
<b>🐋 گزارش هوشمند سرمایه‌گذاران بزرگ</b>
<b>13F Smart Changes Report</b>

<b>📊 سهام مشترک: {} سهم (3+ سرمایه‌گذار)</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

""".format(len(shared))
        
        # Sort by investor count
        sorted_stocks = sorted(shared.items(), key=lambda x: len(x[1]), reverse=True)[:8]  # Top 8
        
        for stock, investors_list in sorted_stocks:
            message += f"<b>🔴 {stock}</b>\n"
            message += f"   👥 {len(investors_list)} سرمایه‌گذار: {', '.join(investors_list[:2])}\n"
            
            # Add changes
            changes = self._get_changes(stock)
            if changes:
                for investor, action, change_pct in changes[:2]:  # Top 2 changes
                    emoji = "📈" if action in ["ADD", "NEW"] else "📉"
                    message += f"   {emoji} {investor}: {action} {change_pct}\n"
            
            message += "\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ منبع: SEC 13F Filings
📅 تاریخ: {}
⏰ گزارش: تغییرات روزانه
🔔 فقط سهام‌های مشترک

""".format(datetime.now().strftime('%Y-%m-%d %H:%M'))
        
        return message
    
    def _get_changes(self, stock):
        """Get changes for a stock"""
        changes = []
        for investor, data in self.investors.items():
            if stock in data['changes']:
                change = data['changes'][stock]
                changes.append((investor, change['action'], change['change']))
        return changes
    
    def send_telegram(self):
        """Send to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ Telegram not configured")
            return False
        
        message = self.format_telegram_message()
        print(message)
        print("\n" + "="*60)
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            response = requests.post(url, data={
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }, timeout=10)
            
            if response.status_code == 200:
                print("✅ Telegram message sent successfully!")
                return True
            else:
                print(f"❌ Telegram error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

# Run
if __name__ == "__main__":
    reporter = Smart13FTelegramReporter('/root/.claude/uploads/3de20c8f-9652-5ca5-b38a-7b00a34bdb08/900986dc-attachment.txt')
    
    # Test message (without Telegram)
    print(reporter.format_telegram_message())
    
    # Send to Telegram (with credentials)
    reporter.send_telegram()
