from flask import Flask, request
from modules.report import build_and_send_report
from modules.telegram import process_telegram_message
import os

app = Flask(__name__)

@app.route("/report", methods=["GET"])
def report():
    result = build_and_send_report()
    return result

@app.route(f"/{os.getenv('TELEGRAM_BOT_TOKEN')}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    process_telegram_message(data)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
