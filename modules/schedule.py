from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report

def schedule_reports():
    scheduler = BackgroundScheduler()
    scheduler.add_job(build_and_send_report, 'cron', hour='0,4,14', minute='30')  # KST: 9:30, 13:00, 23:00
    scheduler.start()
