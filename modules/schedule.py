from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import REPORT_TIMES_KST
from modules.report import build_and_send_report
from modules.emergency import start_emergency_monitor

scheduler = BackgroundScheduler()

def start_scheduler():
    for time in REPORT_TIMES_KST:
        scheduler.add_job(build_and_send_report, 'cron', hour=time["hour"], minute=time["minute"])

    scheduler.start()
    start_emergency_monitor()
