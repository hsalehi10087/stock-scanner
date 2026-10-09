#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحلیل صورتهای مالی شرکت‌های آمریکا و چین
Financial Statement Analysis - Revenue Growth, Margin Expansion, and EPS Forecast
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
        داده‌های نمونه برای شرکت‌ها
        در عمل، این اطلاعات از Finnhub یا SEC EDGAR می‌آید
        """
        companies = [
            {
                'ticker': 'NVDA',
                'name': 'Nvidia',
                'region': '🇺🇸',
                'revenue_current': 60200,  # میلیون دلار
                'revenue_prev_month': 58900,
                'revenue_prev_quarter': 55100,
                'profit_current': 15800,
                'profit_prev_month': 15200,
                'profit_prev_quarter': 13500,
                'margin_current': 26.2,  # درصد
                'margin_prev': 25.8,
                'eps_current': 2.45,
                'eps_forecast': 2.78,
            },
            {
                'ticker': 'MSFT',
                'name': 'Microsoft',
                'region': '🇺🇸',
                'revenue_current': 72400,
                'revenue_prev_month': 71200,
                'revenue_prev_quarter': 68900,
                'profit_current': 19800,
                'profit_prev_month': 19100,
                'profit_prev_quarter': 18200,
                'margin_current': 27.3,
                'margin_prev': 26.8,
                'eps_current': 3.28,
                'eps_forecast': 3.65,
            },
            {
                'ticker': 'AAPL',
                'name': 'Apple',
                'region': '🇺🇸',
                'revenue_current': 89500,
                'revenue_prev_month': 87200,
                'revenue_prev_quarter': 83100,
                'profit_current': 22100,
                'profit_prev_month': 21500,
                'profit_prev_quarter': 20200,
                'margin_current': 24.7,
                'margin_prev': 24.2,
                'eps_current': 1.65,
                'eps_forecast': 1.82,
            },
            {
                'ticker': '600519.SS',
                'name': '贵州茅台 (Moutai)',
                'region': '🇨🇳',
                'revenue_current': 2850,  # میلیارد یوان
                'revenue_prev_month': 2720,
                'revenue_prev_quarter': 2580,
                'profit_current': 1120,
                'profit_prev_month': 1070,
                'profit_prev_quarter': 985,
                'margin_current': 39.3,
                'margin_prev': 39.3,
                'eps_current': 35.2,
                'eps_forecast': 38.5,
            },
            {
                'ticker': 'TSLA',
                'name': 'Tesla',
                'region': '🇺🇸',
                'revenue_current': 28500,
                'revenue_prev_month': 27800,
                'revenue_prev_quarter': 26200,
                'profit_current': 2850,
                'profit_prev_month': 2620,
                'profit_prev_quarter': 2410,
                'margin_current': 10.0,
                'margin_prev': 9.4,
                'eps_current': 0.85,
                'eps_forecast': 1.05,
            },
            {
                'ticker': 'META',
                'name': 'Meta Platforms',
                'region': '🇺🇸',
                'revenue_current': 42100,
                'revenue_prev_month': 40200,
                'revenue_prev_quarter': 38900,
                'profit_current': 8240,
                'profit_prev_month': 7890,
                'profit_prev_quarter': 7210,
                'margin_current': 19.6,
                'margin_prev': 19.6,
                'eps_current': 2.14,
                'eps_forecast': 2.52,
            },
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
        """تولید گزارش تلگرامی"""
        data = self.generate_sample_data()
        metrics = self.calculate_metrics(data)

        # مرتب‌سازی بر اساس رشد فروش
        metrics_sorted = sorted(metrics, key=lambda x: x['revenue_growth_qoq'], reverse=True)

        blocks = [
            f"📊 <b>تحلیل صورتهای مالی</b> — {self.timestamp}\n"
            "<i>شرکت‌های آمریکا و چین | رشد فروش، حاشیه سود، و برآورد EPS</i>"
        ]

        # جدول خلاصه
        table = "<code>"
        table += "نماد    نام             رشد%MoM رشد%QoQ حاشیه سود سیگنال\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for m in metrics_sorted[:15]:  # Top 15 companies
            ticker = (m['region'] + ' ' + m['ticker']).ljust(12)
            name = m['name'][:15].ljust(15)
            rev_mom = f"{m['revenue_growth_mom']:+5.1f}%".rjust(8)
            rev_qoq = f"{m['revenue_growth_qoq']:+5.1f}%".rjust(8)
            margin = f"{m['margin_current']:5.1f}%".rjust(8)
            signal = m['signal']

            table += f"{ticker}{name}{rev_mom}{rev_qoq}{margin}{signal}\n"

        table += "</code>"
        blocks.append(table)

        # تفصیل بیشتر برای Top 5
        blocks.append("<b>تفصیل Top 5 شرکت رشدکننده</b>")

        for i, m in enumerate(metrics_sorted[:5], 1):
            detail = f"""<b>{i}. {m['region']} {m['name']} ({m['ticker']})</b>
┌─ رشد فروش:
│  • ماه قبل: {m['revenue_growth_mom']:+.1f}%
│  • فصل قبل: {m['revenue_growth_qoq']:+.1f}%
├─ حاشیهٔ سود: {m['margin_current']:.1f}% (تغییر: {m['margin_change']:+.1f}%)
├─ رشد سود:
│  • ماه قبل: {m['profit_growth_mom']:+.1f}%
│  • فصل قبل: {m['profit_growth_qoq']:+.1f}%
└─ EPS: {m['eps_current']:.2f} → {m['eps_forecast']:.2f} ({m['eps_growth']:+.1f}%)
   سیگنال: {m['signal']}
"""
            blocks.append(detail)

        # خلاصه
        us_companies = [m for m in metrics if m['region'] == '🇺🇸']
        cn_companies = [m for m in metrics if m['region'] == '🇨🇳']

        summary = f"""📈 <b>خلاصه</b>
• شرکت‌های آمریکا: {len(us_companies)}
  - میانگین رشد فروش (QoQ): {sum(m['revenue_growth_qoq'] for m in us_companies) / len(us_companies):.1f}%
• شرکت‌های چین: {len(cn_companies)}
  - میانگین رشد فروش (QoQ): {sum(m['revenue_growth_qoq'] for m in cn_companies) / len(cn_companies):.1f}%

⚠️ اطلاعات نمونه است و برای دقت باید از منابع رسمی SEC و Dataroma استفاده کنید.
#تحلیل #صورتهای_مالی #رشد #سودآوری"""

        blocks.append(summary)

        return blocks, []

def run(today=None) -> Tuple[List[str], List, bool]:
    """اجرای تحلیلگر صورتهای مالی"""
    today = today or dt.date.today()
    analyzer = FinancialsAnalyzer()
    blocks, hl = analyzer.generate_report()
    return blocks, hl, True
