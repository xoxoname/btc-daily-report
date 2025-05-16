from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message
from modules.constants import ANALYSIS_LOADING_MESSAGE

app = Flask(__name__)
start_scheduler()

@app.route("/")
def index():
    return "BTC 자동 예측 시스템 작동 중"

@app.route("/report")
def report():
    return {"status": "ok"}

@app.route("/<token>", methods=["POST"])
def telegram_webhook(token):
    data = request.get_json()
    if "message" not in data:
        return "no message", 200

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if str(chat_id) != TELEGRAM_CHAT_ID:
        return "unauthorized", 403

    if "/예측" in text:
        send_telegram_message(ANALYSIS_LOADING_MESSAGE)
    elif "/수익" in text:
        send_telegram_message("📊 수익 확인은 현재 연동된 Bitget 포지션 기준입니다.")
    elif "/일정" in text:
        send_telegram_message("🕘 리포트는 매일 09:00 / 13:00 / 23:00에 발송됩니다.")
    elif "/리포트" in text:
        send_telegram_message(ANALYSIS_LOADING_MESSAGE)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
