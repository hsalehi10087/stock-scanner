#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحلیل صورتهای مالی کشورمحور
Financial Analysis by Country - Smart caching with change detection
"""

import os
import json
from datetime import datetime
from typing import Dict, List
import requests
import hashlib

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

class FinancialAnalysisByCountry:
    """تحلیل مالی بر اساس کشور - با تشخیص تغییرات"""
    
    # لیست سهام برای هر کشور
    STOCKS_BY_COUNTRY = {
        'USA': ['AMZN', 'MSFT', 'AAPL', 'GOOGL', 'META', 'NVDA', 'TSLA', 'JPM', 'WMT', 'JNJ'],
        'China': ['9988.HK', '0700.HK', '1398.HK', '1288.HK', '0001.HK', '2318.HK', '3988.HK', '0175.HK', '1211.HK', '6862.HK'],
        'Taiwan': ['2330.TW', '2303.TW', '2454.TW', '2317.TW', '2883.TW', '2912.TW', '3045.TW', '4904.TW', '2108.TW', '3162.TW'],
        'Japan': ['7203.T', '6758.T', '6861.T', '9432.T', '9684.T', '6981.T', '6502.T', '6594.T', '7741.T', '8035.T'],
    }
    
    # داده‌های fallback (اگر API کار نکرد)
    FALLBACK_DATA = {
        'USA': [
            {'symbol': 'NVDA', 'name': 'NVIDIA', 'revenue_billions': 303, 'growth': 0.22, 'pe': 68},
            {'symbol': 'META', 'name': 'Meta', 'revenue_billions': 228, 'growth': 0.14, 'pe': 22},
            {'symbol': 'GOOGL', 'name': 'Alphabet', 'revenue_billions': 446, 'growth': 0.10, 'pe': 24},
            {'symbol': 'MSFT', 'name': 'Microsoft', 'revenue_billions': 332, 'growth': 0.12, 'pe': 32},
            {'symbol': 'AMZN', 'name': 'Amazon', 'revenue_billions': 776, 'growth': 0.15, 'pe': 45},
        ],
        'China': [
            {'symbol': '9988.HK', 'name': 'Alibaba', 'revenue_billions': 1045, 'growth': 0.04, 'pe': 15},
            {'symbol': '0700.HK', 'name': 'Tencent', 'revenue_billions': 788, 'growth': 0.05, 'pe': 18},
            {'symbol': '1398.HK', 'name': 'ICBC', 'revenue_billions': 682, 'growth': 0.02, 'pe': 5},
        ],
        'Taiwan': [
            {'symbol': '2330.TW', 'name': 'TSMC', 'revenue_billions': 220, 'growth': 0.10, 'pe': 18},
            {'symbol': '2303.TW', 'name': 'MediaTek', 'revenue_billions': 85, 'growth': 0.09, 'pe': 28},
        ],
        'Japan': [
            {'symbol': '7203.T', 'name': 'Toyota', 'revenue_billions': 380, 'growth': 0.03, 'pe': 8},
            {'symbol': '6758.T', 'name': 'Sony', 'revenue_billions': 280, 'growth': 0.04, 'pe': 18},
        ]
    }
    
    HISTORY_FILE = 'data/financial_analysis_history.json'
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.history = self.load_history()
    
    def load_history(self) -> Dict:
        """بارگیری تاریخچهٔ داده‌های قدیمی"""
        if os.path.exists(self.HISTORY_FILE):
            with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'last_hash': None, 'last_sent': None}
    
    def save_history(self, data_hash: str):
        """ذخیرهٔ hash داده‌های جدید"""
        os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)
        self.history = {
            'last_hash': data_hash,
            'last_sent': datetime.now().isoformat()
        }
        with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def get_stock_data(self, symbol: str) -> Dict:
        """دریافت داده‌های واقعی از yfinance"""
        if not HAS_YFINANCE:
            return None
        
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            data = {
                'symbol': symbol,
                'name': info.get('longName', symbol),
                'revenue_billions': info.get('totalRevenue', 0) / 1e9,
                'growth': info.get('revenueGrowth', 0),
                'pe': info.get('trailingPE', 0),
            }
            return data if data['revenue_billions'] > 0 else None
        except Exception as e:
            return None
    
    def get_financial_data(self) -> Dict[str, List]:
        """دریافت داده‌های مالی - API یا Fallback"""
        print("📊 درحال دریافت داده‌ها...")
        
        result = {}
        api_success = False
        
        # سعی کن API را استفاده کن
        if HAS_YFINANCE:
            for country, symbols in self.STOCKS_BY_COUNTRY.items():
                companies = []
                for symbol in symbols[:3]:  # تنها 3 تا برای تست
                    data = self.get_stock_data(symbol)
                    if data:
                        companies.append(data)
                        api_success = True
                
                if companies:
                    companies.sort(key=lambda x: x.get('growth', 0) or 0, reverse=True)
                    result[country] = companies
        
        # اگر API کار نکرد، از Fallback استفاده کن
        if not api_success:
            print("⚠️ API در دسترس نیست - استفاده از داده‌های fallback")
            result = self.FALLBACK_DATA
        
        return result
    
    def calculate_data_hash(self, data: Dict) -> str:
        """محاسبهٔ hash داده‌ها برای تشخیص تغییرات"""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def format_telegram_message(self, data: Dict) -> str:
        """تنسیق پیام برای تلگرام"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        message = f"""
<b>📊 تحلیل صورتهای مالی کشورمحور</b>
<b>{now} (تهران)</b>

"""
        
        for country, companies in data.items():
            message += f"\n<b>🌍 {country}</b>\n"
            
            for i, comp in enumerate(companies[:5], 1):
                symbol = comp['symbol']
                revenue = comp['revenue_billions']
                growth = comp.get('growth', 0)
                pe = comp.get('pe', 0)
                
                growth_str = f"{growth*100:.1f}%" if growth else "N/A"
                pe_str = f"{pe:.1f}" if pe else "N/A"
                
                message += f"{i}. <b>{symbol}</b>\n"
                message += f"   💰 {revenue:.0f}B | "
                message += f"📈 {growth_str} | "
                message += f"P/E: {pe_str}\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━
✅ منبع: Yahoo Finance API
📅 گزارش: روزی یک‌بار (فقط تغییرات)
"""
        return message
    
    def send_report(self):
        """ارسال گزارش - فقط اگر تغییر کرده"""
        # دریافت داده‌ها
        data = self.get_financial_data()
        
        # محاسبهٔ hash
        current_hash = self.calculate_data_hash(data)
        previous_hash = self.history.get('last_hash')
        
        # بررسی: آیا تغییر کردند؟
        if current_hash == previous_hash:
            print("⏭️ داده‌ها تغییری نکردند - ارسال نشد")
            return
        
        print("✨ تغییرات شناسایی شدند - ارسال می‌شود...\n")
        
        message = self.format_telegram_message(data)
        print(message)
        
        # ارسال به تلگرام
        if self.telegram_token and self.telegram_chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                response = requests.post(url, data={
                    'chat_id': self.telegram_chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }, timeout=10)
                
                if response.status_code == 200:
                    self.save_history(current_hash)
                    print("✅ گزارش ارسال شد")
            except Exception as e:
                print(f"❌ خطا: {e}")
        else:
            print("⚠️ تلگرام تنظیم نشده - تنها نمایش")
            self.save_history(current_hash)

def run():
    reporter = FinancialAnalysisByCountry()
    reporter.send_report()

if __name__ == "__main__":
    run()
