#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش تحلیلی سهام - نسخهٔ 2
صورتهای مالی + تکنیکال + دسته‌بندی خرید/فروش + P&L محاسبه
"""

from financials_analyzer import FinancialsAnalyzer
from datetime import datetime
import random

class InvestmentReportV2:
    """گزارش تحلیلی جامع سهام‌های پیشنهادی"""
    
    def __init__(self):
        self.analyzer = FinancialsAnalyzer()
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.jalali_date = self._gregorian_to_jalali()
    
    def _gregorian_to_jalali(self) -> str:
        """تبدیل تاریخ میلادی به شمسی"""
        # ساده‌شده برای مثال
        now = datetime.now()
        # تقریبی: 1402 = 2023
        jalali_year = now.year - 621
        jalali_month = now.month
        jalali_day = now.day
        return f"{jalali_year:04d}-{jalali_month:02d}-{jalali_day:02d}"
    
    def analyze_all_stocks(self) -> list:
        """تحلیل تمام سهام‌ها"""
        data = self.analyzer.generate_sample_data()
        metrics = self.analyzer.calculate_metrics(data)
        
        analyzed = []
        for m in metrics:
            short_term_score = self._calculate_short_term(m)
            long_term_score = self._calculate_long_term(m)
            overall_score = (short_term_score + long_term_score) / 2
            
            # تعیین دسته‌بندی
            category = self._categorize(short_term_score, long_term_score, m['signal'])
            
            # محاسبهٔ P&L فرضی (اگر امروز خریده بودیم)
            pnl = self._simulate_pnl(short_term_score, m['revenue_growth_qoq'])
            
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
                'category': category,
                'pnl_simulation': pnl,
            })
        
        return sorted(analyzed, key=lambda x: x['overall'], reverse=True)
    
    def _calculate_short_term(self, m: dict) -> float:
        """امتیاز کوتاه‌مدت"""
        score = 0
        signal_map = {'🟢 خرید قوی': 40, '🟡 خرید': 30, '⚪ نگاه': 15, '🔴 فروش': 5}
        score += signal_map.get(m['signal'], 15)
        
        if m['revenue_growth_qoq'] > 10:
            score += 30
        elif m['revenue_growth_qoq'] > 5:
            score += 20
        elif m['revenue_growth_qoq'] > 0:
            score += 10
        
        eps_gap = m['eps_forecast'] - m['eps_current']
        if eps_gap > 10:
            score += 20
        elif eps_gap > 5:
            score += 10
        
        return min(score, 100)
    
    def _calculate_long_term(self, m: dict) -> float:
        """امتیاز بلند‌مدت"""
        score = 0
        
        if m['margin_current'] > 30:
            score += 35
        elif m['margin_current'] > 20:
            score += 25
        elif m['margin_current'] > 10:
            score += 15
        
        if m['revenue_growth_qoq'] > 10:
            score += 35
        elif m['revenue_growth_qoq'] > 5:
            score += 25
        elif m['revenue_growth_qoq'] > 0:
            score += 15
        
        if m['eps_forecast'] > 30:
            score += 30
        elif m['eps_forecast'] > 15:
            score += 20
        elif m['eps_forecast'] > 5:
            score += 10
        
        return min(score, 100)
    
    def _categorize(self, short: float, long: float, signal: str) -> str:
        """دسته‌بندی خرید/فروش"""
        # فروش: کوتاه و بلند مدت ضعیف
        if short < 50 and long < 50:
            return "🔴 فروش (هردو مدت)"
        if short < 50:
            return "🔴 فروش کوتاه‌مدت"
        if long < 50:
            return "⚠️ نگاه (بلند‌مدت ضعیف)"
        
        # خرید: دو مدت قوی
        if short >= 80 and long >= 80:
            return "🟢 خرید (هردو مدت)"
        if short >= 80:
            return "🟢 خرید کوتاه‌مدت"
        if long >= 80:
            return "🟢 خرید بلند‌مدت"
        
        return "🟡 نگاه"
    
    def _simulate_pnl(self, short_score: float, growth: float) -> float:
        """محاسبهٔ P&L فرضی (درصد رشد)"""
        # فرمول: (score/100) * growth + random
        base_return = (short_score / 100) * growth
        volatility = random.uniform(-2, 2)
        return base_return + volatility
    
    def generate_report(self, analyzed: list) -> list:
        """تولید گزارش"""
        blocks = []
        
        # عنوان با تاریخ
        blocks.append(f"📈 <b>گزارش تحلیلی سهام‌های پیشنهادی</b>\n"
                     f"<b>میلادی:</b> {self.timestamp} | <b>شمسی:</b> {self.jalali_date}\n"
                     f"<i>تحلیل صورتهای مالی + تکنیکال</i>")
        
        # خلاصه
        buy_short = len([a for a in analyzed if 'خرید کوتاه' in a['category']])
        buy_long = len([a for a in analyzed if 'خرید بلند' in a['category']])
        sell_short = len([a for a in analyzed if 'فروش کوتاه' in a['category']])
        
        blocks.append(f"""<b>📊 خلاصه</b>
<b>کل سهام:</b> {len(analyzed)} | <b>خرید کوتاه:</b> {buy_short} | <b>خرید بلند:</b> {buy_long} | <b>فروش:</b> {sell_short}""")
        
        # جدول دسته‌بندی‌شده
        blocks.append("<b>🎯 جدول دسته‌بندی شده</b>")
        
        # دسته‌های مختلف
        categories = {
            "🟢 خرید (هردو مدت)": [a for a in analyzed if a['category'] == "🟢 خرید (هردو مدت)"],
            "🟢 خرید کوتاه‌مدت": [a for a in analyzed if a['category'] == "🟢 خرید کوتاه‌مدت"],
            "🟢 خرید بلند‌مدت": [a for a in analyzed if a['category'] == "🟢 خرید بلند‌مدت"],
            "🟡 نگاه": [a for a in analyzed if a['category'] == "🟡 نگاه"],
            "⚠️ نگاه (بلند‌مدت ضعیف)": [a for a in analyzed if a['category'] == "⚠️ نگاه (بلند‌مدت ضعیف)"],
            "🔴 فروش کوتاه‌مدت": [a for a in analyzed if a['category'] == "🔴 فروش کوتاه‌مدت"],
            "🔴 فروش (هردو مدت)": [a for a in analyzed if a['category'] == "🔴 فروش (هردو مدت)"],
        }
        
        for category_name, stocks in categories.items():
            if not stocks:
                continue
            
            blocks.append(f"\n<b>{category_name}</b> ({len(stocks)} سهام)")
            
            table = "<code>"
            table += "<b>نماد    رشد فروش  حاشیهٔ سود  P&L    کوتاه‌مدت  بلند‌مدت</b>\n"
            table += "        (سالانه%)    (%)      (فرضی%)  (0-100)   (0-100)\n"
            table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            for stock in stocks[:8]:  # حداکثر 8 در هر دسته
                symbol = stock['symbol'].ljust(8)
                growth = f"{stock['revenue_growth']:+.0f}%".rjust(8)
                margin = f"{stock['profit_margin']:.0f}%".rjust(10)
                pnl = f"{stock['pnl_simulation']:+.1f}%".rjust(8)
                short = f"{stock['short_term']:.0f}".rjust(9)
                long = f"{stock['long_term']:.0f}".rjust(10)

                table += f"{symbol}{growth}{margin}{pnl}{short}{long}\n"
            
            table += "</code>"
            blocks.append(table)
        
        # راهنما
        blocks.append("""<b>📌 توضیح ستون‌ها</b>
<b>رشد%:</b> رشد فروش سالانه
<b>حاشیه:</b> حاشیهٔ سود خالص
<b>P&L:</b> سود/زیان فرضی اگر امروز خریده بودیم
<b>کوتاه:</b> امتیاز کوتاه‌مدت (3-6 ماه)
<b>بلند:</b> امتیاز بلند‌مدت (1-3 سال)

⚠️ گزارش برای اطلاع‌رسانی است و توصیهٔ سرمایه‌گذاری نیست.
#سهام #تحلیل #خرید_فروش""")
        
        return blocks

def run():
    """اجرای گزارش"""
    report = InvestmentReportV2()
    analyzed = report.analyze_all_stocks()
    blocks = report.generate_report(analyzed)
    return blocks

if __name__ == "__main__":
    blocks = run()
    print("\n".join(blocks))
