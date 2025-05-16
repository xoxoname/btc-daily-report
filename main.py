from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message, get_command_text
import os

app = Flask(__name__)
start_scheduler()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {}).get("text", "")
    chat_id = data.get("message", {}).get("chat", {}).get("id", "")

    if str(chat_id) != str(CHAT_ID):
        return "unauthorized", 403

    if message == "/수익":
        send_telegram_message(chat_id, get_command_text("profit"))
    elif message == "/예측":
        send_telegram_message(chat_id, get_command_text("prediction"))
    elif message == "/일정":
        send_telegram_message(chat_id, get_command_text("schedule"))
    else:
        send_telegram_message(chat_id, "지원하는 명령어가 아닙니다.")

    return "ok", 200

@app.route("/")
def index():
    return "BTC 리포트 서버 실행 중"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
