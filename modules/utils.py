import os
import datetime
import requests
from flask import request

def format_usd(amount):
    return f"${amount:,.2f}"

def format_krw(amount):
    return f"{amount:,.0f}원"

def get_current_timestamp():
    now = datetime.datetime.now()
    return now.strftime("%Y년 %m월 %d일 %p %I:%M").replace("AM", "오전").replace("PM", "오후")

def send_telegram_message(chat_id, message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def authorized(func):
    def wrapper(*args, **kwargs):
        data = request.get_json()
        if str(data["message"]["chat"]["id"]) != os.getenv("TELEGRAM_CHAT_ID"):
            return "unauthorized", 403
        return func(*args, **kwargs)
    return wrapper