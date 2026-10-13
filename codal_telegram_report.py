#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش تلگرام برای شرکت‌های قوی codal
داده‌های پویا از تاریخچهٔ روزانه
"""

import csv
import os
from datetime import datetime, timedelta
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodalTelegramReport:
    """گزارش تلگرام برای codal"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.history_file = "data/codal_history.csv"
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    def get_today_companies(self):
        """خواندن شرکت‌های امروز از تاریخچه"""
        today = datetime.now().strftime("%Y-%m-%d")
        today_companies = []

        if not os.path.exists(self.history_file):
            logger.warning("❌ فایل تاریخچه پیدا نشد")
            return []

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('date') == today:
                        today_companies.append(row)
        except Exception as e:
            logger.error(f"❌ خطا در خواندن فایل: {e}")

        return today_companies

    def get_trending(self, days=7):
        """شرکت‌هایی که چند روز پیاپی ظاهر شده‌اند (قوی‌تر)"""
        today = datetime.now()
        trending = {}

        if not os.path.exists(self.history_file):
            return []

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_str = row.get('date')
                    try:
                        row_date = datetime.strptime(date_str, "%Y-%m-%d")
                        if (today - row_date).days <= days:
                            symbol = row.get('symbol')
                            if symbol not in trending:
                                trending[symbol] = {
                                    'symbol': symbol,
                                    'company': row.get('company'),
                                    'count': 0,
                                    'score_sum': 0
                                }
                            trending[symbol]['count'] += 1
                            try:
                                trending[symbol]['score_sum'] += float(row.get('score', 0))
                            except:
                                pass
                    except:
                        continue
        except Exception as e:
            logger.error(f"❌ خطا: {e}")

        # فیلتر: فقط آن‌هایی که ۲+ بار ظاهر شده‌اند
        return [c for c in trending.values() if c['count'] >= 2]

    def generate_message(self):
        """تولید پیام تلگرام"""
        today_companies = self.get_today_companies()
        trending = self.get_trending()

        msg = f"📊 <b>گزارش شرکت‌های قوی codal</b>\n"
        msg += f"<i>{self.timestamp}</i>\n\n"

        if not today_companies and not trending:
            msg += "❌ گزارشی برای امروز وجود ندارد"
            return msg

        # بخش ۱: امروز
        if today_companies:
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"<b>📈 امروز ({len(today_companies)} شرکت)</b>\n\n"

            # مرتب‌سازی بر اساس امتیاز
            sorted_today = sorted(
                today_companies,
                key=lambda x: float(x.get('score', 0)) if x.get('score') else 0,
                reverse=True
            )

            for i, company in enumerate(sorted_today[:10], 1):
                symbol = company.get('symbol', 'N/A')
                name = company.get('company', '')
                sales = company.get('sales_growth', 'N/A')
                profit = company.get('profit_growth', 'N/A')
                score = company.get('score', '0')

                try:
                    score_num = float(score)
                except:
                    score_num = 0

                msg += f"<b>{i}. {symbol}</b> - {name}\n"
                msg += f"   📈 فروش: {sales} | سود: {profit}\n"
                msg += f"   ⭐ امتیاز: {score_num:.1f}\n\n"

        # بخش ۲: Trending
        if trending:
            msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"<b>🔥 Trending (۷ روز اخیر)</b>\n"
            msg += f"<i>{len(trending)} شرکت در ۲+ روز ظاهر شده</i>\n\n"

            sorted_trending = sorted(trending, key=lambda x: x['count'], reverse=True)

            for company in sorted_trending[:5]:
                msg += f"<b>{company['symbol']}</b> — {company['company']}\n"
                msg += f"   🔁 تکرار: {company['count']} روز\n"
                msg += f"   ⭐ میانگین امتیاز: {company['score_sum']/company['count']:.1f}\n\n"

        # خلاصه
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>📌 یادداشت</b>\n"
        msg += "• تاریخچهٔ کامل در: <code>data/codal_history.csv</code>\n"
        msg += "• رشد فروش > 10% و سود > 15%\n"
        msg += "• داده‌های پویا از codal.ir\n\n"
        msg += "⚠️ صرفاً اطلاع‌رسانی است.\n"
        msg += "#کودال #شرکت‌های_قوی"

        return msg

    def send_to_telegram(self, message: str) -> bool:
        """ارسال به تلگرام"""
        logger.info(f"🔍 توکن موجود: {bool(self.telegram_token)}")
        logger.info(f"🔍 Chat ID موجود: {bool(self.telegram_chat_id)}")

        if not self.telegram_token or not self.telegram_chat_id:
            logger.error("❌ توکن یا Chat ID موجود نیست")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            logger.info(f"📤 فرستادن به Telegram...")
            logger.info(f"   URL: {url[:50]}...")
            logger.info(f"   Chat ID: {self.telegram_chat_id}")
            logger.info(f"   Message length: {len(message)}")

            # Try with retries
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(url, data=data, timeout=15)

                    if response.status_code == 200:
                        logger.info("✅ پیام ارسال شد")
                        return True
                    else:
                        logger.error(f"❌ HTTP {response.status_code}: {response.text[:100]}")
                        if attempt < max_retries:
                            logger.info(f"   تلاش دوباره {attempt}/{max_retries}...")
                            continue
                        return False

                except requests.exceptions.Timeout:
                    logger.warning(f"⏱️ Timeout (تلاش {attempt}/{max_retries})")
                    if attempt < max_retries:
                        continue
                    raise
                except requests.exceptions.ConnectionError as ce:
                    logger.warning(f"🌐 Connection error (تلاش {attempt}/{max_retries}): {ce}")
                    if attempt < max_retries:
                        continue
                    raise

        except Exception as e:
            logger.error(f"❌ خطا نهایی: {type(e).__name__}: {str(e)[:200]}")
            return False

    def run(self):
        """اجرای کامل"""
        logger.info("🚀 شروع گزارش تلگرام codal...")

        message = self.generate_message()
        print(message)

        self.send_to_telegram(message)


def main():
    report = CodalTelegramReport()
    report.run()


if __name__ == "__main__":
    main()
