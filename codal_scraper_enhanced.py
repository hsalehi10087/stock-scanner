#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Codal Scraper - استفادهٔ واقعی از codal.ir
Real Data Extraction with Multiple Methods
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import re
from bs4 import BeautifulSoup
import time

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class CodtalEnhancedScraper:
    """Enhanced Scraper برای codal.ir"""

    BASE_URL = "https://codal.ir"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fa-IR,fa;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def get_today_reports(self, num_days: int = 1) -> List[Dict]:
        """
        دریافت گزارش‌های امروز و دیروز
        Method 1: Search Form Direct
        """
        logger.info(f"🔍 دریافت گزارش‌های {num_days} روز آخیر از codal.ir...")

        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=num_days)

            # روش 1: Direct Search Form
            search_url = f"{self.BASE_URL}/search/advance"

            # تلاش ۱: POST request
            payload = {
                'TracingNo': '',
                'Symbol': '',
                'CompanyName': '',
                'TextSearchPhrase': '',
                'PageNumber': '1',
                'IssuerId': '',
                'FromDate': from_date.strftime('%Y/%m/%d'),
                'ToDate': to_date.strftime('%Y/%m/%d'),
                'SearchOption': '1',
                'CompanyType': '',
                'NoticeType': '',
                'WithoutAttachment': 'false'
            }

            logger.info(f"📤 POST درخواست به {search_url}")
            response = self.session.post(search_url, data=payload, timeout=15, verify=True)

            if response.status_code == 200:
                logger.info(f"✅ پاسخ دریافت شد ({len(response.text)} بایت)")
                reports = self._parse_search_response(response.text)

                if reports:
                    logger.info(f"✅ {len(reports)} گزارش یافت شد")
                    return reports

        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ خطا در اتصال: {str(e)[:60]}")
        except Exception as e:
            logger.error(f"❌ خطا: {str(e)[:100]}")

        return []

    def _parse_search_response(self, html: str) -> List[Dict]:
        """
        Parse کردن HTML جستجو
        """
        reports = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # جستجو برای جدول نتایج
            tables = soup.find_all('table', class_='table')

            if not tables:
                logger.warning("⚠️ جدول پیدا نشد")
                return []

            table = tables[0]
            rows = table.find_all('tr')[1:]  # Skip header

            logger.info(f"📋 {len(rows)} ردیف در جدول")

            for i, row in enumerate(rows[:30]):  # Max 30
                try:
                    cols = row.find_all('td')

                    if len(cols) < 3:
                        continue

                    # استخراج لینک
                    link_elem = cols[2].find('a')
                    if not link_elem:
                        continue

                    href = link_elem.get('href', '')
                    report_id = href.split('/')[-1] if '/' in href else ''

                    if not report_id:
                        continue

                    # استخراج متن
                    date_text = cols[0].get_text(strip=True)
                    symbol = cols[1].get_text(strip=True)
                    company = cols[2].get_text(strip=True)
                    report_type = cols[3].get_text(strip=True) if len(cols) > 3 else ''

                    if symbol and company:
                        report = {
                            'date': date_text,
                            'symbol': symbol,
                            'company': company,
                            'report_type': report_type,
                            'report_id': report_id,
                            'url': f"{self.BASE_URL}/Reports/Show/{report_id}",
                        }

                        reports.append(report)
                        logger.info(f"   ✓ {symbol} - {company}")

                except Exception as e:
                    logger.debug(f"   ⚠️ خطا در ردیف {i}: {str(e)[:40]}")
                    continue

            logger.info(f"✅ کل: {len(reports)} گزارش معتبر")
            return reports

        except Exception as e:
            logger.error(f"❌ خطا در parsing: {e}")
            return []

    def get_report_details(self, report_id: str, report_url: str) -> Dict:
        """
        دریافت جزئیات گزارش از صفحهٔ گزارش
        """
        try:
            logger.info(f"📄 دریافت جزئیات گزارش {report_id}...")

            response = self.session.get(report_url, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                logger.warning(f"⚠️ Status {response.status_code}")
                return {}

            soup = BeautifulSoup(response.text, 'html.parser')

            # جستجو برای جدول‌های داده‌های مالی
            # روش ۱: جستجو برای کلیدواژه‌های فارسی
            text = response.text

            data = {}

            # فروش
            sales_match = re.search(r'فروش[^0-9]*([0-9,]+)', text)
            if sales_match:
                data['sales'] = int(sales_match.group(1).replace(',', ''))

            # سود
            profit_match = re.search(r'سود[^0-9]*([0-9,]+)', text)
            if profit_match:
                data['profit'] = int(profit_match.group(1).replace(',', ''))

            # دارایی
            assets_match = re.search(r'دارایی[^0-9]*([0-9,]+)', text)
            if assets_match:
                data['assets'] = int(assets_match.group(1).replace(',', ''))

            # سرمایه
            equity_match = re.search(r'سرمایه|حقوق[^0-9]*([0-9,]+)', text)
            if equity_match:
                data['equity'] = int(equity_match.group(1).replace(',', ''))

            if data:
                logger.info(f"✅ داده استخراج شد: {list(data.keys())}")
            else:
                logger.warning("⚠️ داده‌ای استخراج نشد")

            return data

        except Exception as e:
            logger.error(f"❌ خطا در دریافت جزئیات: {e}")
            return {}

    def get_symbol_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        دریافت گزارش‌های یک نماد خاص
        """
        logger.info(f"🔍 جستجو برای گزارش‌های {symbol}...")

        try:
            search_url = f"{self.BASE_URL}/search/advance"

            payload = {
                'TracingNo': '',
                'Symbol': symbol,
                'CompanyName': '',
                'TextSearchPhrase': '',
                'PageNumber': '1',
                'IssuerId': '',
                'FromDate': '',
                'ToDate': '',
                'SearchOption': '1',
                'WithoutAttachment': 'false'
            }

            response = self.session.post(search_url, data=payload, timeout=15)

            if response.status_code == 200:
                reports = self._parse_search_response(response.text)
                logger.info(f"✅ {len(reports)} گزارش برای {symbol}")
                return reports[:limit]

            return []

        except Exception as e:
            logger.error(f"❌ خطا: {e}")
            return []


def test_enhanced_scraper():
    """تست Enhanced Scraper"""
    scraper = CodtalEnhancedScraper()

    print("\n" + "="*70)
    print("🧪 تست Enhanced Codal Scraper")
    print("="*70 + "\n")

    # تست 1: دریافت گزارش‌های امروز
    print("📌 تست 1: گزارش‌های امروز و دیروز\n")
    reports = scraper.get_today_reports(num_days=1)

    if reports:
        print(f"✅ یافت شد: {len(reports)} گزارش\n")

        # نمایش نمونه
        for i, report in enumerate(reports[:5], 1):
            print(f"{i}. {report['symbol']} - {report['company']}")
            print(f"   نوع: {report['report_type']}")
            print(f"   تاریخ: {report['date']}\n")

        # تست 2: دریافت جزئیات
        print("📌 تست 2: استخراج جزئیات گزارش\n")
        if reports:
            first = reports[0]
            details = scraper.get_report_details(first['report_id'], first['url'])

            if details:
                print(f"✅ جزئیات {first['symbol']}:")
                for key, value in details.items():
                    print(f"   {key}: {value:,}")
            else:
                print("⚠️ جزئیات استخراج نشد")
    else:
        print("⚠️ گزارشی یافت نشد")
        print("\n📌 امکانات:")
        print("1. اگر cloud: proxy block می‌کند - GitHub Actions کار می‌کند")
        print("2. اگر local: باید internet دسترسی داشته باشید")
        print("3. codal.ir ممکن است rate limiting داشته باشد")

    print("\n" + "="*70)


if __name__ == "__main__":
    test_enhanced_scraper()
