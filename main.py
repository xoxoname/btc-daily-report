import os
from flask import Flask, request
from modules.report import generate_full_report, generate_profit_report, generate_prediction
from modules.utils import send_telegram_message, authorized

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Daily Report 시스템이 정상 작동 중입니다."

@app.route("/webhook", methods=["POST"])
@authorized
def telegram_webhook():
    data = request.json
    message = data.get("message", {}).get("text", "")

    if message == "/수익":
        msg = generate_profit_report()
    elif message == "/리포트":
        msg = generate_full_report()
    elif message == "/예측":
        msg = generate_prediction()
    elif message == "/일정":
        msg = generate_schedule()
    else:
        msg = "📌 /수익 /리포트 /예측 /일정 중 하나의 명령어를 입력해 주세요."

    send_telegram_message(msg)
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
