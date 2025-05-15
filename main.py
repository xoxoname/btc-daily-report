
from flask import Flask, request
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.report import (
    generate_prediction_report,
    generate_profit_report,
    generate_schedule_info,
)
from modules.schedule import start_scheduler
import requests
import os

app = Flask(__name__)
start_scheduler()

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"].get("text", "").lower()

    if chat_id != TELEGRAM_CHAT_ID:
        return "Unauthorized", 403

    if "/리포트" in text or "예측" in text:
        reply = generate_prediction_report()
    elif "/수익" in text:
        reply = generate_profit_report()
    elif "/일정" in text:
        reply = generate_schedule_info()
    else:
        reply = "🤖 사용 가능한 명령어: /리포트 /수익 /일정"

    requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        params={"chat_id": chat_id, "text": reply}
    )
    return "OK", 200

@app.route("/")
def home():
    return "BTC 리포트 시스템 정상 작동 중"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
