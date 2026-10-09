#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش روزانه: بهترین سهم‌های روز بر اساس رژیم بازار
Daily Report: Best Stocks of the Day by Market Regime Detection
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import requests
import os
from market_regime_detector import MarketRegimeDetector, generate_sample_ohlcv
from adaptive_trading_system import AdaptiveTradingSystem
from investment_report_v2 import InvestmentReportV2

class DailyRegimeSignals:
    """گزارش روزانهٔ سهام‌های بهترین بر اساس رژیم"""
    
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.trading_system = AdaptiveTradingSystem()
        self.investment_report = InvestmentReportV2()
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def get_market_data(self) -> pd.DataFrame:
        """دریافت داده‌های بازار (فعلاً نمونه)"""
        # توده: اتصال به API واقعی
        return generate_sample_ohlcv(days=100)
    
    def analyze_market(self) -> Dict:
        """تحلیل کامل بازار"""
        # دریافت داده‌ها
        ohlcv = self.get_market_data()
        
        # تشخیص رژیم
        features = self.regime_detector.extract_features(ohlcv)
        regimes, _ = self.regime_detector.detect_regime_rule_based(features)
        regime_report = self.regime_detector.generate_report(regimes)
        
        # سیگنال‌های معاملاتی
        trading_analysis = self.trading_system.generate_adaptive_signals(ohlcv)
        
        # تحلیل سهام
        all_stocks = self.investment_report.analyze_all_stocks()
        
        return {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'jalali_date': self.investment_report.jalali_date,
            'regime': regime_report,
            'trading': trading_analysis,
            'stocks': all_stocks
        }
    
    def get_best_stocks_by_regime(self, analysis: Dict, top_n: int = 5) -> Dict[str, List]:
        """بهترین سهم‌ها برای هر رژیم"""
        stocks = analysis['stocks']
        regime_id = analysis['trading']['regime_id']
        
        best_by_regime = {}
        
        # 🔥 رژیم صعودی: بالاترین short-term score
        if regime_id == 0:
            best_by_regime['strategy'] = "📈 Trend Following"
            best_by_regime['stocks'] = sorted(
                stocks, 
                key=lambda x: x['short_term'], 
                reverse=True
            )[:top_n]
        
        # ❄️ رژیم نزولی: بالاترین short-term (خرید نقطهٔ ورود)
        elif regime_id == 1:
            best_by_regime['strategy'] = "📉 Short Selling Ready"
            best_by_regime['stocks'] = sorted(
                stocks, 
                key=lambda x: x['short_term'], 
                reverse=True
            )[:top_n]
        
        # 🔄 رژیم رنج: بالاترین profit margin (Mean Reversion)
        elif regime_id == 2:
            best_by_regime['strategy'] = "🔄 Mean Reversion"
            best_by_regime['stocks'] = sorted(
                stocks, 
                key=lambda x: x['profit_margin'], 
                reverse=True
            )[:top_n]
        
        # ⚡ رژیم بحران: بالاترین long-term (محافظ‌کاری)
        else:
            best_by_regime['strategy'] = "⚡ Defensive (Crisis Mode)"
            best_by_regime['stocks'] = sorted(
                stocks, 
                key=lambda x: x['long_term'], 
                reverse=True
            )[:top_n]
        
        return best_by_regime
    
    def format_telegram_message(self, analysis: Dict) -> str:
        """تنسیق پیام تلگرام"""
        regime_info = analysis['regime']
        trading_info = analysis['trading']
        best_stocks = self.get_best_stocks_by_regime(analysis)
        
        message = f"""
<b>📊 گزارش روزانهٔ رژیم بازار</b>

<b>⏰ تاریخ:</b> {analysis['jalali_date']} میلادی
<b>🎯 رژیم فعلی:</b> {trading_info['current_regime']}
<b>📈 اطمینان:</b> {trading_info['confidence']*100:.0f}%

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>💡 استراتژی فعال:</b> {best_stocks['strategy']}

<b>🏆 بهترین ۵ سهام امروز:</b>
<code>
"""
        
        # جدول بهترین سهام
        message += "<b>نماد / کوتاه / بلند / امتیاز</b>\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for i, stock in enumerate(best_stocks['stocks'][:5], 1):
            symbol = stock['symbol'].ljust(7)
            short = f"{stock['short_term']:.0f}".rjust(5)
            long = f"{stock['long_term']:.0f}".rjust(5)
            overall = f"{stock['overall']:.0f}".rjust(5)
            
            message += f"{i}. {symbol} {short} {long} {overall}\n"
        
        message += """</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>📌 توضیح ستون‌ها:</b>
• <b>کوتاه:</b> امتیاز ۳-۶ ماه (۰-۱۰۰)
• <b>بلند:</b> امتیاز ۱-۳ سال (۰-۱۰۰)
• <b>امتیاز:</b> میانگین کوتاه‌مدت و بلند‌مدت

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>📊 توزیع رژیم‌ها (۱۰۰ روز اخیر):</b>
"""
        
        for regime_name, count in regime_info['regime_distribution'].items():
            percentage = regime_info['regime_percentages'][regime_name]
            message += f"  {regime_name}: {count} روز ({percentage})\n"
        
        message += f"""

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

⚠️ <i>گزارش برای اطلاع‌رسانی است و توصیهٔ سرمایه‌گذاری نیست.</i>

#رژیم_بازار #تحلیل #سهام #خرید_فروش
"""
        
        return message
    
    def send_telegram_message(self, message: str) -> bool:
        """ارسال پیام به تلگرام"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تعریف نشده")
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
                print("✅ پیام به تلگرام ارسال شد")
                return True
            else:
                print(f"❌ خطا در ارسال: {response.status_code}")
                return False
        
        except Exception as e:
            print(f"❌ خطا: {e}")
            return False
    
    def run(self):
        """اجرای گزارش کامل"""
        print("🚀 شروع تحلیل رژیم بازار...\n")
        
        # تحلیل
        analysis = self.analyze_market()
        
        # تنسیق پیام
        message = self.format_telegram_message(analysis)
        
        # نمایش در کنسول
        print(message)
        
        # ارسال به تلگرام
        self.send_telegram_message(message)
        
        print("\n✅ تکمیل شد!")
        
        return analysis

def run():
    """اجرای گزارش روزانه"""
    reporter = DailyRegimeSignals()
    analysis = reporter.run()
    return analysis

if __name__ == "__main__":
    run()
