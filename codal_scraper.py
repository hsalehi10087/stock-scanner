#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal.ir Scraper - دریافت گزارش‌های روزانه شرکت‌های بورسی
Daily Codal Reports - Sales, Profit, Growth Analysis
"""

import requests
from typing import List, Dict
from datetime import datetime, timedelta
import re

class CogalScraper:
    """Scraper برای دریافت گزارش‌های Codal"""
    
    def __init__(self):
        self.base_url = "https://codal.ir"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
    
    def search_today_reports(self) -> List[Dict]:
        """
        جستجو برای گزارش‌های امروز
        
        روش: API Search یا Scraping
        """
        print("📡 جستجو برای گزارش‌های امروز در Codal...")
        
        # ابتدا سعی برای API endpoint
        try:
            # سعی 1: JSON API
            url = f"{self.base_url}/api/search"
            params = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'count': 100
            }
            
            response = self.session.get(url, params=params, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ API دریافت شد: {len(data)} گزارش")
                    return data
                except:
                    pass
        except Exception as e:
            print(f"⚠️ API fail: {e}")
        
        # سعی 2: Search Form endpoint
        try:
            url = f"{self.base_url}/search/advance"
            data = {
                'TracingNo': '',
                'Symbol': '',
                'CompanyName': '',
                'TextSearchPhrase': '',
                'PageNumber': 1,
                'IssuerId': None,
                'FromDate': datetime.now().strftime('%Y/%m/%d'),
                'ToDate': datetime.now().strftime('%Y/%m/%d'),
                'SearchOption': 1,
                'CompanyType': None,
                'NoticeType': None,
                'WithoutAttachment': False
            }
            
            response = self.session.post(url, data=data, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                # Parse HTML
                print(f"✅ Search Form دریافت شد")
                return self._parse_search_results(response.text)
        except Exception as e:
            print(f"⚠️ Search form fail: {e}")
        
        print("⚠️ نتوانستم گزارش‌های امروز را دریافت کنم")
        return []
    
    def _parse_search_results(self, html: str) -> List[Dict]:
        """Parse کردن نتایج جستجو از HTML"""
        results = []
        
        # Pattern برای استخراج ردیف‌های جدول
        # این یک نمونه‌ای کلی است
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        
        for row in rows[:50]:  # Max 50
            try:
                # استخراج ستون‌ها
                cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                
                if len(cols) >= 3:
                    # تمیز کردن HTML
                    clean_cols = [re.sub(r'<[^>]+>', '', col).strip() for col in cols]
                    
                    results.append({
                        'symbol': clean_cols[1] if len(clean_cols) > 1 else '',
                        'company': clean_cols[2] if len(clean_cols) > 2 else '',
                        'date': clean_cols[0] if len(clean_cols) > 0 else '',
                    })
            except:
                pass
        
        return results
    
    def get_report_details(self, report_id: str) -> Dict:
        """دریافت جزئیات یک گزارش"""
        try:
            url = f"{self.base_url}/Reports/Show/{report_id}"
            response = self.session.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                # Extract financial data
                data = {
                    'sales': self._extract_sales(response.text),
                    'profit': self._extract_profit(response.text),
                    'growth': self._extract_growth(response.text),
                }
                return data
        except Exception as e:
            print(f"⚠️ جزئیات fail: {e}")
        
        return {}
    
    def _extract_sales(self, html: str) -> Dict:
        """استخراج داده‌های فروش"""
        # Pattern: "فروش" یا "Sales"
        match = re.search(r'فروش[:\s]+([0-9,]+)', html)
        if match:
            return {'value': match.group(1)}
        return {}
    
    def _extract_profit(self, html: str) -> Dict:
        """استخراج داده‌های سود"""
        match = re.search(r'سود[:\s]+([0-9,]+)', html)
        if match:
            return {'value': match.group(1)}
        return {}
    
    def _extract_growth(self, html: str) -> Dict:
        """استخراج داده‌های رشد"""
        match = re.search(r'رشد[:\s]+([0-9.]+)\s*%', html)
        if match:
            return {'percent': float(match.group(1))}
        return {}

def test_scraper():
    """تست کردن scraper"""
    scraper = CogalScraper()
    
    print("\n🧪 تست Codal Scraper\n")
    print("="*50)
    
    # جستجو برای گزارش‌های امروز
    reports = scraper.search_today_reports()
    
    print(f"\n✅ تعداد گزارش: {len(reports)}")
    
    if reports:
        print("\n📋 نمونه گزارش‌ها:")
        for report in reports[:5]:
            print(f"  • {report.get('symbol', 'N/A')} - {report.get('company', 'N/A')}")
    else:
        print("\n⚠️ گزارش‌ای دریافت نشد")
        print("\nراهنما:")
        print("1. Codal ممکنه به روش‌های مختلف کار کند")
        print("2. نیاز به Selenium/Puppeteer برای JS rendering")
        print("3. یا استفاده از proxy service")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    test_scraper()
