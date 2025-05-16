from flask import Flask, request
from modules.schedule import start_scheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.utils import send_telegram_message, get_profit_report_text, get_prediction_report_text, get_schedule_report_text

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Daily Report System"

@app.route("/report", methods=["GET"])
def report():
    return {
        "message": "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.",
        "status": "success"
    }

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if str(chat_id) != TELEGRAM_CHAT_ID:
            return "Unauthorized", 403

        if "/수익" in text:
            send_telegram_message(chat_id, "📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요.")
            report = get_profit_report_text()
            send_telegram_message(chat_id, report)

        elif "/예측" in text:
            send_telegram_message(chat_id, "📡 예측 분석 준비 중입니다...\n잠시만 기다려 주세요.")
            report = get_prediction_report_text()
            send_telegram_message(chat_id, report)

        elif "/리포트" in text:
            send_telegram_message(chat_id, "📡 정규 리포트 분석 준비 중입니다...\n조금만 기다려 주세요.")
            send_telegram_message(chat_id, "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")  # 이후 외부 분석 붙이기

        elif "/일정" in text:
            send_telegram_message(chat_id, "🗓 주요 경제 일정 분석 준비 중입니다...\n잠시만 기다려 주세요.")
            report = get_schedule_report_text()
            send_telegram_message(chat_id, report)

        else:
            send_telegram_message(chat_id, "🤖 사용 가능한 명령어:\n/수익 /예측 /리포트 /일정")

    return {"status": "ok"}

if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=5000)
