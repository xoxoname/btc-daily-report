from modules.utils import send_telegram_message
from modules.report import generate_full_report
import datetime

def scheduled_job():
    now = datetime.datetime.now().strftime("%H:%M")
    send_telegram_message(f"📡 분석 중입니다. {now} 리포트 준비 중... 약 3분 소요 예상됩니다.")
    msg = generate_full_report()
    send_telegram_message(msg)
