#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Real Scraper - دریافت واقعی از codal.ir
Real Data Extraction from Codal
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CogalRealScraper:
    """Scraper واقعی برای دریافت گزارش‌های Codal"""

    BASE_URL = "https://codal.ir"
    SEARCH_URL = f"{BASE_URL}/search/advance"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fa-IR,fa;q=0.9',
            'Referer': self.BASE_URL,
        })

    def search_today_reports(self, num_days: int = 1) -> List[Dict]:
        """
        جستجو برای گزارش‌های دیروز تا امروز
        """
        logger.info(f"🔍 جستجو برای گزارش‌های {num_days} روز آخیر...")

        try:
            # محاسبهٔ تاریخ‌ها
            to_date = datetime.now()
            from_date = to_date - timedelta(days=num_days)

            params = {
                'TracingNo': '',
                'Symbol': '',
                'CompanyName': '',
                'TextSearchPhrase': '',
                'PageNumber': 1,
                'IssuerId': None,
                'FromDate': from_date.strftime('%Y/%m/%d'),
                'ToDate': to_date.strftime('%Y/%m/%d'),
                'SearchOption': 1,
                'CompanyType': None,
                'NoticeType': None,
                'WithoutAttachment': False
            }

            response = self.session.get(self.SEARCH_URL, params=params, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                reports = self._parse_search_results(response.text)
                logger.info(f"✅ یافت شد: {len(reports)} گزارش")
                return reports
            else:
                logger.warning(f"⚠️ خطا: Status {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ خطا در جستجو: {e}")
            return []

    def _parse_search_results(self, html: str) -> List[Dict]:
        """
        Parse کردن جدول نتایج جستجو
        """
        reports = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # جدول نتایج
            table = soup.find('table', class_='table')
            if not table:
                logger.warning("⚠️ جدول نتایج پیدا نشد")
                return []

            rows = table.find_all('tr')[1:]  # Skip header

            for row in rows[:30]:  # Max 30
                try:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        # ستون‌های جدول
                        link_element = cols[2].find('a')
                        if not link_element:
                            continue

                        report_id = link_element.get('href', '').split('/')[-1]

                        report = {
                            'date': cols[0].get_text(strip=True),
                            'symbol': cols[1].get_text(strip=True),
                            'company': cols[2].get_text(strip=True),
                            'report_type': cols[3].get_text(strip=True) if len(cols) > 3 else '',
                            'report_id': report_id,
                            'url': f"{self.BASE_URL}/Reports/Show/{report_id}",
                        }

                        if report['symbol'] and report['company']:
                            reports.append(report)

                except Exception as e:
                    logger.debug(f"⚠️ خطا در parse ردیف: {e}")
                    continue

            return reports

        except Exception as e:
            logger.error(f"❌ خطا در parse: {e}")
            return []

    def extract_financial_data(self, report_id: str, report_url: str) -> Optional[Dict]:
        """
        استخراج داده‌های مالی از صفحهٔ گزارش
        """
        try:
            response = self.session.get(report_url, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # جستجو برای جداول داده‌های مالی
            data = {
                'sales': self._extract_number(response.text, r'فروش.*?[:\s]+([0-9,]+)'),
                'profit': self._extract_number(response.text, r'سود.*?[:\s]+([0-9,]+)'),
                'assets': self._extract_number(response.text, r'دارایی.*?[:\s]+([0-9,]+)'),
                'equity': self._extract_number(response.text, r'سرمایه.*?[:\s]+([0-9,]+)'),
            }

            return data if any(data.values()) else None

        except Exception as e:
            logger.debug(f"⚠️ خطا در استخراج داده: {e}")
            return None

    def _extract_number(self, text: str, pattern: str) -> Optional[float]:
        """
        استخراج عدد از متن
        """
        try:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(',', '')
                return float(num_str)
        except:
            pass
        return None

    def get_company_latest_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        دریافت آخرین گزارش‌های یک شرکت
        """
        logger.info(f"📄 جستجو برای گزارش‌های {symbol}...")

        try:
            params = {
                'Symbol': symbol,
                'PageNumber': 1,
                'SearchOption': 1,
            }

            response = self.session.get(self.SEARCH_URL, params=params, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code == 200:
                reports = self._parse_search_results(response.text)
                return reports[:limit]

            return []

        except Exception as e:
            logger.error(f"❌ خطا: {e}")
            return []


def test_real_scraper():
    """تست Scraper"""
    scraper = CogalRealScraper()

    print("\n" + "="*60)
    print("🧪 تست Codal Real Scraper")
    print("="*60 + "\n")

    # جستجو برای گزارش‌های دیروز و امروز
    reports = scraper.search_today_reports(num_days=1)

    print(f"✅ تعداد گزارش: {len(reports)}\n")

    if reports:
        print("📋 نمونه گزارش‌ها:")
        for i, report in enumerate(reports[:5], 1):
            print(f"{i}. {report.get('symbol')} - {report.get('company')}")
            print(f"   تاریخ: {report.get('date')}")
            print(f"   نوع: {report.get('report_type')}\n")

        # سعی در استخراج داده‌های مالی
        if reports:
            print("💾 تلاش برای استخراج داده‌های مالی از اولین گزارش...")
            first_report = reports[0]
            financial_data = scraper.extract_financial_data(
                first_report['report_id'],
                first_report['url']
            )

            if financial_data:
                print(f"✅ داده استخراج شد:")
                for key, value in financial_data.items():
                    if value:
                        print(f"   {key}: {value:,.0f}")
            else:
                print("⚠️ داده‌ای استخراج نشد")
    else:
        print("⚠️ گزارشی یافت نشد")
        print("\nاحتمالات:")
        print("1. کودال ممکنه آپ‌تاید کرده باشه")
        print("2. نیاز به JavaScript rendering (Selenium/Playwright)")
        print("3. یا Rate limiting")

    print("\n" + "="*60)


if __name__ == "__main__":
    test_real_scraper()
