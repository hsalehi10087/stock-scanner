#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش روزانه: بهترین سهم‌های روز بر اساس رژیم بازار
Daily Report: Best Stocks of the Day by Market Regime Detection
Now with REAL market data from Yahoo Finance
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import requests
import os

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

from report_scheduler import ReportScheduler

class DailyRegimeSignalsReal:
    """گزارش روزانهٔ سهام‌های بهترین - Real Market Data"""
    
    # سهام برای تحلیل
    SYMBOLS = {
        'US': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'WMT', 'JNJ'],
        'Tech': ['AAPL', 'MSFT', 'NVDA', 'META', 'GOOGL', 'AMD', 'INTC', 'AVGO'],
        'Finance': ['JPM', 'BAC', 'GS', 'MS', 'C', 'WFC'],
    }
    
    def __init__(self):
        self.scheduler = ReportScheduler()
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def get_real_market_data(self, symbol: str) -> Dict:
        """دریافت real market data از Yahoo Finance"""
        if not HAS_YFINANCE:
            return None
        
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            hist = stock.history(period='3mo')  # 3 months for regime detection
            
            if hist.empty:
                return None
            
            # محاسبهٔ regime indicators
            close = hist['Close']
            
            # RSI (14)
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # Volatility (ATR)
            high_low = hist['High'] - hist['Low']
            high_close = abs(hist['High'] - close.shift())
            low_close = abs(hist['Low'] - close.shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=14).mean()
            
            # Trend (slope of 20-day MA)
            ma20 = close.rolling(window=20).mean()
            trend_slope = (ma20.iloc[-1] - ma20.iloc[-20]) / ma20.iloc[-20] * 100 if len(ma20) >= 20 else 0
            
            # بازدهی
            daily_return = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100  # 5-day return
            
            return {
                'symbol': symbol,
                'name': info.get('shortName', symbol),
                'price': close.iloc[-1],
                'rsi': rsi.iloc[-1],
                'atr': atr.iloc[-1],
                'trend': trend_slope,
                'return_5d': daily_return,
                'volatility': atr.iloc[-1] / close.iloc[-1] * 100 if close.iloc[-1] > 0 else 0,
            }
        except Exception as e:
            return None
    
    def detect_regime(self, data_list: List[Dict]) -> str:
        """تشخیص رژیم بازار بر اساس داده‌ها"""
        if not data_list:
            return "Unknown"
        
        avg_rsi = np.mean([d['rsi'] for d in data_list if d['rsi']])
        avg_trend = np.mean([d['trend'] for d in data_list if d['trend'] is not None])
        avg_vol = np.mean([d['volatility'] for d in data_list if d['volatility']])
        
        # رژیم تشخیص
        if avg_rsi > 60 and avg_trend > 2:
            return "🚀 Bullish Trend"
        elif avg_rsi < 40 and avg_trend < -2:
            return "📉 Bearish Trend"
        elif 40 <= avg_rsi <= 60 and abs(avg_trend) < 2:
            return "➡️ Range/Sideways"
        elif avg_vol > 3:
            return "⚡ High Volatility"
        else:
            return "⏸️ Neutral"
    
    def analyze_market(self) -> Dict:
        """تحلیل کامل بازار - Real Data"""
        print("📊 دریافت داده‌های بازار از Yahoo Finance...")
        
        all_data = []
        for category, symbols in self.SYMBOLS.items():
            for symbol in symbols[:5]:  # 5 تا برای سرعت
                data = self.get_real_market_data(symbol)
                if data:
                    all_data.append(data)
        
        if not all_data:
            return None
        
        # مرتب‌سازی براساس بهترین performers
        all_data.sort(key=lambda x: x['return_5d'], reverse=True)
        
        regime = self.detect_regime(all_data)
        
        return {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'regime': regime,
            'top_stocks': all_data[:5],
            'all_data': all_data
        }
    
    def format_telegram_message(self, analysis: Dict) -> str:
        """تنسیق پیام برای تلگرام"""
        message = f"""
<b>📈 گزارش روزانهٔ بهترین سهام‌ها</b>
<b>{analysis['timestamp']} (تهران)</b>

<b>🔍 رژیم بازار: {analysis['regime']}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>⭐ ۵ بهترین سهم (۵ روز اخیر)</b>
"""
        
        for i, stock in enumerate(analysis['top_stocks'], 1):
            rsi_status = "🔥" if stock['rsi'] > 70 else "❄️" if stock['rsi'] < 30 else "⚖️"
            message += f"""
{i}. <b>{stock['symbol']}</b> ({stock['name'][:20]})
   💰 {stock['price']:.2f} | 📊 {stock['return_5d']:+.2f}%
   RSI: {stock['rsi']:.0f} {rsi_status} | Trend: {stock['trend']:+.1f}%
"""
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ منبع: Yahoo Finance (Real-Time)
📅 گزارش: روزی یک‌بار
🤖 رژیم: خودکار تشخیص شده
"""
        return message
    
    def send_report(self):
        """ارسال گزارش"""
        # بررسی: آیا امروز قبلاً ارسال شده
        if not self.scheduler.should_send_daily('daily_regime_signals'):
            print("⏭️ گزارش امروز قبلاً ارسال شده است")
            return
        
        print("🚀 تحلیل بازار (Real Data)...\n")
        
        analysis = self.analyze_market()
        if not analysis:
            print("❌ خطا: داده‌های بازار دریافت نشد")
            return
        
        message = self.format_telegram_message(analysis)
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
                    self.scheduler.mark_sent('daily_regime_signals')
                    print("✅ ارسال شد")
            except Exception as e:
                print(f"❌ خطا: {e}")
        else:
            print("⚠️ تلگرام تنظیم نشده")

def run():
    reporter = DailyRegimeSignalsReal()
    reporter.send_report()

if __name__ == "__main__":
    run()
