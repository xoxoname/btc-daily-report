# modules/constants.py
import os

# Bitget API
BITGET_API_KEY    = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID            = os.getenv("CHAT_ID")

# 서버 포트
PORT = int(os.getenv("PORT", 5000))
