#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش تحلیلی سهام - صورتهای مالی + تکنیکال
Short-term & Long-term Growth Potential
"""

from financials_analyzer import FinancialsAnalyzer
from datetime import datetime
from typing import List, Dict, Tuple

class InvestmentReport:
    """گزارش تحلیلی سهام‌های پیشنهادی"""
    
    def __init__(self):
        self.analyzer = FinancialsAnalyzer()
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    def analyze_all_stocks(self) -> List[Dict]:
        """تحلیل تمام سهام‌ها"""
        data = self.analyzer.generate_sample_data()
        metrics = self.analyzer.calculate_metrics(data)
        
        analyzed = []
        for m in metrics:
            # امتیاز کوتاه‌مدت (Technical + Momentum)
            short_term_score = self._calculate_short_term(m)
            
            # امتیاز بلند‌مدت (Fundamental)
            long_term_score = self._calculate_long_term(m)
            
            # امتیاز کلی
            overall_score = (short_term_score + long_term_score) / 2
            
            analyzed.append({
                'symbol': m['ticker'],
                'name': m['name'],
                'region': m['region'],
                'revenue_growth': m['revenue_growth_qoq'],
                'profit_margin': m['margin_current'],
                'eps_current': m['eps_current'],
                'eps_forecast': m['eps_forecast'],
                'signal': m['signal'],
                'short_term': short_term_score,
                'long_term': long_term_score,
                'overall': overall_score,
            })
        
        # مرتب‌سازی بر اساس امتیاز کلی
        return sorted(analyzed, key=lambda x: x['overall'], reverse=True)
    
    def _calculate_short_term(self, m: Dict) -> float:
        """
        امتیاز کوتاه‌مدت (3-6 ماه)
        
        عوامل:
        - سیگنال (خرید قوی/خرید/نگاه/فروش)
        - رشد فروش
        - شکاف EPS (EPS Forecast - Current)
        """
        score = 0
        
        # سیگنال
        signal_map = {
            '🟢 خرید قوی': 40,
            '🟡 خرید': 30,
            '⚪ نگاه': 15,
            '🔴 فروش': 5,
        }
        score += signal_map.get(m['signal'], 15)
        
        # رشد فروش (QoQ) - بیشتر رشد = بیشتر momentum
        if m['revenue_growth_qoq'] > 10:
            score += 30
        elif m['revenue_growth_qoq'] > 5:
            score += 20
        elif m['revenue_growth_qoq'] > 0:
            score += 10
        
        # EPS Forecast > Current (نشان‌دهندهٔ بهبود)
        eps_gap = m['eps_forecast'] - m['eps_current']
        if eps_gap > 10:
            score += 20
        elif eps_gap > 5:
            score += 10
        
        return min(score, 100)
    
    def _calculate_long_term(self, m: Dict) -> float:
        """
        امتیاز بلند‌مدت (1-3 سال)
        
        عوامل:
        - حاشیهٔ سود (Profitability)
        - رشد فروش (Sustainability)
        - توان رشد (EPS Growth)
        """
        score = 0
        
        # حاشیهٔ سود
        if m['margin_current'] > 30:
            score += 35
        elif m['margin_current'] > 20:
            score += 25
        elif m['margin_current'] > 10:
            score += 15
        
        # رشد فروش (QoQ)
        if m['revenue_growth_qoq'] > 10:
            score += 35
        elif m['revenue_growth_qoq'] > 5:
            score += 25
        elif m['revenue_growth_qoq'] > 0:
            score += 15
        
        # EPS Forecast (توان درآمدزایی)
        if m['eps_forecast'] > 30:
            score += 30
        elif m['eps_forecast'] > 15:
            score += 20
        elif m['eps_forecast'] > 5:
            score += 10
        
        return min(score, 100)
    
    def generate_report(self, analyzed: List[Dict]) -> List[str]:
        """تولید گزارش برای Telegram"""
        blocks = []
        
        blocks.append(f"📈 <b>گزارش تحلیلی سهام‌های پیشنهادی</b> — {self.timestamp}\n"
                     f"<i>بر اساس صورتهای مالی + تکنیکال (Short-term & Long-term)</i>")
        
        # خلاصه
        top_5 = analyzed[:5]
        avg_short = sum(a['short_term'] for a in analyzed) / len(analyzed)
        avg_long = sum(a['long_term'] for a in analyzed) / len(analyzed)
        
        blocks.append(f"""<b>📊 خلاصه تحلیل</b>
<b>کل سهام‌های تحلیل‌شده:</b> {len(analyzed)}
<b>میانگین امتیاز کوتاه‌مدت:</b> {avg_short:.1f}/100
<b>میانگین امتیاز بلند‌مدت:</b> {avg_long:.1f}/100
<b>شرکت‌های برتر:</b> {', '.join([f"{a['symbol']}" for a in top_5])}""")
        
        # جدول اصلی
        blocks.append("<b>🏆 جدول سهام‌های پیشنهادی</b>")
        
        table = "<code>"
        table += "<b>سهام  نام           کوتاه‌مدت بلند‌مدت کلی</b>\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for stock in analyzed[:20]:  # Top 20
            symbol = stock['symbol'].ljust(6)
            name = stock['name'][:10].ljust(12)
            short = f"{stock['short_term']:.0f}".rjust(6)
            long = f"{stock['long_term']:.0f}".rjust(7)
            overall = f"{stock['overall']:.0f}".rjust(5)
            
            # رنگ بندی
            if stock['overall'] >= 75:
                indicator = "🟢"
            elif stock['overall'] >= 60:
                indicator = "🟡"
            else:
                indicator = "⚪"
            
            table += f"{indicator} {symbol}{name}{short}{long}{overall}\n"
        
        table += "</code>"
        blocks.append(table)
        
        # تفصیل Top 10
        blocks.append("<b>🔍 تفصیل سهام‌های برتر</b>")
        
        for i, stock in enumerate(analyzed[:10], 1):
            # رشد + سودآوری
            growth_indicator = "🔥" if stock['revenue_growth'] > 10 else "📈" if stock['revenue_growth'] > 5 else "📊"
            profit_indicator = "💰" if stock['profit_margin'] > 25 else "💵" if stock['profit_margin'] > 15 else "💸"
            
            blocks.append(f"""
<b>{i}. {stock['symbol']} - {stock['name']}</b> {stock['region']}
{growth_indicator} <b>رشد فروش:</b> {stock['revenue_growth']:+.1f}%
{profit_indicator} <b>حاشیهٔ سود:</b> {stock['profit_margin']:.1f}%
📊 <b>EPS:</b> {stock['eps_current']:.1f} → {stock['eps_forecast']:.1f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  <b>کوتاه‌مدت (3-6 ماه):</b> {stock['short_term']:.0f}/100
📅 <b>بلند‌مدت (1-3 سال):</b> {stock['long_term']:.0f}/100
🎯 <b>امتیاز کلی:</b> {stock['overall']:.0f}/100 {self._get_rating(stock['overall'])}""")
        
        # راهنما
        blocks.append("""
<b>📌 راهنمای امتیازات</b>
<b>کوتاه‌مدت (3-6 ماه):</b>
  • سیگنال تکنیکال (خرید/فروش)
  • رشد تند فروش (Momentum)
  • بهبود EPS (Short-term earnings)

<b>بلند‌مدت (1-3 سال):</b>
  • سودآوری (Profitability)
  • رشد پایدار (Sustainability)
  • توان درآمدزایی (EPS Growth)

<b>تفسیر:</b>
🟢 = قوی (75+)  |  🟡 = متوسط (60-75)  |  ⚪ = ضعیف (60-)""")
        
        blocks.append("""
⚠️ <b>توجه:</b> این گزارش برای اطلاع‌رسانی است و توصیهٔ سرمایه‌گذاری نیست.
#تحلیل #سهام #صورتهای_مالی #تکنیکال #سرمایه‌گذاری""")
        
        return blocks
    
    def _get_rating(self, score: float) -> str:
        """تبدیل امتیاز به رتبه"""
        if score >= 90:
            return "⭐⭐⭐⭐⭐"
        elif score >= 80:
            return "⭐⭐⭐⭐"
        elif score >= 70:
            return "⭐⭐⭐"
        elif score >= 60:
            return "⭐⭐"
        else:
            return "⭐"

def run_investment_report():
    """اجرای گزارش"""
    report = InvestmentReport()
    analyzed = report.analyze_all_stocks()
    blocks = report.generate_report(analyzed)
    return blocks

if __name__ == "__main__":
    blocks = run_investment_report()
    print("\n".join(blocks))
