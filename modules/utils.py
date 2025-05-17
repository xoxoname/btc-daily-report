import os
import time

def get_current_timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def authorized(data):
    return str(data["message"]["chat"]["id"]) == os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(msg):
    import requests
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def format_usd(amount):
    return f"${amount:,.2f}"

def format_krw(amount):
    return f"{int(amount):,}원"

def get_bitget_data():
    # TODO: Replace with real Bitget API integration
    return {
        "positions": [{
            "symbol": "BTCUSDT",
            "entry_price": 10200.0,
            "current_price": 10050.0,
            "pnl_usd": -150.0,
            "pnl_krw": -205000,
        }],
        "realized": -20.0,
        "return_rate": -7.1,
        "deposit": 2100.0,
        "now_asset": 1930.0,
        "total_pnl": -170.0,
        "total_krw": -232000,
        "weekly_return": 4.2
    }
