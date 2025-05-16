import requests
import time
from datetime import datetime
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def fetch_coinbase_price():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/spot?currency=USD")
        return float(response.json()["data"]["amount"])
    except Exception as e:
        print(f"❌ fetch_coinbase_price error: {e}")
        return None


def format_currency(value):
    try:
        return f"${value:,.2f}"
    except:
        return "$0.00"


def get_kst_now():
    return datetime.utcnow().timestamp() + 9 * 60 * 60


def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload)
        if not response.ok:
            print("❌ 텔레그램 전송 실패:", response.text)
    except Exception as e:
        print("❌ 텔레그램 전송 중 예외 발생:", str(e))
