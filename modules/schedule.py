from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import generate_prediction_report
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import requests

def send_report():
    msg = "📢 *GPT 매동 예측 예상 리포트*\n\n"
    msg += generate_prediction_report()
    requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        params={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    )

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(send_report, 'cron', hour='9,13,23', minute='0')
    scheduler.start()
