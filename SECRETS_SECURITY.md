# 🔐 راهنمای امنیت Secrets

## مشکل (چرا Secrets پاک می‌شوند)

GitHub Secrets **خودکار پاک نمی‌شوند**. اگر پاک شدند، دلایل احتمالی:

1. **دستی پاک شدند** - کسی در GitHub وارد شد و حذف کرد
2. **Repository reset شد** - مثلاً Fork یا reset
3. **GitHub issue** - کم احتمال اما ممکن

---

## ✅ راه‌حل (3 لایه محافظت)

### لایهٔ 1: Local Development (.env)
```bash
# .env (در .gitignore - هیچ‌وقت commit نشود)
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef
TELEGRAM_CHAT_ID=-987654321
```

**مزایا:**
- ✅ محلی برای توسعه
- ✅ GitHub سرور را بار نکن
- ✅ اگر GitHub Secrets پاک شود، .env هنوز دارا است

### لایهٔ 2: GitHub Secrets (Production)
```
https://github.com/hsalehi10087/stock-scanner/settings/secrets/actions
```

| Secret Name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | توکن شما |
| `TELEGRAM_CHAT_ID` | Chat ID شما |

**مزایا:**
- ✅ محفوظ و encrypted
- ✅ GitHub Actions بطور خودکار دریافت می‌کند
- ✅ Audit trail

### لایهٔ 3: Backup Documentation
```bash
# SECRETS_BACKUP.md (NEVER commit!)
# Personal notes for recovery
# Date: 2026-10-11
# ⚠️ DELETE THIS AFTER SETTING UP GITHUB SECRETS
```

---

## 🔍 Audit: چک کن Secrets موجود است

```bash
# محلی
test -f .env && echo "✅ .env exists" || echo "❌ .env missing"

# GitHub - دستی بررسی کن:
# 1. https://github.com/.../settings/secrets/actions
# 2. See if TELEGRAM_BOT_TOKEN exists
# 3. If empty → reset it
```

---

## 🛡️ بهترین‌های امنی

1. **NEVER commit secrets** - حتی encrypted
2. **Use .env locally** - توسعه بدون GitHub
3. **GitHub Secrets اساسی** - Production
4. **Rotate quarterly** - توکن را تغییر دهید
5. **Audit trail** - ببینید کی تغییر کرد

---

## 🚨 اگر Secrets دوباره پاک شدند

**بازیابی سریع:**
```bash
# 1. .env از محلی بازیابی کن (اگر موجود)
# 2. GitHub Secrets دوباره تنظیم کن
# 3. Push: git push
# 4. Workflow ساعت 6:30 UTC اجرا خواهد شد
```

---

## 📝 Checklist

- [ ] .env فایل محلی (gitignore شده)
- [ ] GitHub Secrets تنظیم شد
- [ ] .env.example موجود (بدون values)
- [ ] SECRETS_SECURITY.md موجود
- [ ] SECRETS_BACKUP.md حذف شد
- [ ] Workflow اجرا شد و ✅ موفق

