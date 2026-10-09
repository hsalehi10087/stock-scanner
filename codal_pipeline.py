#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Full Pipeline
جستجو → تحلیل → گزارش → تلگرام
"""

from codal_requests_scraper import CogalRequestsScraper
from codal_daily_report import CogalDailyReport
from typing import List, Dict
import json

class CogalPipeline:
    """
    پایپ‌لاین کامل Codal
    1. دریافت گزارش‌ها (Scraper)
    2. افزودن اطلاعات مالی (با نمونه داده)
    3. تحلیل و امتیاز‌دهی
    4. تولید گزارش برای تلگرام
    """
    
    def __init__(self):
        self.scraper = CogalRequestsScraper()
        self.report_gen = CogalDailyReport()
    
    def run(self) -> List[str]:
        """اجرای کامل پایپ‌لاین"""
        print("=" * 60)
        print("🚀 CODAL DAILY REPORT PIPELINE")
        print("=" * 60)
        
        # مرحلهٔ 1: جستجو
        print("\n[1/3] 📡 جستجو برای گزارش‌های امروز...")
        reports = self.scraper.search_today_reports()
        print(f"✅ {len(reports)} گزارش دریافت شد\n")
        
        # مرحلهٔ 2: تحلیل (استفاده از نمونه داده)
        print("[2/3] 📊 تحلیل شرکت‌ها...")
        analyzed = self.report_gen.analyze()
        print(f"✅ {len(analyzed)} شرکت تحلیل شد\n")
        
        # مرحلهٔ 3: تولید گزارش
        print("[3/3] 📝 تولید گزارش برای تلگرام...")
        telegram_blocks = self.report_gen.generate_telegram_report(analyzed)
        print("✅ گزارش آماده است\n")
        
        return telegram_blocks

def run_pipeline() -> List[str]:
    """اجرای پایپ‌لاین"""
    pipeline = CogalPipeline()
    return pipeline.run()

if __name__ == "__main__":
    blocks = run_pipeline()
    
    print("=" * 60)
    print("📤 OUTPUT FOR TELEGRAM")
    print("=" * 60)
    print("\n".join(blocks))
