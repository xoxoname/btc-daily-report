import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report
from modules.constants import TIMEZONE

scheduler = BackgroundScheduler(timezone=pytz.timezone(TIMEZONE))

def start_scheduler():
    scheduler.add_job(build_and_send_report, 'cron', hour=0, minute=30)
    scheduler.add_job(build_and_send_report, 'cron', hour=4, minute=0)
    scheduler.add_job(build_and_send_report, 'cron', hour=14, minute=0)
    scheduler.start()
