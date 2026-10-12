#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحلیل گزارش‌های codal
فیلتر: رشد فروش + سود بالا
ذخیرهٔ تاریخچه
"""

import json
import csv
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodalAnalyzer:
    """تحلیل و فیلتر گزارش‌های codal"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d")
        self.history_file = "data/codal_history.csv"
        self.ensure_history_file()

    def ensure_history_file(self):
        """اطمینان از وجود فایل تاریخچه"""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'date', 'symbol', 'company', 'report_type',
                    'sales_growth', 'profit_growth', 'profitability',
                    'score'
                ])
                writer.writeheader()

    def parse_percentage(self, value):
        """تبدیل رشته‌ای مثل '+25%' به عدد"""
        if not value:
            return None
        try:
            # حذف درصد و تبدیل به عدد
            value = str(value).replace('%', '').replace('+', '').strip()
            return float(value)
        except:
            return None

    def score_company(self, report):
        """محاسبهٔ امتیاز شرکت"""
        sales = self.parse_percentage(report.get('sales_growth', 0)) or 0
        profit = self.parse_percentage(report.get('profit_growth', 0)) or 0
        profitability = self.parse_percentage(report.get('profitability', 0)) or 0

        # امتیاز: رشد فروش + رشد سود + سودآوری
        score = (sales * 0.3) + (profit * 0.4) + (profitability * 0.3)

        return {
            'sales_growth': sales,
            'profit_growth': profit,
            'profitability': profitability,
            'score': score
        }

    def filter_strong_companies(self, reports, min_sales=10, min_profit=15):
        """فیلتر: فقط شرکت‌های قوی
        - رشد فروش > min_sales%
        - رشد سود > min_profit%
        """
        strong = []

        for report in reports:
            scores = self.score_company(report)

            if (scores['sales_growth'] >= min_sales and
                scores['profit_growth'] >= min_profit):

                report['score'] = scores['score']
                strong.append(report)

        # مرتب‌سازی بر اساس امتیاز
        return sorted(strong, key=lambda x: x.get('score', 0), reverse=True)

    def add_to_history(self, reports):
        """اضافه کردن به تاریخچهٔ روزانه (بدون تکرار)"""
        # موجودہ entries پڑھیں
        existing = set()
        if os.path.exists(self.history_file):
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('date') == self.timestamp:
                        key = f"{row['symbol']}|{row['company']}"
                        existing.add(key)

        # صرف نئے records add کریں
        with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'date', 'symbol', 'company', 'report_type',
                'sales_growth', 'profit_growth', 'profitability',
                'score'
            ])

            added = 0
            for report in reports:
                key = f"{report.get('symbol', '')}|{report.get('company', '')}"
                if key not in existing:
                    writer.writerow({
                        'date': self.timestamp,
                        'symbol': report.get('symbol', ''),
                        'company': report.get('company', ''),
                        'report_type': report.get('report_type', ''),
                        'sales_growth': report.get('sales_growth', ''),
                        'profit_growth': report.get('profit_growth', ''),
                        'profitability': report.get('profitability', ''),
                        'score': report.get('score', '')
                    })
                    existing.add(key)
                    added += 1

            if added > 0:
                logger.info(f"📝 {added} نئے records add ہوئے")
            else:
                logger.info("✅ کوئی نیا record نہیں (پہلے سے موجود ہیں)")

    def get_top_performers(self, reports, limit=10):
        """بهترین‌های امروز"""
        return reports[:limit]

    def run(self):
        """اجرای کامل"""
        logger.info("🔍 تحلیل گزارش‌های codal...")

        # خواندن گزارش‌های خام
        if not os.path.exists('codal_latest_reports.json'):
            logger.error("❌ فایل گزارش‌ها پیدا نشد")
            return []

        with open('codal_latest_reports.json', 'r', encoding='utf-8') as f:
            reports = json.load(f)

        # فیلتر کردن
        strong = self.filter_strong_companies(reports)

        if strong:
            # اضافه کردن به تاریخچه
            self.add_to_history(strong)
            logger.info(f"✅ {len(strong)} شرکت قوی شناسایی شد")
        else:
            logger.info("⚠️ شرکت قوی شناسایی نشد")

        return strong


def main():
    analyzer = CodalAnalyzer()
    strong = analyzer.run()

    # نمایش نتایج
    print("\n📊 شرکت‌های قوی امروز:\n")
    for i, company in enumerate(strong[:10], 1):
        print(f"{i}. {company.get('symbol')} - {company.get('company')}")
        print(f"   📈 فروش: {company.get('sales_growth', 'N/A')} | سود: {company.get('profit_growth', 'N/A')}")
        print(f"   ⭐ امتیاز: {company.get('score', 0):.2f}\n")


if __name__ == "__main__":
    main()
