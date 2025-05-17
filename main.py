from flask import Flask, request
from modules.report import generate_full_report, generate_profit_report, generate_prediction
from modules.schedule import generate_schedule
from modules.emergency import check_emergency
from modules.telegram import send_telegram_message
from modules.utils import authorized

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not authorized(data):
        return "unauthorized", 403

    message = data['message']['text']
    if message == '/수익':
        msg = generate_profit_report()
    elif message == '/예측':
        msg = generate_prediction()
    elif message == '/리포트':
        msg = generate_full_report()
    elif message == '/일정':
        msg = generate_schedule()
    else:
        msg = "지원하지 않는 명령어입니다."

    send_telegram_message(msg)
    return 'ok', 200

@app.route('/report', methods=['GET'])
def check_report():
    return "ok", 200
