import requests
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY
from modules.utils import fetch_coinbase_price, fetch_bitget_position_data, format_currency

def build_and_send_report():
    price = fetch_coinbase_price()
    position_data = fetch_bitget_position_data()
    message = f"📊 BTC 보고서\n현재 가격: {format_currency(price)}\n포지션 데이터: {position_data}"
    send_telegram_message(message)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=data)
