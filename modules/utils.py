import requests
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Telegram 전송 실패: {e}")

def get_kst_now():
    import pytz
    from datetime import datetime
    return datetime.now(pytz.timezone("Asia/Seoul"))

def format_currency(value):
    return f"{value:,.2f}"

def fetch_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(res.json()["data"]["amount"])
    except Exception as e:
        print(f"❌ 가격 조회 실패: {e}")
        return None
