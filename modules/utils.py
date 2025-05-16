import requests
from datetime import datetime, timedelta
import pytz
import os

TELEGRAM_API_URL = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(text: str):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        response = requests.post(TELEGRAM_API_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ 텔레그램 메시지 전송 실패: {e}")


def get_kst_now():
    return datetime.now(pytz.timezone("Asia/Seoul"))


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_krw(value: float) -> str:
    return f"{int(value):,}원"


def fetch_coinbase_price() -> float:
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/spot?currency=USD")
        response.raise_for_status()
        data = response.json()
        return float(data['data']['amount'])
    except Exception as e:
        print(f"❌ Coinbase 시세 조회 실패: {e}")
        return 0.0


def get_profit_report_text():
    return "💸 수익 분석 준비중입니다."


def get_prediction_report_text():
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."


def get_schedule_report_text():
    return "🗓️ 주요 경제 일정 분석 준비중입니다."
