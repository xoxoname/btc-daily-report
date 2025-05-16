from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_message, parse_command
from modules.report import generate_profit_report, generate_schedule_report
import os

app = Flask(__name__)
start_scheduler()

@app.route('/')
def index():
    return "✅ BTC Report System Running"

@app.route(f"/{os.getenv('TELEGRAM_BOT_TOKEN')}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if "message" not in data:
        return "no message"

    message = data["message"]
    chat_id = message["chat"]["id"]
    if str(chat_id) != os.getenv("TELEGRAM_CHAT_ID"):
        return "unauthorized"

    text = message.get("text", "")
    if "/수익" in text:
        send_message(chat_id, "📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요.")
        report = generate_profit_report()
        send_message(chat_id, report)
    elif "/일정" in text:
        report = generate_schedule_report()
        send_message(chat_id, report)
    else:
        send_message(chat_id, "❓ 지원되지 않는 명령어입니다.")

    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
