# modules/schedule.py
from apscheduler.schedulers.background import BackgroundScheduler
from .report import build_and_send_report

sched = BackgroundScheduler(timezone="UTC")
# 예: 매일 09:00, 21:00 UTC에 리포트 발송
sched.add_job(build_and_send_report, "cron", hour="9,21", minute=0)
sched.start()
