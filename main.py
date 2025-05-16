from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message, get_kst_now
from modules.report import handle_command

import os

app = Flask(__name__)
start_scheduler()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@app.route('/')
def index():
    return "BTC Daily Report Running"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if 'message' in data and 'text' in data['message']:
        chat_id = str(data['message']['chat']['id'])
        if chat_id != CHAT_ID:
            return "Unauthorized", 403
        text = data['message']['text']
        handle_command(text)
    return '', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
