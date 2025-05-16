import os
import requests
from modules.bitget_api import fetch_bitget_wallet_balance, fetch_bitget_positions

def fetch_coinbase_price():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(response.json()["data"]["amount"])
    except Exception as e:
        return None

def format_currency(amount):
    return f"${amount:,.2f}"

def send_telegram_message(text):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, json=data)

def get_profit_report_text():
    balance = fetch_bitget_wallet_balance()
    positions = fetch_bitget_positions()
    return f"💰 잔액 정보: {balance}\n📈 포지션 정보: {positions}"
