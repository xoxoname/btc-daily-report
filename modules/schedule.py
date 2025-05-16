from apscheduler.schedulers.background import BackgroundScheduler
from modules.utils import generate_btc_report, get_kst_now
from modules.telegram import send_telegram_message
import os

def send_regular_report():
    now = get_kst_now()
    if now.hour in [9, 13, 23] and now.minute == 0:
        report = generate_btc_report()
        send_telegram_message(os.environ['TELEGRAM_CHAT_ID'], report)

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(send_regular_report, 'interval', minutes=1)
    scheduler.start()
    print("✅ 스케줄러 시작됨")
