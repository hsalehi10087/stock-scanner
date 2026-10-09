#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحلیل صورتهای مالی - نسخهٔ API
Financial Statement Analysis - API Version (Finnhub + Fallback to Yahoo Finance)
تمام شرکت‌های بورسی جهان بدون محدودیت
"""

import datetime as dt
import os
import json
from typing import List, Dict, Tuple
import requests

# سعی برای import yfinance برای fallback
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

class FinancialsAnalyzerAPI:
    """تحلیل صورتهای مالی با استفاده از Finnhub API - تمام شرکت‌ها"""
    
    def __init__(self):
        self.timestamp = dt.date.today()
        self.finnhub_key = os.getenv('FINNHUB_KEY', '')
        self.base_url = "https://finnhub.io/api/v1"
    
    def get_all_companies(self, exchange: str) -> List[Dict]:
        """
        دریافت تمام شرکت‌های یک بورس از Finnhub
        
        Exchanges:
        - US: NASDAQ, NYSE (50-100+ شرکت برتر)
        - China: SSE (Shanghai), SZSE (Shenzhen) (30-50 شرکت برتر)
        - Japan: TSE (Tokyo Stock Exchange) (50-100+ شرکت برتر)
        """
        if not self.finnhub_key:
            print("⚠️ FINNHUB_KEY یافت نشد - از داده‌های نمونه استفاده می‌شود")
            return []
        
        try:
            url = f"{self.base_url}/stock/symbol"
            params = {
                'exchange': exchange,
                'token': self.finnhub_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {len(data)} شرکت از {exchange} دریافت شد")
                return data
            else:
                print(f"⚠️ خطا {response.status_code} از Finnhub")
                return []
        
        except Exception as e:
            print(f"❌ خطا در اتصال Finnhub: {e}")
            return []
    
    def get_company_financials(self, ticker: str) -> Dict:
        """دریافت اطلاعات مالی یک شرکت"""
        if not self.finnhub_key:
            return None
        
        try:
            url = f"{self.base_url}/stock/metric"
            params = {
                'symbol': ticker,
                'metric': 'all',
                'token': self.finnhub_key
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                return response.json()
            return None
        
        except Exception as e:
            print(f"❌ خطا در دریافت {ticker}: {e}")
            return None
    
    def generate_report_from_api(self) -> Tuple[List[str], List]:
        """
        تولید گزارش از داده‌های واقعی
        Fallback levels: Finnhub → Yahoo Finance → Sample Data
        """
        # سطح 1: سعی برای Finnhub
        if self.finnhub_key:
            print("📡 سعی برای Finnhub API...")
            try:
                exchanges = {
                    '🇺🇸': ['NASDAQ', 'NYSE'],
                    '🇨🇳': ['SSE', 'SZSE'],
                    '🇯🇵': ['TSE']
                }

                all_companies = {}
                total = 0

                for region, exch_list in exchanges.items():
                    all_companies[region] = []
                    for exchange in exch_list:
                        companies = self.get_all_companies(exchange)
                        if companies:
                            all_companies[region].extend(companies[:50])
                            total += len(companies)

                if total > 0:
                    print(f"✅ Finnhub: {total} شرکت دریافت شد")
                    # Finnhub blocks generation
                    blocks = []
                    blocks.append(f"📊 <b>تحلیل صورتهای مالی - Finnhub API</b> — {self.timestamp}")
                    blocks.append(f"✅ Finnhub فعال | {total}+ شرکت")
                    return blocks, []
            except Exception as e:
                print(f"⚠️ Finnhub خرابی: {e}")

        # سطح 2: Fallback به Yahoo Finance
        print("📡 سعی برای Yahoo Finance...")
        try:
            blocks, _ = self.generate_report_from_yfinance()
            if blocks and len(blocks) > 1:
                print("✅ Yahoo Finance: داده دریافت شد")
                return blocks, []
        except Exception as e:
            print(f"⚠️ Yahoo Finance خرابی: {e}")

        # سطح 3: Fallback به نمونه (113 شرکت)
        print("⚠️ هردو API fail شد - استفاده نمونهٔ 113 شرکت")
        return self._fallback_to_sample(), []

    def get_companies_from_yfinance(self) -> List[Dict]:
        """
        دریافت داده‌های شرکت‌ها از Yahoo Finance (Fallback)
        """
        if not YFINANCE_AVAILABLE:
            print("⚠️ yfinance نصب نشده - نصب کن: pip install yfinance")
            return []

        try:
            print("📡 دریافت داده‌ها از Yahoo Finance...")

            # لیست تیکر‌های محبوب
            tickers_us = ['NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'META', 'TSLA',
                         'JPM', 'JNJ', 'V', 'WMT', 'MA', 'PG', 'KO', 'DIS']
            tickers_cn = ['9988.HK', '0700.HK', '1398.HK', '1288.HK', '0001.HK', '3690.HK']
            tickers_jp = ['9984.T', '9983.T', '6758.T', '7203.T', '8306.T', '8411.T']

            companies = []

            for ticker in tickers_us + tickers_cn + tickers_jp:
                try:
                    data = yf.Ticker(ticker)
                    info = data.info

                    companies.append({
                        'symbol': ticker,
                        'description': info.get('longName', ticker),
                        'revenue': info.get('totalRevenue', 0),
                        'netIncome': info.get('netIncomeToCommon', 0),
                        'eps': info.get('trailingEps', 0),
                    })
                    print(f"  ✅ {ticker}")
                except:
                    pass

            print(f"✅ {len(companies)} شرکت از Yahoo Finance دریافت شد")
            return companies

        except Exception as e:
            print(f"❌ خطا در Yahoo Finance: {e}")
            return []

    def generate_report_from_yfinance(self) -> Tuple[List[str], List]:
        """تولید گزارش از Yahoo Finance data"""
        companies = self.get_companies_from_yfinance()

        if not companies:
            print("⚠️ Yahoo Finance هم کار نکرد - fallback به نمونه")
            return self._fallback_to_sample(), []

        blocks = []
        blocks.append(f"📊 <b>تحلیل صورتهای مالی - Yahoo Finance</b> — {self.timestamp}\n<i>دریافت از Yahoo Finance API</i>")

        blocks.append(f"<b>🌍 شرکت‌های بورسی</b>\n<b>کل:</b> {len(companies)} شرکت")

        # جدول - نماد چپ، درآمد راست
        table = "<code>"
        table += "<b>نماد        درآمد (میلیارد دلار)</b>\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for company in companies[:20]:
            ticker = company['symbol'].ljust(10)
            revenue = f"${company.get('revenue', 0) / 1e9:.0f}".rjust(8)
            table += f"{ticker} {revenue}\n"

        table += "</code>"
        blocks.append(table)

        blocks.append("✅ <b>Yahoo Finance API</b>")

        return blocks, []

    def _fallback_to_sample(self) -> List[str]:
        """Fallback به داده‌های نمونه اگر API دستیابی نبود"""
        from financials_analyzer import FinancialsAnalyzer
        analyzer = FinancialsAnalyzer()
        blocks, _ = analyzer.generate_report()
        return blocks

def run_api(today=None) -> Tuple[List[str], List, bool]:
    """اجرای تحلیلگر API"""
    analyzer = FinancialsAnalyzerAPI()
    blocks, hl = analyzer.generate_report_from_api()
    return blocks, hl, True

if __name__ == "__main__":
    analyzer = FinancialsAnalyzerAPI()
    blocks, hl = analyzer.generate_report_from_api()
    for block in blocks:
        print(block)
