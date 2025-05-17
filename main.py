from flask import Flask, request
from modules.report import generate_profit_report, generate_prediction, generate_full_report
from modules.schedule import generate_schedule
from modules.telegram import send_telegram_message
from modules.utils import authorized

app = Flask(__name__)

@app.route("/")
def home():
    return "BTC Daily Report Running"

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not authorized(data):
        return "unauthorized", 403

    text = data["message"]["text"]
    if text == "/수익":
        msg = generate_profit_report()
    elif text == "/예측":
        msg = generate_prediction()
    elif text == "/리포트":
        msg = generate_full_report()
    elif text == "/일정":
        msg = generate_schedule()
    else:
        msg = "명령어를 인식할 수 없습니다."

    send_telegram_message(msg)
    return "ok"
