import requests
import os
from datetime import datetime, timedelta, timezone

def send_telegram_message(chat_id, text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def format_currency(value):
    return f"${value:,.2f}"

def get_kst_now():
    return datetime.now(timezone(timedelta(hours=9)))
