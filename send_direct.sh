#!/bin/bash

TOKEN="8752723544"
CHAT_ID="-5408618772"
URL="https://api.telegram.org/bot${TOKEN}/sendMessage"

# Message 1: Summary
MSG1="<b>🗞 خلاصهٔ بازار روزانه</b>
<b>Daily Market Summary - 2026-10-12</b>

<b>📡 سیگنال‌های امروز:</b>
🎯 خرید روزانه: 88 نماد
🔴 فروش روزانه: 32 نماد
📈 خرید هفتگی: 31 نماد

<b>👀 سهم‌های شما:</b>
🔴 SOUN - سیگنال فروش هفتگی
🔴 ALAB - سیگنال فروش روزانه
⏰ ICICIBANK - گزارش 6 روز دیگر

<b>🎯 خلاصهٔ امروز:</b>
✅ سیگنال خرید: قوی (88)
⚠️ توجه: SOUN، ALAB
✅ انرژی: گاز طبیعی فوری
⬇️ فلزات: طلا تحت فشار
✅ مومنتوم: بهتر از برابر‌وزنی

📅 2026-10-12 18:51 Tehran"

# Message 2: Macro
MSG2="<b>🌍 گزارش کلان‌اقتصادی هوشمند</b>

<b>🎯 الرت‌های فوری:</b>
🔴 دلار قوی (RSI 69) + طلا نزولی = فشار
🟢 VIX پایین = آرام‌تری بازار
📈 مس صعودی = رشد صنعتی

<b>📊 دارایی‌ها:</b>
📈 S&P 500: ⬆️ +1.2% هفته
💵 دلار: ⬆️ +3.1% ماه
🥇 طلا: ⬇️ -4.3% ماه
⚡ گاز: ⬆️ +13.6% ماه HOT

<b>🎲 پیش‌بینی‌ها:</b>
• کاهش نرخ: 0% ❄️
• دلار: ادامه قوت

📅 2026-10-12 18:51"

# Message 3: Signals
MSG3="<b>🔥 سیگنال‌های هوشمند</b>

<b>🎯 بهترین 5 روزانه:</b>

🔥 #1 ITC (India) - 100 امتیاز
✅ Buffett + CANSLIM

🔥 #2 AMT (US) - 97 امتیاز
+9.3% تغییر | ✅ Buffett

🔥 #3 6098 (Japan) - 97 امتیاز
✅ Buffett + CANSLIM

🔥 #4 VEDL (India) - 96
🔥 #5 VEEV (US) - 92

<b>📈 بهترین 3 هفتگی:</b>
🔥 DDOG: +5.1% | CANSLIM
🔥 PLTR: +8.8% | CANSLIM  
🔥 PDD: +5.3% | Buffett

✅ بهترین: ITC (100)
✅ فقط خرید: 55% Win

📅 2026-10-12 18:51"

echo "🚀 Sending reports to Telegram..."

echo "1️⃣ Sending Daily Summary..."
curl -X POST "$URL" -d "chat_id=$CHAT_ID&text=$MSG1&parse_mode=HTML" 2>/dev/null && echo "✅ Summary sent" || echo "❌ Summary failed"

sleep 1

echo "2️⃣ Sending Macro Analysis..."
curl -X POST "$URL" -d "chat_id=$CHAT_ID&text=$MSG2&parse_mode=HTML" 2>/dev/null && echo "✅ Macro sent" || echo "❌ Macro failed"

sleep 1

echo "3️⃣ Sending Smart Signals..."
curl -X POST "$URL" -d "chat_id=$CHAT_ID&text=$MSG3&parse_mode=HTML" 2>/dev/null && echo "✅ Signals sent" || echo "❌ Signals failed"

echo ""
echo "════════════════════════════════"
echo "✅ گزارش‌ها به تلگرام فرستاده شدند!"
echo "════════════════════════════════"
