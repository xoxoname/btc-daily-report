import schedule
import time
import threading
from modules.reporter import format_report
from modules.analyst import gpt_exception_alert
from modules.telegram_bot import TELEGRAM_BOT_TOKEN
import requests

def send_telegram_message(msg):
    chat_id = "1038440081"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg})

def send_report():
    send_telegram_message(format_report())

def send_exception():
    exception_msg = gpt_exception_alert()
    if "감지 실패" not in exception_msg:
        send_telegram_message(f"🚨 긴급 예외 감지\n{exception_msg}")

def start_scheduler():
    # 정규 리포트 4회 예약
    schedule.every().day.at("09:00").do(send_report)
    schedule.every().day.at("13:00").do(send_report)
    schedule.every().day.at("17:00").do(send_report)
    schedule.every().day.at("23:00").do(send_report)
    # 5분 간격 예외 감지
    schedule.every(5).minutes.do(send_exception)
    print("스케줄러 시작")
    while True:
        schedule.run_pending()
        time.sleep(1)
