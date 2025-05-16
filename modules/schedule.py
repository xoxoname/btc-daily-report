from apscheduler.schedulers.background import BackgroundScheduler
from modules.constants import REPORT_TIMES_KST
from modules.report import build_and_send_report
from modules.utils import get_kst_now

def start_scheduler():
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    for t in REPORT_TIMES_KST:
        scheduler.add_job(
            build_and_send_report,
            'cron',
            hour=t['hour'],
            minute=t['minute']
        )
    scheduler.start()
    print("✅ 스케줄러 시작됨")
