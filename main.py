from flask import Flask
from modules.schedule import start_scheduler
from modules.emergency import start_emergency_monitor

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Auto Reporter is Live"

@app.route("/report")
def trigger_report():
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."

if __name__ == "__main__":
    start_scheduler()
    start_emergency_monitor()
    app.run(host="0.0.0.0", port=10000)
