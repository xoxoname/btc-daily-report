import os
import requests
from modules.utils import format_currency
from modules.constants import TELEGRAM_BOT_TOKEN, CHAT_ID, REPORT_URL

def get_bitget_price():
    try:
        url = "https://api.bitget.com/api/mix/v1/market/ticker?symbol=BTCUSDT_UMCBL"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return float(data["data"]["last"]) if "data" in data and "last" in data["data"] else None
    except Exception as e:
        print(f"[가격 조회 실패] {e}")
        return None

def build_and_send_report():
    price = get_bitget_price()

    prediction_report = "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."

    if price is None:
        profit_report = "❌ 비트코인 실시간 가격 조회에 실패했습니다."
    else:
        krw_price = int(price * 1350)
        profit_report = f"📊 현재 BTC 가격: ${price:.2f} ({format_currency(krw_price)} KRW 기준)"

    send_telegram_message(f"{prediction_report}\n\n{profit_report}")

    return {
        "prediction_report": prediction_report,
        "profit_report": profit_report,
        "status": "success" if price else "warning"
    }

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        res = requests.post(url, json=payload, timeout=5)
        res.raise_for_status()
    except Exception as e:
        print(f"[텔레그램 전송 실패] {e}")
