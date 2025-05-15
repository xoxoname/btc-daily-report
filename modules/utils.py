# utils.py
import requests
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import get_prediction_report, format_profit_report_text

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    requests.post(url, data=data)

def send_daily_report():
    prediction = get_prediction_report()
    profit = format_profit_report_text()
    message = f"📌 GPT 매동 예측 예상\n\n{prediction}\n\n{profit}"
    send_message(message)