# main.py
from flask import Flask, request
from modules.report import generate_full_report, generate_profit_report, generate_prediction
from modules.utils import send_telegram_message, authorized

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ BTC Report Server Running"

@app.route("/report", methods=["GET"])
def report():
    return "✅ Report endpoint available"

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if not authorized(chat_id):
        return "unauthorized", 403

    if "/수익" in text:
        msg = generate_profit_report()
    elif "/예측" in text:
        msg = generate_prediction()
    elif "/리포트" in text:
        msg = generate_full_report()
    elif "/일정" in text:
        from modules.constants import UPCOMING_EVENTS
        msg = UPCOMING_EVENTS
    else:
        msg = "지원하지 않는 명령어입니다."

    send_telegram_message(msg)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
