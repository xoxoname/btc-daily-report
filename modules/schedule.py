# schedule.py
from apscheduler.schedulers.background import BackgroundScheduler
from modules.utils import send_daily_report

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(send_daily_report, 'cron', hour='9,13,23', minute=0)
    scheduler.start()