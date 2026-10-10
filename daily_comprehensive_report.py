#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش روزانهٔ جامع (یک‌بار در روز - ساعت 10 صبح تهران)
Daily Comprehensive Report - Once per day at 10 AM Tehran time
"""

import os
from datetime import datetime
from typing import Dict, List
import requests
from signal_performance_tracker import SignalPerformanceTracker
from market_regime_detector import MarketRegimeDetector, generate_sample_ohlcv
from adaptive_trading_system import AdaptiveTradingSystem
from investment_report_v2 import InvestmentReportV2
from report_scheduler import ReportScheduler

class DailyComprehensiveReport:
    """گزارش روزانهٔ جامع - یک‌بار در روز"""
    
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.trading_system = AdaptiveTradingSystem()
        self.investment_report = InvestmentReportV2()
        self.performance_tracker = SignalPerformanceTracker()
        self.scheduler = ReportScheduler()

        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def get_strong_signals(self) -> Dict[str, List]:
        """
        دریافت فقط سیگنال‌های قوی
        (سیگنال‌هایی که 3+ بار تکرار شده‌اند)
        """
        # نمونهٔ سیگنال‌های قوی
        strong_signals = {
            'RSI': [
                {'symbol': 'GOOGL', 'rsi': 35, 'signal': 'Oversold', 'repeats': 5},
                {'symbol': 'NVDA', 'rsi': 75, 'signal': 'Overbought', 'repeats': 4},
            ],
            'MACD': [
                {'symbol': 'MSFT', 'signal': 'Bullish Crossover', 'repeats': 3},
                {'symbol': 'AMZN', 'signal': 'Bearish Crossover', 'repeats': 2},
            ]
        }
        
        # فیلتر: فقط سیگنال‌های 3+ تکرار
        filtered = {}
        for indicator, signals in strong_signals.items():
            filtered[indicator] = [s for s in signals if s['repeats'] >= 3]
        
        return filtered
    
    def format_telegram_message(self) -> str:
        """تنسیق گزارش کامل برای تلگرام"""
        
        # دریافت داده‌ها
        ohlcv = generate_sample_ohlcv(days=100)
        features = self.regime_detector.extract_features(ohlcv)
        regimes, _ = self.regime_detector.detect_regime_rule_based(features)
        regime_report = self.regime_detector.generate_report(regimes)
        
        trading_analysis = self.trading_system.generate_adaptive_signals(ohlcv)
        all_stocks = self.investment_report.analyze_all_stocks()
        performance = self.performance_tracker.get_performance_summary()
        strong_signals = self.get_strong_signals()
        
        now = datetime.now()
        
        message = f"""
<b>📊 گزارش روزانهٔ جامع</b>
<b>{now.strftime('%Y-%m-%d %H:%M')} (تهران)</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🎯 رژیم بازار</b>
رژیم: {trading_analysis['current_regime']}
اطمینان: {trading_analysis['confidence']*100:.0f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📈 بهترین ۳ سهام امروز</b>
"""
        
        best_stocks = sorted(all_stocks, key=lambda x: x['overall'], reverse=True)[:3]
        for i, stock in enumerate(best_stocks, 1):
            message += f"{i}. {stock['symbol']}: {stock['overall']:.0f}/100\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🔴 سیگنال‌های قوی (تکرار‌شده)</b>
"""
        
        if strong_signals['RSI']:
            message += "\n<b>RSI (Relative Strength Index):</b>\n"
            for sig in strong_signals['RSI']:
                message += f"  • {sig['symbol']}: {sig['signal']} (تکرار: {sig['repeats']})\n"
        
        if strong_signals['MACD']:
            message += "\n<b>MACD (Moving Average Convergence):</b>\n"
            for sig in strong_signals['MACD']:
                message += f"  • {sig['symbol']}: {sig['signal']} (تکرار: {sig['repeats']})\n"
        
        if not strong_signals['RSI'] and not strong_signals['MACD']:
            message += "<i>سیگنال قوی موجود نیست</i>\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 عملکرد سیگنال‌های تاریخی</b>
"""
        
        if performance['total_signals'] > 0:
            message += f"""
کل: {performance['total_signals']}
برنده: {performance['wins']} ✅
درصد برد: {performance['win_rate']:.0f}%
بازدهی: {performance['total_closed_return']:+.2f}%
"""
        else:
            message += "<i>سیگنالی ثبت نشده</i>\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>⚠️ توضیح</b>
✅ سیگنال‌های قوی = 3+ تکرار
❌ سیگنال‌های ضعیف = شامل نمی‌شوند
📅 گزارش: روزی یک‌بار (10 صبح)
"""
        
        return message
    
    def send_to_telegram(self, message: str) -> bool:
        """ارسال به تلگرام"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ تلگرام تنظیم نشده")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                print("✅ گزارش روزانه ارسال شد")
                return True
            else:
                print(f"❌ خطا: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ خطا: {e}")
            return False
    
    def run(self):
        """اجرای گزارش"""
        # ✅ بررسی: آیا امروز قبلاً ارسال شده است؟
        if not self.scheduler.should_send_daily('daily_comprehensive'):
            now = datetime.now()
            print(f"⏭️ گزارش امروز قبلاً ارسال شده است ({now.strftime('%Y-%m-%d %H:%M')})")
            print("⏹️ ارسال دوباره متوقف شد - فقط روزی یک‌بار\n")

            # نمایش وضعیت
            self.scheduler.print_report_status()
            return None

        print("🚀 تولید گزارش روزانهٔ جامع...\n")

        message = self.format_telegram_message()
        print(message)
        print("\n" + "="*60)

        # ✅ ارسال به تلگرام
        if self.send_to_telegram(message):
            # ✅ علامت‌گذاری: ارسال شد
            self.scheduler.mark_sent('daily_comprehensive', 'sent')
            print("\n✅ گزارش روزانه تکمیل شد و ارسال شد!")
        else:
            # ⚠️ اگر ارسال ناموفق بود، علامت نگذاریم (دوباره تلاش کنیم)
            print("\n⚠️ گزارش ارسال نشد - دوباره تلاش خواهد شد")

        return message

def run():
    """اجرای گزارش"""
    reporter = DailyComprehensiveReport()
    message = reporter.run()
    return message

if __name__ == "__main__":
    run()
