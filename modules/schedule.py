from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report

def start_scheduler():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(build_and_send_report, 'cron', hour='9,13,23', minute=0)
    scheduler.start()
    print("✅ 스케줄러 시작됨")
