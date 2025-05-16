from flask import Flask, request
from modules.constants import TELEGRAM_CHAT_ID
from modules.schedule import start_scheduler
from modules.report import build_and_send_report, handle_prediction_report

app = Flask(__name__)
start_scheduler()

@app.route("/")
def home():
    return "BTC Daily Report System is Running!"

@app.route("/report", methods=["GET"])
def report_page():
    return {"status": "success", "message": "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."}

@app.route(f"/{TELEGRAM_CHAT_ID}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return {"ok": True}

    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"].get("text", "")

    if chat_id != TELEGRAM_CHAT_ID:
        return {"ok": False}

    if text == "/수익":
        build_and_send_report()
    elif text == "/예측":
        handle_prediction_report()
    elif text == "/리포트":
        build_and_send_report()
    elif text == "/일정":
        return {
            "ok": True,
            "text": "🗓 앞으로 7일간 주요 일정:\n\n• 📆 5/17 - 트럼프 연설 예정 (BTC 심리 영향 가능성)\n• 📆 5/20 - FOMC 회의록 공개 (금리 관련 불확실성)\n\n🔎 요약: 이번 주는 심리적 변수 비중이 큽니다. 관망 유지 추천"
        }

    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
