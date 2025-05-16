import os

# 텔레그램 봇 인증 정보
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Bitget API
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

# 기준 시간대
TIMEZONE = "Asia/Seoul"

# 변동성 경고 기준 (예: 2% 이상)
PRICE_CHANGE_THRESHOLD = 2.0
