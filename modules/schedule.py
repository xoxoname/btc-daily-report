from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import REPORT_TIMES_KST
from modules.report import build_and_send_report
import pytz
from datetime import datetime

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Seoul"))
    for time in REPORT_TIMES_KST:
        scheduler.add_job(build_and_send_report, 'cron', hour=time["hour"], minute=time["minute"])
    scheduler.start()
