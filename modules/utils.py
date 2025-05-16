import requests
import os

# 환경변수 불러오기
BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_APISECRET = os.environ.get("BITGET_APISECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Coinbase BTC 가격 불러오기
def fetch_coinbase_price():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        response.raise_for_status()
        data = response.json()
        return float(data["data"]["amount"])
    except Exception as e:
        print(f"[Coinbase Error] {e}")
        return None

# 텔레그램 전송 (1인 대상)
def send_telegram_message(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[Telegram Error] {e}")

# 화폐 형식
def format_currency(value: float) -> str:
    return f"${value:,.2f}"

# 한화 환산 (기본 환율 1370)
def convert_to_krw(value: float, rate: float = 1370) -> str:
    return f"{round(value * rate / 10000, 1)}만원"

# 더미: 비트겟 API 연동이 필요한 함수 자리
def fetch_bitget_positions():
    # TODO: Bitget API 연동 시 실제 포지션 가져오도록 수정
    return []

def fetch_bitget_wallet_balance():
    # TODO: Bitget API 연동 시 실제 잔고 가져오도록 수정
    return {"total": 0, "available": 0}

# 리포트 응답 프리셋
def get_profit_report_text():
    return "📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요."

def get_prediction_report_text():
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."

def get_schedule_report_text():
    return "🗓️ 주요 경제 일정 분석 준비 중입니다..."
