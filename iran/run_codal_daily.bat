@echo off
rem اجرای گزارش روزانه‌ی کدال روی ویندوز (کامپیوتر داخل ایران). برای زمان‌بندی: Task Scheduler ← این فایل را روزانه ساعت ۱۹:۰۰ اجرا کند.
cd /d "%~dp0\.."
python -m pip install -q -r iran\requirements.txt
python iran\codal_daily.py
