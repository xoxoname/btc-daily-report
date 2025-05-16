import os
import requests

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(url, json=payload)

def format_currency(val):
    return f"{val:,.2f}"

def convert_usd_to_krw(usd):
    try:
        rate = 1310  # Fix or replace with real-time rate if needed
        return f"{usd * rate:,.0f}"
    except:
        return "N/A"
