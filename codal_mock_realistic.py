#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Mock Realistic Data
واقع‌گرایانه‌ترین نمونه‌داده برای تست
Realistic Sample Data for Testing
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict

class CogalMockRealistic:
    """Mock data که واقع‌گرایانه است"""

    # شرکت‌های بورسی واقعی
    COMPANIES = [
        {'symbol': 'شاه', 'name': 'پتروشیمی شاهندژ', 'industry': 'پتروشیمی'},
        {'symbol': 'بیمه', 'name': 'بیمهٔ ایران', 'industry': 'بیمه'},
        {'symbol': 'خودرو', 'name': 'ایران خودرو', 'industry': 'خودروسازی'},
        {'symbol': 'فولاد', 'name': 'فولاد خوزستان', 'industry': 'فولاد'},
        {'symbol': 'کاسپین', 'name': 'شرکت کاسپین', 'industry': 'انرژی'},
        {'symbol': 'ملی', 'name': 'بانک ملی', 'industry': 'بانکداری'},
        {'symbol': 'رفاه', 'name': 'بانک رفاه', 'industry': 'بانکداری'},
        {'symbol': 'صادرات', 'name': 'بانک صادرات', 'industry': 'بانکداری'},
        {'symbol': 'اختیار', 'name': 'گاز ایران', 'industry': 'انرژی'},
        {'symbol': 'خاور', 'name': 'شرکت خاور', 'industry': 'خودروسازی'},
    ]

    REPORT_TYPES = [
        'گزارش مالی سالانه',
        'گزارش فصلی',
        'گزارش ماهانه',
        'اطلاعیهٔ متفرقه',
        'گزارش درخواست‌شده',
    ]

    def __init__(self):
        self.seed_date = datetime.now()

    def generate_realistic_reports(self, count: int = 5) -> List[Dict]:
        """
        تولید گزارش‌های واقع‌گرایانه
        """
        reports = []

        for i in range(count):
            # انتخاب تصادفی
            company = random.choice(self.COMPANIES)
            report_type = random.choice(self.REPORT_TYPES)

            # تاریخ (امروز یا دیروز)
            days_back = random.randint(0, 2)
            report_date = (self.seed_date - timedelta(days=days_back))

            # داده‌های مالی واقع‌گرایانه (مختلف بر اساس صنعت)
            industry = company['industry']

            if industry == 'بانکداری':
                sales_base = random.randint(500_000, 2_000_000)
                profit_ratio = random.uniform(0.08, 0.25)
            elif industry == 'انرژی':
                sales_base = random.randint(300_000, 1_500_000)
                profit_ratio = random.uniform(0.12, 0.35)
            elif industry == 'خودروسازی':
                sales_base = random.randint(400_000, 3_000_000)
                profit_ratio = random.uniform(0.05, 0.15)
            else:  # پتروشیمی، فولاد، بیمه
                sales_base = random.randint(200_000, 1_200_000)
                profit_ratio = random.uniform(0.10, 0.30)

            # محاسبهٔ فروش و سود
            sales = int(sales_base * random.uniform(0.8, 1.3))
            profit = int(sales * profit_ratio)
            assets = int(sales * random.uniform(1.5, 4.0))
            equity = int(assets * random.uniform(0.4, 0.8))

            report = {
                'date': report_date.strftime('%Y/%m/%d'),
                'symbol': company['symbol'],
                'company': company['name'],
                'industry': company['industry'],
                'report_type': report_type,
                'report_id': f"REP{i + 1000}",
                'url': f"https://codal.ir/Reports/Show/REP{i + 1000}",
                'sales': sales,
                'profit': profit,
                'assets': assets,
                'equity': equity,
                'debt': assets - equity,
            }

            reports.append(report)

        # مرتب‌سازی بر اساس تاریخ (جدید‌تر اول)
        reports.sort(key=lambda x: x['date'], reverse=True)

        return reports

    def get_financial_metrics(self, report: Dict) -> Dict:
        """
        محاسبهٔ متریک‌های مالی
        """
        sales = report['sales']
        profit = report['profit']
        assets = report['assets']
        equity = report['equity']
        debt = report['debt']

        return {
            'profit_margin': (profit / sales * 100) if sales > 0 else 0,
            'roa': (profit / assets * 100) if assets > 0 else 0,
            'roe': (profit / equity * 100) if equity > 0 else 0,
            'debt_ratio': (debt / assets * 100) if assets > 0 else 0,
            'debt_to_equity': (debt / equity) if equity > 0 else 0,
        }

    def score_report(self, report: Dict) -> int:
        """
        امتیاز دادن به گزارش
        """
        metrics = self.get_financial_metrics(report)
        score = 0

        # نوع گزارش
        report_type = report['report_type'].lower()
        if 'سالانه' in report_type:
            score += 40
        elif 'فصل' in report_type:
            score += 30
        elif 'ماهانه' in report_type:
            score += 20
        else:
            score += 10

        # معیارهای مالی
        profit_margin = metrics['profit_margin']
        if profit_margin > 20:
            score += 25
        elif profit_margin > 10:
            score += 20
        elif profit_margin > 0:
            score += 15

        roe = metrics['roe']
        if roe > 20:
            score += 20
        elif roe > 10:
            score += 15
        elif roe > 0:
            score += 10

        debt_ratio = metrics['debt_ratio']
        if debt_ratio < 30:
            score += 15
        elif debt_ratio < 50:
            score += 10
        elif debt_ratio < 70:
            score += 5

        return score


def generate_mock_data(count: int = 8) -> List[Dict]:
    """
    تولید نمونه‌داده واقع‌گرایانه
    """
    generator = CogalMockRealistic()
    reports = generator.generate_realistic_reports(count)

    # اضافه کردن امتیاز
    for report in reports:
        report['score'] = generator.score_report(report)
        report['metrics'] = generator.get_financial_metrics(report)

    # مرتب‌سازی بر اساس امتیاز
    reports.sort(key=lambda x: x['score'], reverse=True)

    return reports


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 تست Mock Realistic Data")
    print("="*60 + "\n")

    reports = generate_mock_data(6)

    print(f"✅ تعداد گزارش: {len(reports)}\n")

    for i, report in enumerate(reports, 1):
        metrics = report['metrics']
        print(f"{i}. {report['symbol']} - {report['company']}")
        print(f"   نوع: {report['report_type']}")
        print(f"   تاریخ: {report['date']}")
        print(f"   فروش: {report['sales']:,.0f}")
        print(f"   سود: {report['profit']:,.0f}")
        print(f"   حاشیهٔ سود: {metrics['profit_margin']:.1f}%")
        print(f"   ROE: {metrics['roe']:.1f}%")
        print(f"   نسبت بدهی: {metrics['debt_ratio']:.1f}%")
        print(f"   امتیاز: {report['score']}/100")
        print()

    print("="*60)
