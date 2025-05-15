# 📅 APScheduler 기반 예약 작업용 템플릿

from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import get_prediction_report

def scheduled_job():
    print("⏰ 스케줄러 실행 중")
    report = get_prediction_report()
    print("🔮 예측 리포트 생성 완료:", report[:100])  # 일부 출력

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_job, 'interval', hours=12)
    scheduler.start()
