# main.py

from flask import Flask
from modules.schedule import start_scheduler
from modules.emergency import start_emergency_monitor
from modules.report import build_and_send_report
from modules.utils import build_profit_report
from modules.constants import TELEGRAM_CHAT_ID
from modules.utils import send_telegram_message

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Report System is running."

@app.route("/수익")
def profit():
    report = build_profit_report()
    send_telegram_message(report)
    return {"status": "ok", "message": "수익 리포트 전송 완료"}

@app.route("/예측")
def predict():
    send_telegram_message("📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")
    build_and_send_report()
    return {"status": "ok", "message": "예측 리포트 전송 요청 완료"}

if __name__ == "__main__":
    start_scheduler()
    start_emergency_monitor()
    app.run(host="0.0.0.0", port=10000)
