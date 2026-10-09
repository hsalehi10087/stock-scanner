#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Selenium Scraper - نسخهٔ Browser Automation
دریافت گزارش‌های روزانه از codal.ir با استفاده از Selenium
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
import re
import time
from typing import List, Dict
import json

class CogalSeleniumScraper:
    """
    دریافت گزارش‌های Codal با Browser Automation
    """
    
    def __init__(self, headless=True):
        self.base_url = "https://codal.ir"
        self.headless = headless
        self.driver = None
        self.timeout = 10
        self.today = datetime.now().strftime("%Y-%m-%d")
        
    def _init_driver(self):
        """راه‌اندازی Chrome driver"""
        try:
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            # User-Agent برای جلوگیری از blocking
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self.driver = webdriver.Chrome(options=options)
            print("✅ Chrome driver راه‌اندازی شد")
            return True
        except Exception as e:
            print(f"❌ خطا در راه‌اندازی driver: {e}")
            return False
    
    def search_today_reports(self) -> List[Dict]:
        """
        جستجو برای گزارش‌های امروز
        """
        if not self._init_driver():
            return []
        
        try:
            print(f"📡 دریافت گزارش‌های {self.today} از Codal...")
            
            # صفحهٔ جستجو
            search_url = f"{self.base_url}/search/advance"
            self.driver.get(search_url)
            
            # صبر برای لود شدن صفحه
            time.sleep(3)
            
            # تنظیم فیلتر تاریخ (به تاریخ امروز)
            try:
                date_from = self.driver.find_element(By.ID, "fromDate")
                date_from.clear()
                date_from.send_keys(self.today)
                
                date_to = self.driver.find_element(By.ID, "toDate")
                date_to.clear()
                date_to.send_keys(self.today)
                
                print(f"✓ تاریخ تنظیم شد: {self.today}")
            except:
                print("⚠️ نتوانستم فیلتر تاریخ را تنظیم کنم - ادامه بدون فیلتر")
            
            # کلیک روی دکمهٔ جستجو
            try:
                search_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'جستجو')]")
                search_button.click()
                time.sleep(3)
                print("✓ دکمهٔ جستجو فشار داده شد")
            except:
                pass
            
            # استخراج نتایج
            reports = self._extract_results()
            return reports
            
        except Exception as e:
            print(f"❌ خطا در جستجو: {e}")
            return []
        finally:
            if self.driver:
                self.driver.quit()
    
    def _extract_results(self) -> List[Dict]:
        """استخراج نتایج جستجو"""
        reports = []
        
        try:
            # انتظار برای بارگذاری نتایج
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "report-row"))
            )
            
            # پیدا کردن تمام ردیف‌های گزارش
            rows = self.driver.find_elements(By.CLASS_NAME, "report-row")
            print(f"📊 {len(rows)} گزارش یافت شد")
            
            for row in rows[:20]:  # حداکثر 20 گزارش
                try:
                    # استخراج اطلاعات
                    symbol = row.find_element(By.CLASS_NAME, "symbol").text.strip()
                    company = row.find_element(By.CLASS_NAME, "company-name").text.strip()
                    date = row.find_element(By.CLASS_NAME, "date").text.strip()
                    
                    # دریافت URL گزارش
                    report_link = row.find_element(By.TAG_NAME, "a")
                    report_url = report_link.get_attribute("href")
                    
                    reports.append({
                        'symbol': symbol,
                        'company': company,
                        'date': date,
                        'url': report_url
                    })
                    
                    print(f"  ✓ {symbol} - {company}")
                except Exception as e:
                    continue
            
            return reports
            
        except Exception as e:
            print(f"⚠️ خطا در استخراج نتایج: {e}")
            return reports
    
    def get_report_details(self, report_url: str) -> Dict:
        """
        دریافت جزئیات یک گزارش
        """
        try:
            self.driver.get(report_url)
            time.sleep(2)
            
            # استخراج متن گزارش
            report_text = self.driver.find_element(By.ID, "report-content").text
            
            # استخراج متریک‌ها
            sales = self._extract_sales(report_text)
            profit = self._extract_profit(report_text)
            growth = self._extract_growth(report_text)
            
            return {
                'sales': sales,
                'profit': profit,
                'growth': growth,
                'raw_text': report_text[:500]  # اولین 500 کاراکتر
            }
        except Exception as e:
            print(f"⚠️ خطا در دریافت جزئیات: {e}")
            return {}
    
    def _extract_sales(self, text: str) -> float:
        """استخراج فروش"""
        patterns = [
            r'فروش.*?(\d+(?:,\d+)*)',
            r'درآمد.*?(\d+(?:,\d+)*)',
            r'Sales.*?(\d+(?:,\d+)*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    pass
        return 0.0
    
    def _extract_profit(self, text: str) -> float:
        """استخراج سود"""
        patterns = [
            r'سود خالص.*?(\d+(?:,\d+)*)',
            r'Net Income.*?(\d+(?:,\d+)*)',
            r'profit.*?(\d+(?:,\d+)*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    pass
        return 0.0
    
    def _extract_growth(self, text: str) -> float:
        """استخراج رشد"""
        patterns = [
            r'رشد.*?(\d+(?:\.\d+)?)\s*%',
            r'growth.*?(\d+(?:\.\d+)?)\s*%',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        return 0.0

# تست
if __name__ == "__main__":
    scraper = CogalSeleniumScraper(headless=True)
    print("🚀 شروع Selenium Scraper...")
    
    # جستجو برای گزارش‌های امروز
    reports = scraper.search_today_reports()
    
    if reports:
        print(f"\n✅ {len(reports)} گزارش دریافت شد:")
        for report in reports[:3]:
            print(f"\n  نماد: {report['symbol']}")
            print(f"  شرکت: {report['company']}")
            print(f"  تاریخ: {report['date']}")
    else:
        print("⚠️ هیچ گزارشی یافت نشد")
