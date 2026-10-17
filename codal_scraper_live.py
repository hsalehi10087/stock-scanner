#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper پویا برای codal.ir
دریافت گزارش‌های روزانهٔ شرکت‌ها
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodalLiveScraper:
    """Scraper پویا برای codal.ir"""

    def __init__(self):
        self.base_url = "https://codal.ir"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.timestamp = datetime.now().strftime("%Y-%m-%d")

    def get_latest_reports(self, limit=50):
        """دریافت جدیدترین گزارش‌های codal"""
        try:
            # صفحهٔ اصلی
            url = f"{self.base_url}/Home/Index"
            response = requests.get(url, headers=self.headers, timeout=5)
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.content, 'html.parser')

            reports = []

            # جستجو برای جدول گزارش‌ها
            report_rows = soup.find_all('tr', limit=limit)

            for row in report_rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    try:
                        # استخراج داده‌ها
                        symbol = cols[0].text.strip()
                        company = cols[1].text.strip()
                        report_type = cols[2].text.strip()
                        date = cols[3].text.strip()

                        if symbol and company:
                            reports.append({
                                'symbol': symbol,
                                'company': company,
                                'report_type': report_type,
                                'date': date,
                                'scraped_date': self.timestamp
                            })
                    except Exception as e:
                        logger.warning(f"خطا در پارس ردیف: {e}")
                        continue

            logger.info(f"✅ {len(reports)} گزارش دریافت شد")
            return reports

        except requests.exceptions.ProxyError:
            logger.error("❌ Cloud proxy مسدود است - GitHub Actions سعی کند")
            return []
        except Exception as e:
            logger.error(f"❌ خطا در دریافت: {e}")
            return []



    def run(self):
        """اجرای کامل"""
        logger.info("🚀 شروع scraping codal.ir...")

        reports = self.get_latest_reports()

        if not reports:
            # هرگز داده‌ی ساختگی نمی‌سازیم: GitHub (آمریکا) به کدال دسترسی ندارد.
            # گزارش واقعی کدال با iran/codal_daily.py روی کامپیوتر داخل ایران ساخته می‌شود.
            logger.warning("⚠️ گزارشی دریافت نشد - داده‌ی جایگزین ساخته نمی‌شود")
        return reports


def main():
    scraper = CodalLiveScraper()
    reports = scraper.run()

    # نمایش نتایج
    for report in reports[:5]:
        print(f"📄 {report['symbol']} - {report['company']}")
        print(f"   نوع: {report['report_type']} | تاریخ: {report['date']}")
        print()

    # ذخیره به JSON
    with open('codal_latest_reports.json', 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ {len(reports)} گزارش ذخیره شد")


if __name__ == "__main__":
    main()
