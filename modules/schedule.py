# modules/schedule.py

from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report
from pytz import timezone

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=timezone("Asia/Seoul"))
    scheduler.add_job(build_and_send_report, 'cron', hour=9, minute=0)
    scheduler.add_job(build_and_send_report, 'cron', hour=13, minute=0)
    scheduler.add_job(build_and_send_report, 'cron', hour=23, minute=0)
    scheduler.start()
