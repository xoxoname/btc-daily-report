# main.py
import os
from flask import Flask, request
from modules.report import (
    generate_full_report,
    generate_profit_report,
    generate_prediction,
    generate_schedule
)
from modules.utils import send_telegram_message, authorized

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


@app.route("/")
def index():
    return "✅ BTC Report System is Running."


@app.route("/report", methods=["GET"])
def report_endpoint():
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    if not request.is_json:
        return "invalid", 400

    data = request.get_json()
    if "message" not in data:
        return "no message", 200

    message = data["message"]
    chat_id = str(message.get("chat", {}).get("id"))
    text = message.get("text", "")

    if not authorized(chat_id):
        return "unauthorized", 200

    if text == "/수익":
        msg = generate_profit_report()
    elif text == "/리포트":
        msg = generate_full_report()
    elif text == "/예측":
        msg = generate_prediction()
    elif text == "/일정":
        msg = generate_schedule()
    else:
        msg = "❌ 지원하지 않는 명령어입니다. /수익 /리포트 /예측 /일정 중 하나를 사용해주세요."

    send_telegram_message(msg)
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
