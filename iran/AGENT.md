# ایجنت «احتمال رشد تکنیکال و بنیادی — بورس ایران»

هر روز (پس از بسته‌شدن بازار) روی کامپیوتر ایران اجرا می‌شود، چون tsetmc و کدال از سرور ابری باز نمی‌شوند.
داده فقط واقعی است؛ هیچ عددی ساخته نمی‌شود. کپچا را هرگز حل نکن. به چت 75439320 و فقط روزی یک گزارش بفرست.

## قاعده
1. **تکنیکال** (tsetmc، قیمت تعدیل‌شده): شکست با حجم / روند صعودی منظم / فشردگی نزدیک سقف / برگشت به میانگین ۵۰، و الگوهای نموداری بلندمدت
   (کف دوقلو، سرووشانه معکوس، فنجان‌ودسته، مثلث صعودی، شکست سقف ۵۲ هفته). نقدشوندگی: میانه‌ی ارزش معاملات ۲۰ روز ≥ ۵ میلیارد ریال.
2. **P/E** (tsetmc): P/E پیش‌بینی (قیمت ÷ EPS پیش‌بینی‌شده) ≤ P/E گروه.
3. **رشد کدال**: رشد فروش > ۱۰٪ و رشد سود خالص > ۱۵٪ نسبت به دوره‌ی مشابه سال قبل، از آخرین صورت مالی؛ سود باید با «درصد تغییر» خود کدال بخواند.
   اگر داده‌ی کدال نیامد → «ناقص»، سیگنال نمی‌شود.

## مراحل (ابزارهای Playwright کامپیوتر ایران؛ ریپو را clone کن)
1. `git pull`. مرورگر: `browser_navigate https://www.tsetmc.com/` (اگر باز نشد: v2rayN باید `domain:tsetmc.com` را مستقیم کند).
2. `browser_evaluate` با محتوای `iran/browser/screen_stage1.js` ← حدود ۱ دقیقه؛ با `browser_run_code_unsafe` ( `await new Promise(r=>setTimeout(r,40000)); return page.evaluate(()=>({s:IR.status,done:IR.done,total:IR.total}))` ) صبر کن تا `s == "tech_done"`.
3. `browser_evaluate` با `iran/browser/screen_stage2.js` را اجرا کن؛ بعدش این را بزن تا نتیجه‌ی فشرده بیاید و در `window.name` هم بماند:
   ```js
   () => { const ok = IR.final; const d = IR.tech.map(x=>x.date).sort();
     const toISO = n => String(n).replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3');
     const res = {meta:{all:IR.all,total:IR.total,liquid:IR.liquid,tech:IR.tech.length,date:d[d.length-1]},
       final: ok.map(x=>{const A=IR.cache[x.code].A;return {code:x.code,sym:x.sym,name:x.name,last:x.last,st:x.st,cp:x.cp,cps:x.cps,rank:x.rank,fpe:x.fpe,spe:x.spe,sector:x.sector,date:x.date,
         hist:{d:A.dates.slice(-260).map(toISO),c:A.c.slice(-260),v:A.vol.slice(-260)}};})};
     window.name = JSON.stringify({syms: ok.map(x=>x.sym), res}); return res; }
   ```
   نتیجه را در `/tmp/results.json` ذخیره کن. (`hist` قیمت/حجم ۲۶۰ روز اخیر هر سهم است؛ فقط برای ساختن نمودار تکنیکال در مرحله‌ی ۷ استفاده می‌شود، جای دیگری لازم نیست.)
4. `python3 iran/iran_agent.py plan /tmp/results.json` ← `{"syms":[...]}` نمادهایی که رشد کدالشان باید گرفته شود (کش ۳۰ روزه).
5. اگر `syms` خالی نیست: `browser_navigate https://www.codal.ir/` ، `window.name = JSON.stringify({syms})` ، سپس `browser_run_code_unsafe` با `iran/browser/codal_growth.js`.
   این اسکریپت آهسته است (حدود ۲۰ ثانیه برای هر نماد). با فراخوانی‌های کوتاه (حداکثر ۴۰ ثانیه) `window.__cdr` را بخوان تا `status` برابر `done` یا `blocked` شود.
   با اولین ۴۲۹ خودش متوقف می‌شود (`blocked`)؛ **حلقه نزن**، آنچه هست را نگه دار؛ فردا ادامه می‌دهد. نتیجه (`window.__cdr`) را در `/tmp/codal.json` ذخیره کن.
6. دوباره `browser_navigate https://www.tsetmc.com/` و `iran/browser/track.js` را اجرا کن، با `__ROWS__` = ردیف‌های `data/iran_growth/history.csv`
   به شکل `[{ticker,date,insCode}]` (insCode را به‌صورت رشته بگذار). خروجی را در `/tmp/track.json` ذخیره کن.
7. `python3 iran/iran_agent.py merge /tmp/results.json /tmp/codal.json /tmp/track.json`
   ← کش کدال، تاریخچه، `track.json` و `today_message.txt` را در `data/iran_growth/` می‌نویسد و پیام را چاپ می‌کند.
8. `git add -f data/iran_growth && git commit && git pull --rebase && git push`.
9. تلگرام (فقط 75439320): `gh api -X POST repos/hsalehi10087/stock-scanner/actions/workflows/send-telegram-test.yml/dispatches -f ref=main -f 'inputs[chat_id]=75439320' -f "inputs[text]=<متن>"`
   (اگر متن از ۳۸۰۰ نویسه بیشتر بود، در دو پیام، تقسیم در مرز خط). پیام را همان‌طور که `today_message.txt` ساخته بفرست و چیزی به آن اضافه نکن.
   اگر کامپیوتر/کدال/tsetmc در دسترس نبود، یک پیام یک‌خطی دلیل را بفرست و عدد نساز.
10. نمودار تکنیکال سهم‌های برتر (اگر مرحله‌ی ۷ خطی «🖼 نمودار تکنیکال …» در پیام نوشت): `data/iran_growth/charts_manifest.json` را بخوان
    (لیست `{png, caption}`؛ `png` مسیر نسبی داخل ریپو است و قبلاً در مرحله‌ی ۸ با `git push` به ریپو رفته). توکن ربات هرگز روی کامپیوتر ایران نمی‌آید؛ به همین دلیل مثل
    پیام متنی، از طریق GitHub Actions (که توکن را به‌صورت secret دارد) ارسال می‌شود، نه مستقیم از کامپیوتر ایران:
    به ترتیب برای هر عضو این لیست (حداکثر ۱۰ تا):
    `gh api -X POST repos/hsalehi10087/stock-scanner/actions/workflows/send-telegram-photo.yml/dispatches -f ref=main -f 'inputs[chat_id]=75439320' -f "inputs[path]=<png>" -f "inputs[caption]=<caption>"`
    هر دیسپچ را با چند ثانیه فاصله بزن و بعد از هر کدام با `gh run list --workflow=send-telegram-photo.yml -L 1` مطمئن شو که `completed`/`success` شده قبل از عضو بعدی.
    اگر فایل مانیفست نبود یا خالی بود، این مرحله را رد کن (یعنی امروز سیگنال تأیید‌شده‌ای برای نمودار نبود).

## موقعیت های آپشن ایران (پیام جدا، هر روز بعد از گزارش بالا)
11. روی همان صفحه‌ی `https://www.tsetmc.com/`، `browser_evaluate` با محتوای `iran/browser/options_screen.js` (حدود ۲۰ ثانیه). خروجی یک رشته‌ی JSON فشرده است؛
    آن را عیناً در `/tmp/options.json` ذخیره کن (فقط کپی؛ هیچ عددی را دستی عوض نکن و بعد از ذخیره با خروجی مرورگر تطبیق بده).
12. `python3 iran/iran_agent.py options /tmp/options.json` ← `data/iran_growth/options_message.txt` و `options_today.json` را می‌نویسد و پیام را چاپ می‌کند.
    `git add -f data/iran_growth && git commit && git pull --rebase && git push`.
13. `options_message.txt` را همان‌طور که هست، در یک پیام جدا (بعد از پیام‌های گزارش رشد) با همان گردش‌کار تلگرام به 75439320 بفرست؛ چیزی اضافه نکن.
    اگر خروجی مرورگر `error` داشت یا tsetmc باز نشد، پیام آپشن را نفرست و فقط در خلاصه‌ی پایانی بنویس چرا. قاعده: نقدشوندگی (≥۳۰ معامله، ≥۵ میلیارد ریال،
    فاصله‌ی خرید و فروش ≤۸٪، ≥۱۴ روز تا سررسید)، کال فقط روی پایه‌ی بالای میانگین ۵۰ روزه و پوت فقط روی پایه‌ی زیر آن، مرتب بر اساس نوسان ضمنی ÷ نوسان واقعی ۳۰ روزه (حداکثر ۲ برابر).

