import requests
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

def fetch_coinbase_price():
    response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
    return float(response.json()["data"]["amount"])

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }
    requests.post(url, data=payload)

def format_currency(amount):
    return f"${amount:,.2f}"

def fetch_bitget_position_data():
    # 이 부분은 실제 Bitget API 연동 시 아래 구조를 바꿔야 함
    # 여기서는 테스트용 데이터 사용
    return {
        "total_pnl": 78.5,  # USD
        "positions": [
            {"symbol": "BTCUSDT", "entryPrice": 10200, "pnl": 78.5},
        ],
    }
