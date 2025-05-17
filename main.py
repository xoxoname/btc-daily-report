from flask import Flask, request
from modules.report import generate_full_report, generate_profit_report, generate_prediction
from modules.constants import TELEGRAM_CHAT_ID
from modules.utils import send_telegram_message, authorized

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "✅ BTC 데일리 리포트 서버가 정상 작동 중입니다."

@app.route("/report", methods=["GET", "HEAD"])
def report():
    if request.method == "HEAD":
        return "", 200
    if not authorized(request):
        return "Unauthorized", 403
    msg = generate_full_report()
    send_telegram_message(msg)
    return {"status": "success", "report": msg}

@app.route("/수익", methods=["GET"])
def profit():
    if not authorized(request):
        return "Unauthorized", 403
    msg = generate_profit_report()
    send_telegram_message(msg)
    return {"status": "success", "profit": msg}

@app.route("/예측", methods=["GET"])
def prediction():
    if not authorized(request):
        return "Unauthorized", 403
    msg = generate_prediction()
    send_telegram_message(msg)
    return {"status": "success", "prediction": msg}

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    data = request.json
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", ""))

    if chat_id != TELEGRAM_CHAT_ID:
        return "unauthorized", 403

    if text == "/리포트":
        msg = generate_full_report()
    elif text == "/수익":
        msg = generate_profit_report()
    elif text == "/예측":
        msg = generate_prediction()
    else:
        msg = "❌ 지원하지 않는 명령어입니다.\n가능한 명령어: /리포트 /수익 /예측"

    send_telegram_message(msg)
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
