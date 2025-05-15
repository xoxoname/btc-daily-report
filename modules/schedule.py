# modules/schedule.py

from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report
from modules.emergency import check_btc_price_change

def start_scheduler():
    scheduler = BackgroundScheduler()

    # 정규 리포트 스케줄 (UTC 기준): 한국 시간 09:30, 13:00, 23:00
    scheduler.add_job(build_and_send_report, 'cron', hour=0, minute=30)
    scheduler.add_job(build_and_send_report, 'cron', hour=4, minute=0)
    scheduler.add_job(build_and_send_report, 'cron', hour=14, minute=0)

    # 5분 간격으로 긴급 감지
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)

    scheduler.start()
