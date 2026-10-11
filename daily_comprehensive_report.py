#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش روزانهٔ جامع - نسخهٔ REAL DATA
Daily Comprehensive Report - Real Yahoo Finance API
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List
import requests

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from signal_performance_tracker import SignalPerformanceTracker
from market_regime_detector import MarketRegimeDetector
from adaptive_trading_system import AdaptiveTradingSystem
from report_scheduler import ReportScheduler

class DailyComprehensiveReportReal:
    """گزارش روزانهٔ جامع - با real Yahoo Finance data"""
    
    # سهام برای تحلیل (US, China, Taiwan, Japan)
    STOCKS = {
        'US': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'JNJ', 'WMT'],
        'China': ['9988.HK', '0700.HK', '1398.HK', '1288.HK', '0001.HK'],
        'Taiwan': ['2330.TW', '2303.TW', '2454.TW'],
        'Japan': ['7203.T', '6758.T', '6861.T', '9432.T', '9684.T']
    }
    
    def __init__(self):
        self.scheduler = ReportScheduler()
        self.regime_detector = MarketRegimeDetector()
        self.trading_system = AdaptiveTradingSystem()
        self.performance_tracker = SignalPerformanceTracker()
        
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def get_stock_data(self, symbol: str) -> Dict:
        """دریافت real data از Yahoo Finance"""
        if not HAS_YFINANCE:
            return None
        
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period='1mo')
            
            if hist.empty:
                return None
            
            # محاسبهٔ RSI ساده
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return {
                'symbol': symbol,
                'name': info.get('longName', symbol),
                'price': info.get('currentPrice', 0),
                'rsi': rsi.iloc[-1] if not rsi.empty else None,
                'change_pct': ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100),
                'volume': info.get('volume', 0)
            }
        except Exception as e:
            print(f"⚠️ {symbol}: {str(e)[:30]}")
            return None
    
    def get_top_stocks(self) -> List[Dict]:
        """دریافت بهترین سهام براساس RSI و Change"""
        print("📊 دریافت real data...")
        
        all_stocks = []
        
        for country, symbols in self.STOCKS.items():
            for symbol in symbols[:3]:  # تنها 3 تا برای سرعت
                data = self.get_stock_data(symbol)
                if data:
                    all_stocks.append(data)
        
        # مرتب‌سازی براساس change (بهترین performers)
        all_stocks.sort(key=lambda x: x['change_pct'], reverse=True)
        
        return all_stocks[:3]
    
    def format_telegram_message(self) -> str:
        """تنسیق پیام برای تلگرام"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        top_stocks = self.get_top_stocks()
        
        message = f"""
<b>📊 گزارش روزانهٔ جامع</b>
<b>{now} (تهران)</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 بهترین ۳ سهام امروز</b>
"""
        
        for i, stock in enumerate(top_stocks, 1):
            message += f"\n{i}. <b>{stock['symbol']}</b>\n"
            message += f"   نام: {stock['name']}\n"
            message += f"   قیمت: ${stock['price']:.2f}\n"
            message += f"   تغییر: {stock['change_pct']:+.2f}%\n"
            if stock['rsi']:
                message += f"   RSI: {stock['rsi']:.1f}\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ منبع: Yahoo Finance API (Real-Time)
📅 گزارش: روزی یک‌بار
"""
        
        return message
    
    def send_report(self):
        """ارسال گزارش"""
        # بررسی: آیا امروز قبلاً ارسال شده
        if not self.scheduler.should_send_daily('daily_comprehensive'):
            print("⏭️ گزارش امروز قبلاً ارسال شده است")
            return
        
        print("🚀 تولید گزارش روزانهٔ جامع (Real Data)...\n")
        
        message = self.format_telegram_message()
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
                    self.scheduler.mark_sent('daily_comprehensive')
                    print("✅ گزارش ارسال شد")
            except Exception as e:
                print(f"❌ خطا: {e}")
        else:
            print("⚠️ تلگرام تنظیم نشده")

def run():
    reporter = DailyComprehensiveReportReal()
    reporter.send_report()

if __name__ == "__main__":
    run()
