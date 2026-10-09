#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ردیابی عملکرد سیگنال‌های تاریخی
Signal Performance Tracking - Monitor historical signals and returns
"""

import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

class SignalPerformanceTracker:
    """ردیابی عملکرد سیگنال‌ها و بازدهی آن‌ها"""
    
    def __init__(self, data_dir: str = "data"):
        """
        Parameters:
        -----------
        data_dir: پوشهٔ نگهداری داده‌ها
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.signals_file = self.data_dir / "historical_signals.json"
        self.performance_file = self.data_dir / "signal_performance.csv"
        
        # بارگذاری داده‌های موجود
        self.signals = self._load_signals()
    
    def _load_signals(self) -> Dict:
        """بارگذاری سیگنال‌های تاریخی"""
        if self.signals_file.exists():
            with open(self.signals_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_signals(self):
        """ذخیرهٔ سیگنال‌ها"""
        with open(self.signals_file, 'w', encoding='utf-8') as f:
            json.dump(self.signals, f, ensure_ascii=False, indent=2)
    
    def record_signal(self, symbol: str, entry_price: float, signal_type: str, 
                     regime: str, strategy: str, short_score: float, long_score: float):
        """
        ثبت سیگنال جدید
        
        Parameters:
        -----------
        symbol: نماد سهام (مثلاً GOOGL)
        entry_price: قیمت ورود
        signal_type: نوع سیگنال (خرید/فروش)
        regime: رژیم بازار
        strategy: استراتژی استفاده‌شده
        short_score: امتیاز کوتاه‌مدت
        long_score: امتیاز بلند‌مدت
        """
        signal_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        self.signals[signal_id] = {
            'symbol': symbol,
            'entry_price': entry_price,
            'signal_type': signal_type,
            'regime': regime,
            'strategy': strategy,
            'short_score': short_score,
            'long_score': long_score,
            'entry_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'entry_timestamp': datetime.now().isoformat(),
            'returns': {}  # بازدهی روزانه
        }
        
        self._save_signals()
        print(f"✅ سیگنال ثبت شد: {symbol} @ {entry_price:.2f}")
        return signal_id
    
    def update_returns(self, symbol: str, current_price: float):
        """
        بروزرسانی بازدهی برای تمام سیگنال‌های باز
        
        Parameters:
        -----------
        symbol: نماد سهام
        current_price: قیمت فعلی
        """
        updated_count = 0
        
        for signal_id, signal_data in self.signals.items():
            if signal_data['symbol'] != symbol:
                continue
            
            # فقط سیگنال‌های باز (بدون خروج)
            if 'exit_price' in signal_data:
                continue
            
            entry_price = signal_data['entry_price']
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            
            # محاسبهٔ بازدهی
            signal_data['returns'][datetime.now().strftime("%Y-%m-%d")] = {
                'current_price': current_price,
                'pnl_percent': pnl_percent,
                'pnl_amount': current_price - entry_price,
                'timestamp': datetime.now().isoformat()
            }
            
            updated_count += 1
        
        if updated_count > 0:
            self._save_signals()
        
        return updated_count
    
    def close_signal(self, signal_id: str, exit_price: float, exit_reason: str = ""):
        """بستن سیگنال و محاسبهٔ بازدهی نهایی"""
        if signal_id not in self.signals:
            print(f"❌ سیگنال {signal_id} یافت نشد")
            return False
        
        signal_data = self.signals[signal_id]
        entry_price = signal_data['entry_price']
        
        signal_data['exit_price'] = exit_price
        signal_data['exit_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        signal_data['exit_timestamp'] = datetime.now().isoformat()
        signal_data['exit_reason'] = exit_reason
        
        # محاسبهٔ بازدهی نهایی
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        pnl_amount = exit_price - entry_price
        
        signal_data['final_return'] = {
            'pnl_percent': pnl_percent,
            'pnl_amount': pnl_amount,
            'success': pnl_percent > 0
        }
        
        self._save_signals()
        
        status = "✅ سود" if pnl_percent > 0 else "❌ زیان"
        print(f"{status}: {signal_data['symbol']} | {pnl_percent:+.2f}% | {pnl_amount:+.2f}")
        
        return True
    
    def get_open_signals(self) -> List[Dict]:
        """دریافت سیگنال‌های باز"""
        open_signals = []
        
        for signal_id, signal_data in self.signals.items():
            if 'exit_price' not in signal_data:
                open_signals.append({
                    'signal_id': signal_id,
                    'symbol': signal_data['symbol'],
                    'entry_price': signal_data['entry_price'],
                    'entry_date': signal_data['entry_date'],
                    'regime': signal_data['regime'],
                    'strategy': signal_data['strategy'],
                    'latest_return': self._get_latest_return(signal_data)
                })
        
        return sorted(open_signals, key=lambda x: x['symbol'])
    
    def get_closed_signals(self) -> List[Dict]:
        """دریافت سیگنال‌های بسته‌شده"""
        closed_signals = []
        
        for signal_id, signal_data in self.signals.items():
            if 'exit_price' in signal_data:
                closed_signals.append({
                    'signal_id': signal_id,
                    'symbol': signal_data['symbol'],
                    'entry_price': signal_data['entry_price'],
                    'exit_price': signal_data['exit_price'],
                    'entry_date': signal_data['entry_date'],
                    'exit_date': signal_data['exit_date'],
                    'regime': signal_data['regime'],
                    'strategy': signal_data['strategy'],
                    'final_return': signal_data['final_return']['pnl_percent'],
                    'success': signal_data['final_return']['success']
                })
        
        return sorted(closed_signals, key=lambda x: x['symbol'])
    
    def _get_latest_return(self, signal_data: Dict) -> Optional[float]:
        """دریافت آخرین بازدهی"""
        if not signal_data['returns']:
            return None
        
        latest_date = max(signal_data['returns'].keys())
        return signal_data['returns'][latest_date]['pnl_percent']
    
    def get_performance_summary(self) -> Dict:
        """خلاصهٔ عملکرد"""
        closed = self.get_closed_signals()
        open_signals = self.get_open_signals()
        
        if not closed and not open_signals:
            return {
                'total_signals': 0,
                'closed_signals': 0,
                'open_signals': 0,
                'win_rate': 0,
                'avg_return': 0,
                'total_return': 0
            }
        
        # سیگنال‌های بسته‌شده
        total_closed = len(closed)
        wins = sum(1 for s in closed if s['success'])
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        avg_return = sum(s['final_return'] for s in closed) / total_closed if total_closed > 0 else 0
        total_return = sum(s['final_return'] for s in closed)
        
        # سیگنال‌های باز
        open_return = sum(s['latest_return'] for s in open_signals if s['latest_return'] is not None)
        
        return {
            'total_signals': total_closed + len(open_signals),
            'closed_signals': total_closed,
            'open_signals': len(open_signals),
            'wins': wins,
            'losses': total_closed - wins,
            'win_rate': win_rate,
            'avg_closed_return': avg_return,
            'total_closed_return': total_return,
            'open_return': open_return,
            'closed_signals_data': closed,
            'open_signals_data': open_signals
        }
    
    def generate_performance_report(self) -> str:
        """تولید گزارش عملکرد برای تلگرام"""
        summary = self.get_performance_summary()
        
        if summary['total_signals'] == 0:
            return "<i>هنوز سیگنالی ثبت نشده</i>"
        
        report = f"""
<b>📈 گزارش عملکرد سیگنال‌ها</b>

<b>📊 خلاصه:</b>
  • <b>کل سیگنال:</b> {summary['total_signals']}
  • <b>بسته‌شده:</b> {summary['closed_signals']}
  • <b>باز:</b> {summary['open_signals']}

<b>🎯 نتایج (سیگنال‌های بسته‌شده):</b>
  • <b>برنده:</b> {summary['wins']} ✅
  • <b>بازنده:</b> {summary['losses']} ❌
  • <b>درصد برد:</b> {summary['win_rate']:.1f}%

<b>💰 بازدهی:</b>
  • <b>میانگین بازدهی:</b> {summary['avg_closed_return']:+.2f}%
  • <b>بازدهی کل (بسته):</b> {summary['total_closed_return']:+.2f}%
  • <b>بازدهی باز:</b> {summary['open_return']:+.2f}%
"""
        
        # بهترین و بدترین
        if summary['closed_signals_data']:
            best = max(summary['closed_signals_data'], key=lambda x: x['final_return'])
            worst = min(summary['closed_signals_data'], key=lambda x: x['final_return'])
            
            report += f"""
<b>🏆 بهترین سیگنال:</b> {best['symbol']} ({best['final_return']:+.2f}%)
<b>📉 بدترین سیگنال:</b> {worst['symbol']} ({worst['final_return']:+.2f}%)
"""
        
        # سیگنال‌های باز
        if summary['open_signals_data']:
            report += f"\n<b>🔓 سیگنال‌های باز:</b>\n"
            for signal in summary['open_signals_data'][:5]:  # بالای ۵
                ret = signal['latest_return'] if signal['latest_return'] else 0
                report += f"  • {signal['symbol']}: {ret:+.2f}% ({signal['entry_date']})\n"
        
        return report

def demo():
    """تست سیستم"""
    tracker = SignalPerformanceTracker()
    
    print("🚀 تست ردیابی عملکرد\n")
    
    # ثبت چند سیگنال نمونه
    print("📝 ثبت سیگنال‌ها:")
    tracker.record_signal(
        symbol="GOOGL",
        entry_price=140.0,
        signal_type="خرید",
        regime="🔄 رنج",
        strategy="🔄 Mean Reversion",
        short_score=75,
        long_score=85
    )
    
    tracker.record_signal(
        symbol="NVDA",
        entry_price=120.0,
        signal_type="خرید",
        regime="🔥 صعودی",
        strategy="📈 Trend Following",
        short_score=85,
        long_score=90
    )
    
    # بروزرسانی بازدهی
    print("\n📊 بروزرسانی قیمت‌ها:")
    tracker.update_returns("GOOGL", 142.0)  # +1.43%
    tracker.update_returns("NVDA", 125.0)   # +4.17%
    
    # بستن سیگنال
    print("\n🔒 بستن سیگنال:")
    for signal_id in list(tracker.signals.keys())[:1]:
        tracker.close_signal(signal_id, 145.0, "Take Profit")
    
    # گزارش عملکرد
    print("\n" + tracker.generate_performance_report())

if __name__ == "__main__":
    demo()
