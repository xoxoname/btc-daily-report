import os
from flask import Flask, request
from modules.utils import parse_command, generate_btc_report, generate_schedule_message, get_kst_now
from modules.schedule import start_scheduler
from modules.constants import TELEGRAM_CHAT_ID
from modules.telegram import send_telegram_message

app = Flask(__name__)

@app.route(f"/{os.environ['TELEGRAM_BOT_TOKEN']}", methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if 'message' not in data:
        return {'status': 'ignored'}

    chat_id = str(data['message']['chat']['id'])
    user_message = data['message'].get('text', '')

    # Only respond to authorized chat
    if chat_id != os.environ['TELEGRAM_CHAT_ID']:
        return {'status': 'unauthorized'}

    command = parse_command(user_message)

    if command == "/수익":
        send_telegram_message(chat_id, "📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요.")
        report = generate_btc_report()
        send_telegram_message(chat_id, report)

    elif command == "/예측":
        send_telegram_message(chat_id, "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")

    elif command == "/일정":
        schedule_message = generate_schedule_message()
        send_telegram_message(chat_id, schedule_message)

    return {'status': 'success'}

@app.route("/report", methods=['GET'])
def test_report():
    return generate_btc_report()

if __name__ == '__main__':
    start_scheduler()
    app.run(host='0.0.0.0', port=5000)
