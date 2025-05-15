from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from modules.report import build_and_send_report
from modules.schedule import scheduled_report_jobs
from modules.emergency import start_emergency_monitor
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "📈 BTC 리포트 시스템이 작동 중입니다."

# 1. 정규 리포트 스케줄 등록
scheduler = BackgroundScheduler()
scheduled_report_jobs(scheduler)

# 2. 긴급 탐지 시스템 시작
start_emergency_monitor(scheduler)

# 3. 스케줄러 시작
scheduler.start()

# 4. 포트 바인딩 (Render에서 필수)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
# Placeholder content for main.py
