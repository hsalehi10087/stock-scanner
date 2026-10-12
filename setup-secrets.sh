#!/bin/bash
# Setup GitHub Secrets

TOKEN="8752723544:AAElnbyf_wIVDcpTlJJ-VoKsx7QHaaolZ54"
CHAT_ID="-5408618772"

echo "🔐 اضافه کردن GitHub Secrets..."
echo ""

# Check gh CLI
if ! command -v gh &> /dev/null; then
    echo "❌ gh CLI موجود نیست"
    echo "دانلود از: https://cli.github.com"
    exit 1
fi

# Add secrets
echo "📝 TELEGRAM_BOT_TOKEN..."
gh secret set TELEGRAM_BOT_TOKEN --body "$TOKEN"

echo "📝 TELEGRAM_CHAT_ID..."
gh secret set TELEGRAM_CHAT_ID --body "$CHAT_ID"

echo ""
echo "✅ تمام Secrets اضافه شدند!"
echo ""
echo "اطمینان دار:"
gh secret list
