from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import REPORT_TIMES_KST
from modules.report import build_and_send_report
from modules.emergency import start_emergency_monitor
import pytz
from datetime import datetime

scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Seoul"))

def start_scheduler():
    for time_cfg in REPORT_TIMES_KST:
        scheduler.add_job(
            build_and_send_report,
            "cron",
            hour=time_cfg["hour"],
            minute=time_cfg["minute"]
        )
    start_emergency_monitor()
    scheduler.start()
