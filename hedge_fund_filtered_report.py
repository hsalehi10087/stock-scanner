#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
گزارش روزانه: سرمایه‌گذاران بزرگ + خلاصهٔ هوشمندانه
فقط تغییرات > 10% + سیگنال‌های قوی (Win% > 50%)
"""

import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HedgeFundSmartReport:
    """گزارش روزانه: سرمایه‌گذاران بزرگ + خلاصهٔ هوشمندانه"""

    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    # داده‌های سرمایه‌گذاران بزرگ (> 10% تغییر)
    HEDGE_FUND_MOVES = {
        "وارن بافت": {
            "moves": [
                {"move": "ADD", "stock": "Alphabet", "change_pct": 45, "weight": 9.4},
                {"move": "ADD", "stock": "Alphabet", "change_pct": 658, "weight": 3.2},
                {"move": "ADD", "stock": "Delta Air Line", "change_pct": 44, "weight": 1.8},
            ]
        },
        "بیل اکمن": {
            "moves": [
                {"move": "CUT", "stock": "Alphabet", "change_pct": 95, "weight": 0.7},
                {"move": "CUT", "stock": "Alphabet", "change_pct": 95, "weight": 0.1},
                {"move": "SOLD", "stock": "Hilton Worldwi", "change_pct": 100, "weight": 5.6},
            ]
        },
        "مایکل بری": {
            "moves": [
                {"move": "SOLD", "stock": "Unitedhealth", "change_pct": 100, "weight": 18.9},
                {"move": "SOLD", "stock": "Regeneron Phar", "change_pct": 100, "weight": 18.2},
                {"move": "SOLD", "stock": "Lululemon Athl", "change_pct": 100, "weight": 16.4},
                {"move": "SOLD", "stock": "Meta Platforms", "change_pct": 100, "weight": 12.8},
            ]
        },
        "ری دالیو": {
            "moves": [
                {"move": "ADD", "stock": "Vanguard Index", "change_pct": 189, "weight": 1.3},
                {"move": "CUT", "stock": "Broadcom", "change_pct": 28, "weight": 2.0},
                {"move": "CUT", "stock": "Amazon", "change_pct": 54, "weight": 2.0},
                {"move": "CUT", "stock": "Alphabet", "change_pct": 34, "weight": 1.9},
                {"move": "CUT", "stock": "Lam Research", "change_pct": 40, "weight": 1.7},
                {"move": "CUT", "stock": "Advanced Micro", "change_pct": 58, "weight": 1.3},
                {"move": "CUT", "stock": "Microsoft", "change_pct": 34, "weight": 1.1},
            ]
        },
        "استنلی دراکنمیلر": {
            "moves": [
                {"move": "ADD", "stock": "Amazon", "change_pct": 1083, "weight": 2.5},
                {"move": "ADD", "stock": "Seagate Techno", "change_pct": 141, "weight": 2.3},
                {"move": "ADD", "stock": "Amazon (Call)", "change_pct": 130, "weight": 2.1},
                {"move": "ADD", "stock": "United Airls", "change_pct": 203, "weight": 2.1},
                {"move": "ADD", "stock": "Ishares Tr (Ca", "change_pct": 318, "weight": 1.9},
                {"move": "CUT", "stock": "Woodward", "change_pct": 68, "weight": 0.5},
                {"move": "CUT", "stock": "Roku", "change_pct": 75, "weight": 0.5},
                {"move": "CUT", "stock": "Teva Pharmaceu", "change_pct": 74, "weight": 0.4},
                {"move": "SOLD", "stock": "Broadcom", "change_pct": 100, "weight": 1.8},
            ]
        },
        "جرج سوروس": {
            "moves": [
                {"move": "ADD", "stock": "Entergy", "change_pct": 1084, "weight": 1.3},
                {"move": "ADD", "stock": "Itron", "change_pct": 46, "weight": 1.2},
                {"move": "ADD", "stock": "Digital Rlty T", "change_pct": 840, "weight": 1.2},
                {"move": "ADD", "stock": "Webster Finl", "change_pct": 56, "weight": 1.0},
                {"move": "ADD", "stock": "Nextera Energy", "change_pct": 36, "weight": 1.0},
                {"move": "ADD", "stock": "Brighthouse Fi", "change_pct": 32, "weight": 0.9},
                {"move": "CUT", "stock": "Amazon", "change_pct": 39, "weight": 3.5},
                {"move": "CUT", "stock": "Taiwan Semicon", "change_pct": 55, "weight": 1.0},
            ]
        },
        "دیوید تپر": {
            "moves": [
                {"move": "ADD", "stock": "Meta Platforms", "change_pct": 55, "weight": 4.9},
                {"move": "ADD", "stock": "Baidu", "change_pct": 87, "weight": 1.9},
                {"move": "CUT", "stock": "Micron Technol", "change_pct": 41, "weight": 14.6},
                {"move": "CUT", "stock": "Alibaba Hldg", "change_pct": 42, "weight": 2.5},
                {"move": "SOLD", "stock": "Sandisk", "change_pct": 100, "weight": 3.0},
                {"move": "SOLD", "stock": "Corning", "change_pct": 100, "weight": 2.6},
            ]
        },
        "دن لوب": {
            "moves": [
                {"move": "ADD", "stock": "Alphabet", "change_pct": 486, "weight": 7.8},
                {"move": "ADD", "stock": "Taiwan Semicon", "change_pct": 67, "weight": 4.7},
                {"move": "ADD", "stock": "Live Nation En", "change_pct": 144, "weight": 4.4},
                {"move": "ADD", "stock": "Norfolk Southn", "change_pct": 500, "weight": 4.0},
                {"move": "ADD", "stock": "Capital One Fi", "change_pct": 489, "weight": 3.5},
                {"move": "SOLD", "stock": "Meta Platforms", "change_pct": 100, "weight": 2.5},
                {"move": "SOLD", "stock": "Nvidia", "change_pct": 100, "weight": 1.6},
            ]
        },
        "ست کلارمن": {
            "moves": [
                {"move": "ADD", "stock": "Genuine Parts", "change_pct": 89, "weight": 6.1},
                {"move": "ADD", "stock": "Norwegian Crui", "change_pct": 113, "weight": 3.0},
                {"move": "CUT", "stock": "Wesco Intl", "change_pct": 54, "weight": 4.2},
                {"move": "CUT", "stock": "Eagle Matls", "change_pct": 41, "weight": 2.2},
                {"move": "SOLD", "stock": "Willis Towers", "change_pct": 100, "weight": 5.1},
            ]
        },
        "کتی وود": {
            "moves": [
                {"move": "ADD", "stock": "Alphabet", "change_pct": 45, "weight": 2.4},
                {"move": "ADD", "stock": "Nvidia", "change_pct": 33, "weight": 1.8},
                {"move": "ADD", "stock": "Eli Lilly &", "change_pct": 509, "weight": 0.6},
                {"move": "CUT", "stock": "Advanced Micro", "change_pct": 48, "weight": 5.3},
            ]
        },
        "چیس کلمن": {
            "moves": [
                {"move": "ADD", "stock": "Intel", "change_pct": 160, "weight": 2.5},
                {"move": "CUT", "stock": "Alphabet", "change_pct": 45, "weight": 8.7},
                {"move": "CUT", "stock": "Broadcom", "change_pct": 51, "weight": 2.8},
            ]
        },
        "فیلیپ لافون": {
            "moves": [
                {"move": "ADD", "stock": "Micron Technol", "change_pct": 1794, "weight": 7.5},
                {"move": "ADD", "stock": "Amazon", "change_pct": 49, "weight": 5.8},
            ]
        },
        "لی لو": {
            "moves": [
                {"move": "ADD", "stock": "Pdd", "change_pct": 134, "weight": 22.2},
                {"move": "SOLD", "stock": "Bk Of America", "change_pct": 100, "weight": 4.6},
            ]
        },
    }

    # بهترین performers
    BEST_PERFORMERS = [
        {"symbol": "1301.TW", "signal": "Buy-D", "ret": 21.7},
        {"symbol": "CCI", "signal": "Buy-D", "ret": 17.1},
        {"symbol": "2383.TW", "signal": "Buy-D", "ret": 15.7},
    ]

    # سهم‌های تکرار
    REPEATED_STOCKS = ["BSX", "LDOS", "J", "CTSH", "MDT", "CCI", "COST", "NFLX"]

    def filter_significant_moves(self, threshold=10):
        """فیلتر: فقط تغییرات > threshold%"""
        filtered = {}
        for investor, data in self.HEDGE_FUND_MOVES.items():
            significant = [m for m in data["moves"] if m.get("change_pct", 0) and m["change_pct"] > threshold]
            if significant:
                filtered[investor] = {"moves": significant}
        return filtered

    def generate_message(self):
        """تولید پیام تلگرام"""
        filtered = self.filter_significant_moves(threshold=10)

        msg = f"🐋 <b>گزارش روزانه سرمایه‌گذاران بزرگ</b>\n"
        msg += f"<i>{self.timestamp}</i>\n"
        msg += "منبع: SEC Dataroma\n\n"

        # بخش ۱: تغییرات > 10%
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>🔥 تغییرات > 10% در پورتفوليو</b>\n\n"

        for investor, data in filtered.items():
            msg += f"<b>{investor}</b>\n"
            for move in data["moves"]:
                symbol = move["stock"]
                change = move["change_pct"]
                weight = move["weight"]
                symbol_emoji = "🟢" if move["move"] in ["ADD", "NEW"] else "🔴"
                msg += f"{symbol_emoji} {symbol:20} {change:>5}% | Wt: {weight:>5.1f}%\n"
            msg += "\n"

        # بخش ۲: خلاصهٔ هوشمندانه
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "<b>📊 خلاصهٔ هوشمندانه</b>\n\n"

        # بهترین performers
        msg += "<b>🏆 بهترین سیگنال‌ها:</b>\n"
        for perf in self.BEST_PERFORMERS:
            msg += f"  • {perf['symbol']} {perf['signal']}: +{perf['ret']:.1f}%\n"

        # سهم‌های تکرار
        msg += f"\n<b>🔥 سهم‌های تکرار (قوی‌تر):</b>\n"
        for stock in self.REPEATED_STOCKS[:5]:
            msg += f"  • {stock}\n"

        # خلاصهٔ کوتاه
        msg += f"\n<b>📌 خلاصه:</b>\n"
        msg += f"  • {len(filtered)} سرمایه‌گذار فعال\n"
        msg += f"  • {sum(len(d['moves']) for d in filtered.values())} تغییر معنی‌دار\n"
        msg += f"  • Buy/ADD بیشتر از SOLD\n"

        msg += "\n⚠️ صرفاً اطلاع‌رسانی است.\n"
        msg += "#سرمایه‌گذاران_بزرگ #تحلیل_مالی"

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
        logger.info("🚀 شروع گزارش روزانه...")

        message = self.generate_message()
        print(message)

        self.send_to_telegram(message)


def main():
    report = HedgeFundSmartReport()
    report.run()


if __name__ == "__main__":
    main()
