# modules/schedule.py

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from modules.report import build_and_send_report
from modules.emergency import check_btc_price_change
import pytz

def start_scheduler():
    seoul_tz = pytz.timezone('Asia/Seoul')
    scheduler = BackgroundScheduler(timezone=seoul_tz)

    # 정규 리포트: 한국시간 기준 09:30, 13:00, 23:00
    scheduler.add_job(build_and_send_report, CronTrigger(hour=9, minute=30, timezone=seoul_tz))
    scheduler.add_job(build_and_send_report, CronTrigger(hour=13, minute=0, timezone=seoul_tz))
    scheduler.add_job(build_and_send_report, CronTrigger(hour=23, minute=0, timezone=seoul_tz))

    # 긴급 감지: 5분 간격
    scheduler.add_job(check_btc_price_change, 'interval', minutes=5)

    scheduler.start()
