#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش روزانهٔ رژیم بازار + عملکرد سیگنال‌های قدیم
Daily Regime Signals + Historical Performance Tracking
"""

import os
from datetime import datetime
from signal_performance_tracker import SignalPerformanceTracker
from market_regime_detector import MarketRegimeDetector, generate_sample_ohlcv
from adaptive_trading_system import AdaptiveTradingSystem
from investment_report_v2 import InvestmentReportV2
import requests

class DailyRegimeSignalsV2:
    """گزارش روزانهٔ رژیم + عملکرد"""
    
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.trading_system = AdaptiveTradingSystem()
        self.investment_report = InvestmentReportV2()
        self.performance_tracker = SignalPerformanceTracker()
        
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    def get_market_data(self):
        """دریافت داده‌های بازار"""
        return generate_sample_ohlcv(days=100)
    
    def analyze_market(self):
        """تحلیل بازار"""
        ohlcv = self.get_market_data()
        features = self.regime_detector.extract_features(ohlcv)
        regimes, _ = self.regime_detector.detect_regime_rule_based(features)
        regime_report = self.regime_detector.generate_report(regimes)
        
        trading_analysis = self.trading_system.generate_adaptive_signals(ohlcv)
        all_stocks = self.investment_report.analyze_all_stocks()
        
        return {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'jalali_date': self.investment_report.jalali_date,
            'regime': regime_report,
            'trading': trading_analysis,
            'stocks': all_stocks
        }
    
    def get_best_stocks_by_regime(self, analysis, top_n=5):
        """بهترین سهام برای هر رژیم"""
        stocks = analysis['stocks']
        regime_id = analysis['trading']['regime_id']
        
        best_by_regime = {}
        
        if regime_id == 0:  # صعودی
            best_by_regime['strategy'] = "📈 Trend Following"
            best_by_regime['stocks'] = sorted(
                stocks, key=lambda x: x['short_term'], reverse=True
            )[:top_n]
        elif regime_id == 1:  # نزولی
            best_by_regime['strategy'] = "📉 Short Selling Ready"
            best_by_regime['stocks'] = sorted(
                stocks, key=lambda x: x['short_term'], reverse=True
            )[:top_n]
        elif regime_id == 2:  # رنج
            best_by_regime['strategy'] = "🔄 Mean Reversion"
            best_by_regime['stocks'] = sorted(
                stocks, key=lambda x: x['profit_margin'], reverse=True
            )[:top_n]
        else:  # بحران
            best_by_regime['strategy'] = "⚡ Defensive (Crisis Mode)"
            best_by_regime['stocks'] = sorted(
                stocks, key=lambda x: x['long_term'], reverse=True
            )[:top_n]
        
        return best_by_regime
    
    def format_telegram_message(self, analysis):
        """تنسیق پیام تلگرام با عملکرد"""
        regime_info = analysis['regime']
        trading_info = analysis['trading']
        best_stocks = self.get_best_stocks_by_regime(analysis)
        performance = self.performance_tracker.get_performance_summary()
        
        message = f"""
<b>📊 گزارش روزانهٔ رژیم بازار</b>

<b>⏰ تاریخ:</b> {analysis['jalali_date']} میلادی
<b>🎯 رژیم فعلی:</b> {trading_info['current_regime']}
<b>📈 اطمینان:</b> {trading_info['confidence']*100:.0f}%

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>💡 استراتژی فعال:</b> {best_stocks['strategy']}

<b>🏆 بهترین ۵ سهام امروز:</b>
<code>
<b>نماد / کوتاه / بلند / امتیاز</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        for i, stock in enumerate(best_stocks['stocks'][:5], 1):
            symbol = stock['symbol'].ljust(7)
            short = f"{stock['short_term']:.0f}".rjust(5)
            long = f"{stock['long_term']:.0f}".rjust(5)
            overall = f"{stock['overall']:.0f}".rjust(5)
            message += f"{i}. {symbol} {short} {long} {overall}\n"
        
        message += """</code>

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>📈 گزارش عملکرد سیگنال‌های تاریخی:</b>
"""
        
        if performance['total_signals'] > 0:
            message += f"""
<b>📊 خلاصه:</b>
  • کل سیگنال: <b>{performance['total_signals']}</b>
  • بسته‌شده: <b>{performance['closed_signals']}</b>
  • باز: <b>{performance['open_signals']}</b>

<b>🎯 نتایج:</b>
  • برنده: {performance['wins']} ✅
  • بازنده: {performance['losses']} ❌
  • درصد برد: <b>{performance['win_rate']:.1f}%</b>

<b>💰 بازدهی:</b>
  • میانگین: {performance['avg_closed_return']:+.2f}%
  • کل (بسته): {performance['total_closed_return']:+.2f}%
  • باز: {performance['open_return']:+.2f}%
"""
            
            if performance['closed_signals_data']:
                best = max(performance['closed_signals_data'], key=lambda x: x['final_return'])
                worst = min(performance['closed_signals_data'], key=lambda x: x['final_return'])
                message += f"""
<b>🏆 بهترین:</b> {best['symbol']} ({best['final_return']:+.2f}%)
<b>📉 بدترین:</b> {worst['symbol']} ({worst['final_return']:+.2f}%)
"""
            
            if performance['open_signals_data']:
                message += f"\n<b>🔓 سیگنال‌های باز:</b>\n"
                for signal in performance['open_signals_data'][:3]:
                    ret = signal['latest_return'] if signal['latest_return'] else 0
                    message += f"  • {signal['symbol']}: {ret:+.2f}% ({signal['entry_date']})\n"
        else:
            message += "<i>سیگنالی ثبت نشده</i>"
        
        message += f"""

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

<b>📊 توزیع رژیم‌ها (۱۰۰ روز):</b>
"""
        
        for regime_name, count in regime_info['regime_distribution'].items():
            percentage = regime_info['regime_percentages'][regime_name]
            message += f"  {regime_name}: {count} روز ({percentage})\n"
        
        message += f"""

<b>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>

⚠️ <i>گزارش برای اطلاع‌رسانی است و توصیهٔ سرمایه‌گذاری نیست.</i>

#رژیم_بازار #عملکرد #تحلیل #سهام
"""
        
        return message
    
    def send_telegram_message(self, message):
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
                print("✅ پیام ارسال شد")
                return True
            else:
                print(f"❌ خطا: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ خطا: {e}")
            return False
    
    def run(self):
        """اجرای کامل"""
        print("🚀 شروع تحلیل...\n")
        
        analysis = self.analyze_market()
        message = self.format_telegram_message(analysis)
        
        print(message)
        self.send_telegram_message(message)
        
        print("\n✅ تکمیل شد!")
        return analysis

def run():
    """اجرای گزارش"""
    reporter = DailyRegimeSignalsV2()
    analysis = reporter.run()
    return analysis

if __name__ == "__main__":
    run()
