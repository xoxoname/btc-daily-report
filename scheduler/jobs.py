import os
import schedule
import time
import requests
from modules.reporter import format_report
from modules.analyst import gpt_exception_alert

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram_message(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def send_report():
    send_telegram_message(format_report())

def send_exception():
    exception_msg = gpt_exception_alert()
    if "감지 실패" not in exception_msg:
        send_telegram_message(f"🚨 긴급 예외 감지\n{exception_msg}")

def start_scheduler():
    schedule.every().day.at("09:00").do(send_report)
    schedule.every().day.at("13:00").do(send_report)
    schedule.every().day.at("17:00").do(send_report)
    schedule.every().day.at("23:00").do(send_report)
    schedule.every(5).minutes.do(send_exception)
    while True:
        schedule.run_pending()
        time.sleep(1)
