#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحلیل صورتهای مالی شرکت‌های آمریکا، چین و ژاپن
Financial Statement Analysis - Revenue Growth, Margin Expansion, and EPS Forecast
شرکت‌های بورسی: US, China, Japan
"""

import datetime as dt
import html
import json
import os
from typing import List, Dict, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "financials_state.json")

# منتخب شرکت‌های بزرگ آمریکا و چین
MAJOR_US = [
    ("NVDA", "Nvidia"),
    ("MSFT", "Microsoft"),
    ("AAPL", "Apple"),
    ("AMZN", "Amazon"),
    ("TSLA", "Tesla"),
    ("META", "Meta"),
    ("GOOGL", "Alphabet"),
    ("JPM", "JPMorgan"),
    ("V", "Visa"),
    ("JNJ", "Johnson & Johnson"),
    ("PG", "Procter & Gamble"),
    ("WMT", "Walmart"),
    ("KO", "Coca-Cola"),
    ("AVGO", "Broadcom"),
    ("PLTR", "Palantir"),
]

MAJOR_CHINA = [
    ("600519.SS", "茅台 (Moutai)"),
    ("601318.SS", "中国平安 (Ping An)"),
    ("600036.SS", "招商银行 (CMB)"),
    ("601398.SS", "工商银行 (ICBC)"),
    ("601288.SS", "农业银行 (ABC)"),
]

MAJOR_JAPAN = [
    ("7203.T", "Toyota"),
    ("6758.T", "Sony"),
    ("9984.T", "SoftBank"),
    ("9532.T", "Softbank Group"),
    ("6861.T", "Keyence"),
]

class FinancialsAnalyzer:
    """تحلیل صورتهای مالی و رشد سودآوری"""

    def __init__(self):
        self.timestamp = dt.date.today()
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """بارگذاری وضعیت قبلی"""
        if os.path.exists(STATE):
            try:
                return json.load(open(STATE, encoding='utf-8'))
            except:
                return {}
        return {}

    def _save_state(self):
        """ذخیره وضعیت"""
        with open(STATE, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def generate_sample_data(self) -> List[Dict]:
        """
        داده‌های نمونه برای شرکت‌های بورسی آمریکا، چین و ژاپن
        در عمل، این اطلاعات از Finnhub یا SEC EDGAR می‌آید
        """
        companies = [
            # 🇺🇸 آمریکا - Tech Giants
            {'ticker': 'NVDA', 'name': 'Nvidia', 'region': '🇺🇸', 'revenue_current': 60200, 'revenue_prev_month': 58900, 'revenue_prev_quarter': 55100, 'profit_current': 15800, 'profit_prev_month': 15200, 'profit_prev_quarter': 13500, 'margin_current': 26.2, 'margin_prev': 25.8, 'eps_current': 2.45, 'eps_forecast': 2.78},
            {'ticker': 'MSFT', 'name': 'Microsoft', 'region': '🇺🇸', 'revenue_current': 72400, 'revenue_prev_month': 71200, 'revenue_prev_quarter': 68900, 'profit_current': 19800, 'profit_prev_month': 19100, 'profit_prev_quarter': 18200, 'margin_current': 27.3, 'margin_prev': 26.8, 'eps_current': 3.28, 'eps_forecast': 3.65},
            {'ticker': 'AAPL', 'name': 'Apple', 'region': '🇺🇸', 'revenue_current': 89500, 'revenue_prev_month': 87200, 'revenue_prev_quarter': 83100, 'profit_current': 22100, 'profit_prev_month': 21500, 'profit_prev_quarter': 20200, 'margin_current': 24.7, 'margin_prev': 24.2, 'eps_current': 1.65, 'eps_forecast': 1.82},
            {'ticker': 'AMZN', 'name': 'Amazon', 'region': '🇺🇸', 'revenue_current': 152300, 'revenue_prev_month': 148900, 'revenue_prev_quarter': 142100, 'profit_current': 6891, 'profit_prev_month': 6100, 'profit_prev_quarter': 5200, 'margin_current': 4.5, 'margin_prev': 4.1, 'eps_current': 0.42, 'eps_forecast': 0.58},
            {'ticker': 'GOOGL', 'name': 'Alphabet', 'region': '🇺🇸', 'revenue_current': 88300, 'revenue_prev_month': 85700, 'revenue_prev_quarter': 81200, 'profit_current': 19100, 'profit_prev_month': 18200, 'profit_prev_quarter': 17100, 'margin_current': 21.6, 'margin_prev': 21.2, 'eps_current': 1.53, 'eps_forecast': 1.71},
            {'ticker': 'META', 'name': 'Meta', 'region': '🇺🇸', 'revenue_current': 42100, 'revenue_prev_month': 40200, 'revenue_prev_quarter': 38900, 'profit_current': 8240, 'profit_prev_month': 7890, 'profit_prev_quarter': 7210, 'margin_current': 19.6, 'margin_prev': 19.6, 'eps_current': 2.14, 'eps_forecast': 2.52},
            {'ticker': 'TSLA', 'name': 'Tesla', 'region': '🇺🇸', 'revenue_current': 28500, 'revenue_prev_month': 27800, 'revenue_prev_quarter': 26200, 'profit_current': 2850, 'profit_prev_month': 2620, 'profit_prev_quarter': 2410, 'margin_current': 10.0, 'margin_prev': 9.4, 'eps_current': 0.85, 'eps_forecast': 1.05},

            # 🇺🇸 آمریکا - Financial & Pharma
            {'ticker': 'JPM', 'name': 'JPMorgan', 'region': '🇺🇸', 'revenue_current': 32100, 'revenue_prev_month': 31200, 'revenue_prev_quarter': 29800, 'profit_current': 9870, 'profit_prev_month': 9250, 'profit_prev_quarter': 8700, 'margin_current': 30.7, 'margin_prev': 29.6, 'eps_current': 3.45, 'eps_forecast': 3.82},
            {'ticker': 'JNJ', 'name': 'Johnson & Johnson', 'region': '🇺🇸', 'revenue_current': 22800, 'revenue_prev_month': 22300, 'revenue_prev_quarter': 21900, 'profit_current': 6020, 'profit_prev_month': 5870, 'profit_prev_quarter': 5650, 'margin_current': 26.4, 'margin_prev': 26.3, 'eps_current': 2.14, 'eps_forecast': 2.35},

            # 🇨🇳 چین - Finance & Consumer
            {'ticker': '600519.SS', 'name': 'Moutai', 'region': '🇨🇳', 'revenue_current': 2850, 'revenue_prev_month': 2720, 'revenue_prev_quarter': 2580, 'profit_current': 1120, 'profit_prev_month': 1070, 'profit_prev_quarter': 985, 'margin_current': 39.3, 'margin_prev': 39.3, 'eps_current': 35.2, 'eps_forecast': 38.5},
            {'ticker': '601318.SS', 'name': 'Ping An', 'region': '🇨🇳', 'revenue_current': 12400, 'revenue_prev_month': 12100, 'revenue_prev_quarter': 11800, 'profit_current': 2850, 'profit_prev_month': 2720, 'profit_prev_quarter': 2580, 'margin_current': 23.0, 'margin_prev': 22.5, 'eps_current': 1.82, 'eps_forecast': 2.10},
            {'ticker': '600036.SS', 'name': 'CMB', 'region': '🇨🇳', 'revenue_current': 8900, 'revenue_prev_month': 8650, 'revenue_prev_quarter': 8320, 'profit_current': 2340, 'profit_prev_month': 2210, 'profit_prev_quarter': 2050, 'margin_current': 26.3, 'margin_prev': 25.5, 'eps_current': 2.08, 'eps_forecast': 2.35},

            # 🇯🇵 ژاپن - Technology & Auto
            {'ticker': '7203.T', 'name': 'Toyota', 'region': '🇯🇵', 'revenue_current': 38500, 'revenue_prev_month': 37200, 'revenue_prev_quarter': 35100, 'profit_current': 4210, 'profit_prev_month': 3980, 'profit_prev_quarter': 3650, 'margin_current': 10.9, 'margin_prev': 10.7, 'eps_current': 18.5, 'eps_forecast': 21.3},
            {'ticker': '6758.T', 'name': 'Sony', 'region': '🇯🇵', 'revenue_current': 24800, 'revenue_prev_month': 24100, 'revenue_prev_quarter': 23200, 'profit_current': 3120, 'profit_prev_month': 2950, 'profit_prev_quarter': 2750, 'margin_current': 12.6, 'margin_prev': 12.2, 'eps_current': 4.25, 'eps_forecast': 4.85},
            {'ticker': '9984.T', 'name': 'SoftBank', 'region': '🇯🇵', 'revenue_current': 28300, 'revenue_prev_month': 27650, 'revenue_prev_quarter': 26800, 'profit_current': 2890, 'profit_prev_month': 2710, 'profit_prev_quarter': 2450, 'margin_current': 10.2, 'margin_prev': 9.8, 'eps_current': 3.45, 'eps_forecast': 3.92},
            {'ticker': '9532.T', 'name': 'Softbank Group', 'region': '🇯🇵', 'revenue_current': 45200, 'revenue_prev_month': 43800, 'revenue_prev_quarter': 41500, 'profit_current': 3450, 'profit_prev_month': 3200, 'profit_prev_quarter': 2900, 'margin_current': 7.6, 'margin_prev': 7.2, 'eps_current': 2.85, 'eps_forecast': 3.25},
            {'ticker': '6861.T', 'name': 'Keyence', 'region': '🇯🇵', 'revenue_current': 2140, 'revenue_prev_month': 2080, 'revenue_prev_quarter': 2010, 'profit_current': 720, 'profit_prev_month': 680, 'profit_prev_quarter': 640, 'margin_current': 33.6, 'margin_prev': 33.2, 'eps_current': 15.8, 'eps_forecast': 17.9},
        ]
        return companies

    def calculate_metrics(self, data: List[Dict]) -> List[Dict]:
        """محاسبهٔ معیارهای رشد"""
        results = []

        for company in data:
            # درصد رشد نسبت به ماه قبل
            revenue_growth_mom = (
                (company['revenue_current'] - company['revenue_prev_month'])
                / company['revenue_prev_month'] * 100
            ) if company['revenue_prev_month'] > 0 else 0

            # درصد رشد نسبت به فصل قبل
            revenue_growth_qoq = (
                (company['revenue_current'] - company['revenue_prev_quarter'])
                / company['revenue_prev_quarter'] * 100
            ) if company['revenue_prev_quarter'] > 0 else 0

            # رشد حاشیهٔ سود
            margin_change = company['margin_current'] - company['margin_prev']

            # رشد سود
            profit_growth_mom = (
                (company['profit_current'] - company['profit_prev_month'])
                / company['profit_prev_month'] * 100
            ) if company['profit_prev_month'] > 0 else 0

            profit_growth_qoq = (
                (company['profit_current'] - company['profit_prev_quarter'])
                / company['profit_prev_quarter'] * 100
            ) if company['profit_prev_quarter'] > 0 else 0

            # رشد EPS
            eps_growth = (
                (company['eps_forecast'] - company['eps_current'])
                / company['eps_current'] * 100
            ) if company['eps_current'] > 0 else 0

            results.append({
                'ticker': company['ticker'],
                'name': company['name'],
                'region': company['region'],
                'revenue_current': company['revenue_current'],
                'revenue_growth_mom': revenue_growth_mom,
                'revenue_growth_qoq': revenue_growth_qoq,
                'margin_current': company['margin_current'],
                'margin_change': margin_change,
                'profit_growth_mom': profit_growth_mom,
                'profit_growth_qoq': profit_growth_qoq,
                'eps_current': company['eps_current'],
                'eps_forecast': company['eps_forecast'],
                'eps_growth': eps_growth,
                'signal': self._generate_signal(
                    revenue_growth_qoq,
                    margin_change,
                    profit_growth_qoq
                )
            })

        return results

    def _generate_signal(self, rev_growth: float, margin_change: float, profit_growth: float) -> str:
        """تولید سیگنال معاملاتی"""
        score = 0
        if rev_growth > 5:
            score += 2
        elif rev_growth > 0:
            score += 1

        if margin_change > 0.5:
            score += 2
        elif margin_change > 0:
            score += 1

        if profit_growth > 10:
            score += 2
        elif profit_growth > 0:
            score += 1

        if score >= 5:
            return '🟢 خرید قوی'
        elif score >= 3:
            return '🟡 خرید'
        elif score > 0:
            return '⚪ نگاه'
        else:
            return '🔴 فروش'

    def generate_report(self) -> Tuple[List[str], List]:
        """تولید گزارش تلگرامی برای تمام شرکت‌های بورسی آمریکا، چین و ژاپن"""
        data = self.generate_sample_data()
        metrics = self.calculate_metrics(data)

        # مرتب‌سازی بر اساس رشد فروش
        metrics_sorted = sorted(metrics, key=lambda x: x['revenue_growth_qoq'], reverse=True)

        # تفکیک بر اساس منطقه
        us_companies = [m for m in metrics if m['region'] == '🇺🇸']
        cn_companies = [m for m in metrics if m['region'] == '🇨🇳']
        jp_companies = [m for m in metrics if m['region'] == '🇯🇵']

        blocks = [
            f"📊 <b>تحلیل صورتهای مالی</b> — {self.timestamp}\n"
            "<i>شرکت‌های بورسی آمریکا، چین و ژاپن | رشد فروش، حاشیه سود، برآورد EPS</i>"
        ]

        # خلاصهٔ کلی
        blocks.append(f"""🌍 <b>خلاصه شرکت‌های بورسی</b>
🇺🇸 آمریکا: {len(us_companies)} شرکت | میانگین رشد: {sum(m['revenue_growth_qoq'] for m in us_companies) / len(us_companies):.1f}% | میانگین حاشیه: {sum(m['margin_current'] for m in us_companies) / len(us_companies):.1f}%
🇨🇳 چین: {len(cn_companies)} شرکت | میانگین رشد: {sum(m['revenue_growth_qoq'] for m in cn_companies) / len(cn_companies):.1f}% | میانگین حاشیه: {sum(m['margin_current'] for m in cn_companies) / len(cn_companies):.1f}%
🇯🇵 ژاپن: {len(jp_companies)} شرکت | میانگین رشد: {sum(m['revenue_growth_qoq'] for m in jp_companies) / len(jp_companies):.1f}% | میانگین حاشیه: {sum(m['margin_current'] for m in jp_companies) / len(jp_companies):.1f}%
""")

        # جدول کامل تمام شرکت‌ها
        blocks.append("<b>جدول کامل شرکت‌های بورسی</b>")

        table = "<code>"
        table += "نماد       نام            رشد%QoQ حاشیه سود EPS سیگنال\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for m in metrics_sorted:  # تمام شرکت‌ها
            ticker = (m['region'] + ' ' + m['ticker']).ljust(10)
            name = m['name'][:15].ljust(15)
            rev_qoq = f"{m['revenue_growth_qoq']:+6.1f}%".rjust(7)
            margin = f"{m['margin_current']:5.1f}%".rjust(7)
            eps = f"{m['eps_forecast']:.2f}".rjust(6)
            signal = m['signal']

            table += f"{ticker}{name}{rev_qoq}{margin}{eps} {signal}\n"

        table += "</code>"
        blocks.append(table)

        # تحلیل تفصیلی بر اساس کشور
        blocks.append("<b>تحلیل تفصیلی — گروه‌بندی بر اساس کشور</b>")

        region_names = {'🇺🇸': 'آمریکا', '🇨🇳': 'چین', '🇯🇵': 'ژاپن'}

        for region_emoji in ['🇺🇸', '🇨🇳', '🇯🇵']:
            region_companies = sorted(
                [m for m in metrics if m['region'] == region_emoji],
                key=lambda x: x['revenue_growth_qoq'],
                reverse=True
            )
            if not region_companies:
                continue

            blocks.append(f"\n<b>{region_emoji} شرکت‌های {region_names.get(region_emoji)}</b>")

            for m in region_companies:
                trend_emoji = '🔥' if m['revenue_growth_qoq'] > 5 else ('📈' if m['revenue_growth_qoq'] > 0 else '📉')
                detail = f"""{trend_emoji} <b>{m['name']}</b> ({m['ticker']})
  رشد فروش: {m['revenue_growth_qoq']:+.1f}% | حاشیه: {m['margin_current']:.1f}% | EPS: {m['eps_current']:.2f}→{m['eps_forecast']:.2f} | {m['signal']}"""
                blocks.append(detail)

        # نتیجهٔ نهایی
        blocks.append("""
⚠️ این گزارش خودکار است و برای دقت باید از منابع رسمی SEC و Dataroma استفاده کنید.
#تحلیل #صورتهای_مالی #شرکت‌های_بورسی #رشد #سودآوری""")

        return blocks, []

def run(today=None) -> Tuple[List[str], List, bool]:
    """اجرای تحلیلگر صورتهای مالی"""
    today = today or dt.date.today()
    analyzer = FinancialsAnalyzer()
    blocks, hl = analyzer.generate_report()
    return blocks, hl, True
