#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Daily Analyzer - تحلیل گزارش‌های روزانه
شرکت‌های قوی با رشد فروش و سود بالا
"""

from typing import List, Dict, Tuple
from datetime import datetime
import json

class CogalAnalyzer:
    """تحلیل گزارش‌های Codal برای انتخاب شرکت‌های قوی"""
    
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    def analyze_reports(self, reports: List[Dict]) -> List[Dict]:
        """تحلیل گزارش‌ها و رتبه‌بندی شرکت‌ها"""
        analyzed = []
        
        for report in reports:
            score = self._calculate_score(report)
            analyzed.append({
                **report,
                'score': score,
                'rating': self._get_rating(score)
            })
        
        # مرتب کردن بر اساس امتیاز
        return sorted(analyzed, key=lambda x: x['score'], reverse=True)
    
    def _calculate_score(self, report: Dict) -> float:
        """
        محاسبهٔ امتیاز شرکت
        
        فاکتورها:
        - رشد فروش (Sales Growth): +40%
        - سودآوری (Profit Margin): +30%
        - رشد سود (Profit Growth): +30%
        """
        score = 0
        
        # رشد فروش
        sales_growth = report.get('sales_growth', 0)
        if sales_growth > 20:
            score += 40
        elif sales_growth > 10:
            score += 30
        elif sales_growth > 0:
            score += 20
        
        # حاشیهٔ سود
        profit_margin = report.get('profit_margin', 0)
        if profit_margin > 15:
            score += 30
        elif profit_margin > 10:
            score += 25
        elif profit_margin > 5:
            score += 20
        
        # رشد سود
        profit_growth = report.get('profit_growth', 0)
        if profit_growth > 30:
            score += 30
        elif profit_growth > 15:
            score += 25
        elif profit_growth > 0:
            score += 20
        
        return score
    
    def _get_rating(self, score: float) -> str:
        """تبدیل امتیاز به رتبه"""
        if score >= 90:
            return '⭐⭐⭐⭐⭐ (فوق‌العاده)'
        elif score >= 75:
            return '⭐⭐⭐⭐ (بسیار خوب)'
        elif score >= 60:
            return '⭐⭐⭐ (خوب)'
        elif score >= 40:
            return '⭐⭐ (متوسط)'
        else:
            return '⭐ (ضعیف)'
    
    def generate_daily_report(self, analyzed: List[Dict]) -> List[str]:
        """تولید گزارش روزانه برای تلگرام"""
        blocks = []
        
        blocks.append(f"📊 <b>گزارش روزانهٔ Codal</b> — {self.timestamp}\n"
                     f"<i>تحلیل شرکت‌های قوی و در حال رشد</i>")
        
        # خلاصه
        blocks.append(f"""
📈 <b>خلاصه</b>
• تعداد شرکت‌های تحلیل‌شده: {len(analyzed)}
• شرکت‌های ستاره‌دار (⭐⭐⭐+): {len([a for a in analyzed if a['score'] >= 60])}
• میانگین امتیاز: {sum(a['score'] for a in analyzed) / len(analyzed):.1f}
""")
        
        # جدول Top 10
        blocks.append("<b>جدول شرکت‌های برتر</b>")
        
        table = "<code>"
        table += "نماد     نام              فروش% سود% امتیاز رتبه\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for report in analyzed[:10]:
            symbol = (report.get('symbol', 'N/A')).ljust(8)
            name = (report.get('company', '')[:12]).ljust(15)
            sales_g = f"{report.get('sales_growth', 0):+.0f}%".rjust(6)
            profit_g = f"{report.get('profit_growth', 0):+.0f}%".rjust(6)
            score = f"{report['score']:.0f}".rjust(6)
            rating_emoji = '🟢' if report['score'] >= 60 else '🟡' if report['score'] >= 40 else '🔴'
            
            table += f"{symbol}{name}{sales_g}{profit_g}{score} {rating_emoji}\n"
        
        table += "</code>"
        blocks.append(table)
        
        # توصیه‌های Top 3
        blocks.append("<b>توصیهٔ خریدی</b>")
        
        for i, report in enumerate(analyzed[:3], 1):
            blocks.append(f"""
{i}. <b>{report.get('symbol')} - {report.get('company')}</b>
   رشد فروش: {report.get('sales_growth', 0):+.1f}%
   رشد سود: {report.get('profit_growth', 0):+.1f}%
   حاشیهٔ سود: {report.get('profit_margin', 0):.1f}%
   {report['rating']}
""")
        
        blocks.append("""
⚠️ این گزارش صرفاً برای اطلاع‌رسانی است و توصیهٔ سرمایه‌گذاری نیست.
#گزارش_روزانه #کودال #تحلیل_مالی""")
        
        return blocks

# نمونهٔ استفاده
if __name__ == "__main__":
    # نمونهٔ داده
    sample_reports = [
        {
            'symbol': 'شاه',
            'company': 'شاه',
            'sales_growth': 25.5,
            'profit_margin': 18.2,
            'profit_growth': 35.8
        },
        {
            'symbol': 'بیمه',
            'company': 'بیمهٔ ایران',
            'sales_growth': 12.3,
            'profit_margin': 14.5,
            'profit_growth': 18.2
        },
        {
            'symbol': 'فولاد',
            'company': 'فولاد',
            'sales_growth': 8.5,
            'profit_margin': 10.2,
            'profit_growth': 5.3
        },
    ]
    
    analyzer = CogalAnalyzer()
    analyzed = analyzer.analyze_reports(sample_reports)
    blocks = analyzer.generate_daily_report(analyzed)
    
    print("\n".join(blocks))
