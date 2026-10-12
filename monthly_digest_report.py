#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش خلاصهٔ ماهانه
فقط سیگنال‌های قوی (Win% > 50%) + تکرار‌های زیاد
"""

import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonthlyDigestReport:
    """گزارش خلاصهٔ ماهانه - فقط قوی‌ترین‌ها"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    # داده‌های گزارش RSI/MACD از فایل بارگذاری شده
    STRONG_SIGNALS = {
        "aligned_buy": {
            "name": "⭐ خرید روزانه + روند هفتگی (قوی‌ترین)",
            "win_pct": 51,
            "avg_return": 0.13,
            "exc_return": 0.44,
            "count": 22,
            "description": "خرید روزانه که هم‌جهت با روند مثبت هفتگی است",
            "top_stocks": ["BSX", "LDOS", "J", "CTSH", "MDT", "BIIB", "MRNA"]
        },
        "buy_daily": {
            "name": "🟢 خرید روزانه (قوی)",
            "win_pct": 59,
            "avg_return": 0.56,
            "exc_return": 0.68,
            "count": 492,
            "description": "سیگنال خرید روزانه - بهترین عملکرد",
            "top_stocks": ["HRL", "WYNN", "PNR", "WY", "BAC", "FRT", "GS", "MS", "PNC", "ARES"]
        },
        "buy_weekly": {
            "name": "🟢 خرید هفتگی",
            "win_pct": 46,
            "avg_return": -0.76,
            "exc_return": -0.82,
            "count": 69,
            "description": "سیگنال خرید هفتگی - نیاز به دقت",
            "skip": True  # ضعیف است
        }
    }

    # سهم‌های تکرار شده (بیش از ۲ بار)
    REPEATED_STOCKS = {
        "BSX": {"times": 2, "status": "Buy-D"},
        "LDOS": {"times": 2, "status": "Buy-D"},
        "J": {"times": 2, "status": "Buy-D"},
        "CTSH": {"times": 2, "status": "Buy-D"},
        "MDT": {"times": 2, "status": "Buy-D"},
        "CCI": {"times": 2, "status": "Buy-D"},
        "COST": {"times": 2, "status": "Buy-W"},
        "NFLX": {"times": 2, "status": "Buy-W"},
    }

    # بهترین سیگنال‌های باز (Top performers)
    BEST_PERFORMERS = [
        {"symbol": "1301.TW", "signal": "Buy-D", "date": "10-01", "days": 7, "ret": 21.7},
        {"symbol": "CCI", "signal": "Buy-D", "date": "10-08", "days": 4, "ret": 17.1},
        {"symbol": "2383.TW", "signal": "Buy-D", "date": "10-02", "days": 6, "ret": 15.7},
        {"symbol": "SNPS", "signal": "Buy-W", "date": "09-30", "days": 12, "ret": 15.5},
        {"symbol": "VST", "signal": "Buy-D", "date": "10-02", "days": 10, "ret": 14.5},
    ]

    # معلومات بنیادی برتر
    FUNDAMENTALS_BEST = {
        "US": {
            "leader": "SNDK",
            "sales": "+372%",
            "profit": "+999%",
            "price": 1487.4,
            "avg_return": 0.7
        },
        "China": {
            "leader": "601628",
            "sales": "+154%",
            "profit": "+848%",
            "price": 36.15,
            "avg_return": -1.5
        },
        "Taiwan": {
            "leader": "2408",
            "sales": "+577%",
            "profit": "+999%",
            "price": 532.0,
            "avg_return": 5.8
        }
    }

    def generate_message(self):
        """تولید پیام تلگرام"""
        msg = f"📊 <b>گزارش خلاصهٔ ماهانه</b>\n"
        msg += f"<i>{self.timestamp}</i>\n"
        msg += "فقط سیگنال‌های قوی و تکرار‌های معنی‌دار\n\n"

        # بخش ۱: سیگنال‌های قوی
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>🎯 سیگنال‌های قوی</b>\n\n"

        for key, sig in self.STRONG_SIGNALS.items():
            if sig.get("skip"):
                continue

            msg += f"<b>{sig['name']}</b>\n"
            msg += f"✅ موفقیت: {sig['win_pct']}%\n"
            msg += f"📈 بازده: {sig['avg_return']:+.2f}% | برتری: {sig['exc_return']:+.2f}%\n"
            msg += f"📊 تعداد: {sig['count']} سیگنال\n"
            msg += f"📌 توضیح: {sig['description']}\n\n"

        # بخش ۲: سهم‌های تکرار (مهم!)
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>🔥 سهم‌های تکرار شده (قوی‌تر)</b>\n"
        msg += "<i>هرچند بیشتر تکرار شود، احتمال موفقیت بیشتر</i>\n\n"

        for stock, data in sorted(self.REPEATED_STOCKS.items(),
                                  key=lambda x: x[1]["times"], reverse=True):
            msg += f"🟢 <b>{stock}</b> — {data['times']}× تکرار | {data['status']}\n"

        # بخش ۳: بهترین‌ها
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>🏆 بهترین سیگنال‌های باز</b>\n\n"

        for i, perf in enumerate(self.BEST_PERFORMERS[:3], 1):
            msg += f"{i}. <b>{perf['symbol']}</b> {perf['signal']}\n"
            msg += f"   {perf['days']} روز | <b>+{perf['ret']:.1f}%</b> 📈\n"

        # بخش ۴: بنیادی برتر
        msg += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>📊 رشد بنیادی برتر</b>\n\n"

        for region, data in self.FUNDAMENTALS_BEST.items():
            msg += f"<b>{region}</b>\n"
            msg += f"قیمت: {data['price']} | "
            msg += f"فروش: {data['sales']} | "
            msg += f"سود: {data['profit']}\n"
            msg += f"بازده: {data['avg_return']:+.1f}%\n\n"

        # خلاصهٔ نهایی
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>📌 خلاصهٔ فصل</b>\n"
        msg += "• Buy-D بهترین (Win% 59%)\n"
        msg += "• تکرار‌ها = سیگنال‌های قوی‌تر\n"
        msg += "• تایوان بهترین عملکرد (+5.8%)\n"
        msg += "• فقط سیگنال‌های Win% > 50%\n\n"
        msg += "⚠️ صرفاً اطلاع‌رسانی است.\n"
        msg += "#گزارش_ماهانه #سیگنال_قوی"

        return msg

    def send_to_telegram(self, message: str) -> bool:
        """ارسال به تلگرام"""
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
        """اجرای کامل"""
        logger.info("🚀 شروع گزارش خلاصهٔ ماهانه...")

        message = self.generate_message()
        print(message)

        self.send_to_telegram(message)


def main():
    report = MonthlyDigestReport()
    report.run()


if __name__ == "__main__":
    main()
