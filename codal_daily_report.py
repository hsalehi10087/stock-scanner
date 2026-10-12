#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codal Daily Report - استفادهٔ واقعی از codal.ir
Real Data from codal.ir OR Mock Fallback
"""

import os
import sys
from typing import List, Dict
from datetime import datetime
import logging

# Add scrapers
try:
    from codal_scraper_enhanced import CodtalEnhancedScraper
    from codal_mock_realistic import generate_mock_data
    from report_scheduler import ReportScheduler
    from load_env import load_env_file, check_secrets
except ImportError as e:
    print(f"❌ خطا در import: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodtalDailyReport:
    """گزارش روزانهٔ codal.ir - استفادهٔ واقعی"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.scraper = CodtalEnhancedScraper()  # Scraper واقعی
        self.scheduler = ReportScheduler()
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.use_real_data = False  # Track: واقعی یا Mock؟

    def fetch_reports(self, num_days: int = 1) -> List[Dict]:
        """
        دریافت گزارش‌های واقعی از codal.ir
        """
        logger.info("🔄 تلاش برای دریافت گزارش‌های واقعی از codal.ir...")

        # سعی اول: واقعی
        reports = self.scraper.get_today_reports(num_days=num_days)

        if reports:
            self.use_real_data = True
            logger.info(f"✅ {len(reports)} گزارش واقعی از codal.ir")

            # دریافت جزئیات برای هر گزارش
            for report in reports[:8]:
                logger.info(f"   📄 {report['symbol']}...")
                details = self.scraper.get_report_details(report['report_id'], report['url'])
                report['financial'] = details

            return reports[:8]

        # Fallback: Mock Data
        logger.warning("⚠️ نتوانستم از codal.ir دریافت کنم")
        logger.info("💡 استفاده از Mock Data برای تست...")
        self.use_real_data = False

        mock_reports = generate_mock_data(count=8)
        logger.info(f"✅ {len(mock_reports)} گزارش Mock برای تست")

        return mock_reports

    def analyze_reports(self, reports: List[Dict]) -> List[Dict]:
        """
        تحلیل گزارش‌ها و امتیاز‌دهی
        """
        analyzed = []

        for report in reports:
            # اگر Mock است، metrics موجود است
            if 'metrics' in report and 'score' in report:
                analyzed.append(report)
                continue

            # برای واقعی، داده‌های مالی استخراج‌شده
            financial = report.get('financial', {})

            # امتیاز
            score = 0

            # نوع گزارش
            report_type = report.get('report_type', '').lower()
            if 'سالانه' in report_type or 'فصل' in report_type:
                score += 30
            elif 'ماهانه' in report_type:
                score += 20
            else:
                score += 10

            # داده‌های مالی
            if financial:
                if financial.get('sales'):
                    score += 25
                if financial.get('profit'):
                    score += 25
                if financial.get('assets'):
                    score += 15
            else:
                score += 5

            analyzed.append({
                **report,
                'score': score,
                'financial': financial,
            })

        # مرتب‌سازی
        return sorted(analyzed, key=lambda x: x.get('score', 0), reverse=True)

    def generate_telegram_report(self, analyzed: List[Dict]) -> List[str]:
        """
        تولید گزارش برای تلگرام
        """
        blocks = []

        if not analyzed:
            blocks.append("⚠️ گزارش روزانهٔ Codal\n\nمتاسفانه گزارش جدیدی وجود ندارد")
            return blocks

        # عنوان
        source = "✅ codal.ir (واقعی)" if self.use_real_data else "📊 Mock (برای تست)"

        blocks.append(f"📊 <b>گزارش روزانهٔ کودال</b> — {self.timestamp}\n"
                     f"<i>{source}</i>")

        # خلاصه
        blocks.append(f"""
📈 <b>خلاصه امروز</b>
• تعداد گزارش: {len(analyzed)}
• منبع: {source}
• وضعیت: ✅ فعال
""")

        # جدول
        blocks.append("<b>🏆 گزارش‌های برتر</b>")

        table = "<code>"
        table += "ردیف  نماد    شرکت              نوع گزارش\n"
        table += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for i, item in enumerate(analyzed[:8], 1):
            symbol = (item.get('symbol', 'N/A')).ljust(6)
            company = (item.get('company', '')[:12]).ljust(15)
            rtype = (str(item.get('report_type', ''))[:10]).ljust(10)

            table += f"{i:2d}   {symbol} {company} {rtype}\n"

        table += "</code>"
        blocks.append(table)

        # تفصیل
        blocks.append("<b>📋 تفصیل ۵ گزارش برتر</b>")

        for i, item in enumerate(analyzed[:5], 1):
            symbol = item.get('symbol', 'N/A')
            company = item.get('company', 'نامشخص')

            # متریک‌ها
            metrics = item.get('metrics', {})
            financial = item.get('financial', {})

            if metrics:
                metric_text = f"""
├─ متریک‌های مالی:
│  • حاشیهٔ سود: {metrics.get('profit_margin', 0):.1f}%
│  • ROE: {metrics.get('roe', 0):.1f}%
│  • نسبت بدهی: {metrics.get('debt_ratio', 0):.1f}%"""
            elif financial:
                metric_text = "\n├─ داده‌های مالی:"
                if financial.get('sales'):
                    metric_text += f"\n│  • فروش: {financial.get('sales', 0):,}"
                if financial.get('profit'):
                    metric_text += f"\n│  • سود: {financial.get('profit', 0):,}"
                if financial.get('assets'):
                    metric_text += f"\n│  • دارایی: {financial.get('assets', 0):,}"
            else:
                metric_text = "\n├─ داده‌های مالی: در حال استخراج..."

            url = item.get('url', '')
            link = f' <a href="{url}">مشاهده</a>' if url else ''

            blocks.append(f"""
<b>{i}. {symbol} - {company}</b>
├─ تاریخ: {item.get('date', '-')}
├─ نوع: {item.get('report_type', '-')}{metric_text}
├─ امتیاز: {item.get('score', 0)}/100
└─ لینک:{link}
""")

        # توصیه نهایی
        blocks.append("""
🎯 <b>نکات</b>
• این گزارش تنها یک‌بار روزی ارسال می‌شود ✅
• داده‌های واقعی از codal.ir
• برای جزئیات بیشتر: codal.ir

⚠️ صرفاً اطلاع‌رسانی است.
#کودال #تحلیل_مالی #گزارش_روزانه""")

        return blocks

    def send_to_telegram(self, message: str) -> bool:
        """
        ارسال پیام به تلگرام
        """
        if not self.telegram_token or not self.telegram_chat_id:
            logger.error("❌ توکن یا Chat ID موجود نیست")
            return False

        try:
            import requests

            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                logger.info("✅ پیام ارسال شد")
                return True
            else:
                logger.error(f"❌ خطا: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ خطا در ارسال: {e}")
            return False

    def run(self):
        """
        اجرای کامل
        """
        # بررسی: آیا باید ارسال شود؟
        if not self.scheduler.should_send_daily('codal_daily_report'):
            logger.info("❌ امروز قبلاً ارسال شد")
            print("⏳ این گزارش امروز قبلاً ارسال شده است")
            return

        logger.info("\n" + "="*60)
        logger.info("🚀 گزارش روزانهٔ کودال")
        logger.info("="*60 + "\n")

        # دریافت
        reports = self.fetch_reports(num_days=1)

        if not reports:
            logger.warning("⚠️ گزارشی موجود نیست")
            return

        # تحلیل
        analyzed = self.analyze_reports(reports)

        # تولید
        message_blocks = self.generate_telegram_report(analyzed)
        message = "\n".join(message_blocks)

        # نمایش
        print(message)

        # ارسال
        if self.send_to_telegram(message):
            self.scheduler.mark_sent('codal_daily_report', 'sent')
            logger.info("✅ ارسال و ذخیره شد")
        else:
            logger.error("❌ خطا در ارسال")


def main():
    """ورود"""
    load_env_file()
    check_secrets()

    report = CodtalDailyReport()
    report.run()


if __name__ == "__main__":
    main()
