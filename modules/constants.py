import os

# Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Bitget API
BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

# OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# 가격 급변 기준 (단위: 퍼센트)
EMERGENCY_THRESHOLD_PERCENT = 2.5

# 보고서 발송 시간 (한국시간 기준)
REPORT_TIMES_KST = [
    {"hour": 9, "minute": 0},
    {"hour": 13, "minute": 0},
    {"hour": 23, "minute": 0},
]

# 보고서 전송 메시지 안내
ANALYSIS_LOADING_MESSAGE = "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."
