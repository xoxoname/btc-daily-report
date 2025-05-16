# main.py

from flask import Flask, request, jsonify
from modules.schedule import start_scheduler
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.utils import send_telegram_message
from modules.report import (
    build_profit_report,
    build_schedule_report,
    build_prediction_report,
    build_regular_report,
)

app = Flask(__name__)
start_scheduler()

@app.route('/')
def index():
    return "BTC 자동 리포트 시스템"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if str(chat_id) != TELEGRAM_CHAT_ID:
        return "Unauthorized", 403

    if text == "/수익":
        response = build_profit_report()
        send_telegram_message(chat_id, response)
        return jsonify({"status": "ok"})

    elif text == "/일정":
        response = build_schedule_report()
        send_telegram_message(chat_id, response)
        return jsonify({"status": "ok"})

    elif text == "/예측":
        response = build_prediction_report()
        send_telegram_message(chat_id, response)
        return jsonify({"status": "ok"})

    elif text == "/리포트":
        response = build_regular_report()
        send_telegram_message(chat_id, response)
        return jsonify({"status": "ok"})

    return jsonify({"message": "알 수 없는 명령어입니다."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
