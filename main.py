from flask import Flask, request
from modules.report import generate_full_report, generate_profit_report, generate_prediction
from modules.constants import TELEGRAM_CHAT_ID
from modules.utils import send_telegram_message, authorized

app = Flask(__name__)

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)  # 🔥 Render 인식 가능하게 수정
