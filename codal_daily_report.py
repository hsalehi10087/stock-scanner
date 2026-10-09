#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Daily Report - نسخهٔ نمونه‌داده
Sample Data Version - Quick and Easy
"""

from typing import List, Dict
from datetime import datetime
import random

class CogalDailyReport:
    """تولید گزارش روزانهٔ Codal"""
    
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.reports = self._get_sample_data()
    
    def _get_sample_data(self) -> List[Dict]:
        """نمونه‌داده شرکت‌های Codal"""
        return [
            {
                'symbol': 'شاه',
                'company': 'پتروشیمی شاهندژ',
                'industry': 'پتروشیمی',
                'sales_current': 45000,
                'sales_prev_month': 42000,
                'sales_prev_year': 35000,
                'profit_current': 8200,
                'profit_prev_month': 7800,
                'profit_prev_year': 6500,
                'assets': 120000,
                'debt': 35000,
            },
            {
                'symbol': 'بیمه',
                'company': 'بیمهٔ ایران',
                'industry': 'بیمه',
                'sales_current': 125000,
                'sales_prev_month': 118000,
                'sales_prev_year': 110000,
                'profit_current': 18500,
                'profit_prev_month': 16200,
                'profit_prev_year': 15800,
                'assets': 850000,
                'debt': 150000,
            },
            {
                'symbol': 'فولاد',
                'company': 'فولاد خوزستان',
                'industry': 'فولاد',
                'sales_current': 89000,
                'sales_prev_month': 86500,
                'sales_prev_year': 82000,
                'profit_current': 9100,
                'profit_prev_month': 8500,
                'profit_prev_year': 7900,
                'assets': 450000,
                'debt': 120000,
            },
            {
                'symbol': 'خودرو',
                'company': 'ایران خودرو',
                'industry': 'خودروسازی',
                'sales_current': 156000,
                'sales_prev_month': 145000,
                'sales_prev_year': 132000,
                'profit_current': 12400,
                'profit_prev_month': 10800,
                'profit_prev_year': 9500,
                'assets': 780000,
                'debt': 280000,
            },
            {
                'symbol': 'کاسپین',
                'company': 'شرکت کاسپین',
                'industry': 'انرژی',
                'sales_current': 72000,
                'sales_prev_month': 68000,
                'sales_prev_year': 62000,
                'profit_current': 6500,
                'profit_prev_month': 5800,
                'profit_prev_year': 5200,
                'assets': 320000,
                'debt': 95000,
            },
        ]
    
    def analyze(self) -> List[Dict]:
        """تحلیل تمام داده‌ها"""
        analyzed = []
        
        for report in self.reports:
            # محاسبهٔ متریک‌ها
            sales_growth_monthly = ((report['sales_current'] - report['sales_prev_month']) / report['sales_prev_month'] * 100)
            sales_growth_yearly = ((report['sales_current'] - report['sales_prev_year']) / report['sales_prev_year'] * 100)
            profit_growth_monthly = ((report['profit_current'] - report['profit_prev_month']) / report['profit_prev_month'] * 100)
            profit_growth_yearly = ((report['profit_current'] - report['profit_prev_year']) / report['profit_prev_year'] * 100)
            
            profit_margin = (report['profit_current'] / report['sales_current'] * 100)
            debt_ratio = (report['debt'] / report['assets'] * 100)
            
            # امتیاز‌دهی
            score = 0
            if sales_growth_yearly > 20: score += 40
            elif sales_growth_yearly > 10: score += 30
            elif sales_growth_yearly > 0: score += 20
            
            if profit_margin > 15: score += 30
            elif profit_margin > 10: score += 25
            elif profit_margin > 5: score += 20
            
            if profit_growth_yearly > 30: score += 30
            elif profit_growth_yearly > 15: score += 25
            elif profit_growth_yearly > 0: score += 20
            
            analyzed.append({
                **report,
                'sales_growth_m': sales_growth_monthly,
                'sales_growth_y': sales_growth_yearly,
                'profit_growth_m': profit_growth_monthly,
                'profit_growth_y': profit_growth_yearly,
                'profit_margin': profit_margin,
                'debt_ratio': debt_ratio,
                'score': score,
            })
        
        return sorted(analyzed, key=lambda x: x['score'], reverse=True)
    
    def generate_telegram_report(self, analyzed: List[Dict]) -> List[str]:
        """تولید جدول برای تلگرام"""
        blocks = []
        
        # عنوان
        blocks.append(f"📊 <b>گزارش روزانهٔ کودال</b> — {self.timestamp}\n"
                     f"<i>تحلیل شرکت‌های قوی و در حال رشد</i>")
        
        # خلاصه
        blocks.append(f"""
📈 <b>خلاصه امروز</b>
• تعداد شرکت‌های تحلیل‌شده: {len(analyzed)}
• شرکت‌های ستاره‌دار (⭐⭐⭐+): {len([a for a in analyzed if a['score'] >= 70])}
• میانگین امتیاز: {sum(a['score'] for a in analyzed) / len(analyzed):.1f}
• میانگین رشد فروش (سالانه): {sum(a['sales_growth_y'] for a in analyzed) / len(analyzed):+.1f}%
""")
        
        # جدول اصلی
        blocks.append("<b>🏆 جدول شرکت‌های برتر</b>")
        
        table = "<code>"
        table += "نماد    نام              فروش% سود%  حاشیه% امتیاز\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for i, report in enumerate(analyzed, 1):
            emoji = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f'{i}.'
            symbol = (report['symbol']).ljust(6)
            name = (report['company'][:12]).ljust(15)
            sales_y = f"{report['sales_growth_y']:+.0f}%".rjust(6)
            profit_y = f"{report['profit_growth_y']:+.0f}%".rjust(6)
            margin = f"{report['profit_margin']:.1f}%".rjust(8)
            score = f"{report['score']:.0f}".rjust(6)
            
            table += f"{symbol}{name}{sales_y}{profit_y}{margin}{score}\n"
        
        table += "</code>"
        blocks.append(table)
        
        # تفصیل Top 5
        blocks.append("<b>📋 تفصیل شرکت‌های برتر</b>")
        
        for i, report in enumerate(analyzed[:5], 1):
            rating = '⭐⭐⭐⭐⭐' if report['score'] >= 90 else '⭐⭐⭐⭐' if report['score'] >= 75 else '⭐⭐⭐'
            
            blocks.append(f"""
<b>{i}. {report['symbol']} - {report['company']}</b>
┌─ فروش:
│  • ماه آخر: {report['sales_current']:,.0f} (رشد: {report['sales_growth_m']:+.1f}%)
│  • سال آخر: {report['sales_prev_year']:,.0f} (رشد: {report['sales_growth_y']:+.1f}%)
├─ سود:
│  • سود خالص: {report['profit_current']:,.0f} (حاشیه: {report['profit_margin']:.1f}%)
│  • رشد سالانه: {report['profit_growth_y']:+.1f}%
├─ سلامت مالی:
│  • نسبت بدهی: {report['debt_ratio']:.1f}%
│  • داراییها: {report['assets']:,.0f}
└─ امتیاز: {report['score']:.0f}/100 {rating}
""")
        
        # توصیهٔ نهایی
        blocks.append("""
🎯 <b>توصیهٔ خریدی</b>
• شرکت‌های Top 3 قابل توجه هستند
• رشد فروش + سود مثبت = سیگنال خوب
• بدهی کم = امنیت بالاتر

⚠️ این گزارش صرفاً اطلاع‌رسانی است.
#کودال #تحلیل_مالی #گزارش_روزانه""")
        
        return blocks

# تست
if __name__ == "__main__":
    report = CogalDailyReport()
    analyzed = report.analyze()
    blocks = report.generate_telegram_report(analyzed)
    
    print("\n".join(blocks))
