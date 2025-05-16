from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report
from modules.utils import get_kst_now

def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    for hour, minute in [(9, 0), (13, 0), (23, 0)]:
        scheduler.add_job(build_and_send_report, 'cron', hour=hour, minute=minute)
    scheduler.start()
    print("✅ 스케줄러 시작됨")
