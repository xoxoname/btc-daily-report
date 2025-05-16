from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message, get_profit_report_text, get_prediction_report_text, get_schedule_report_text

app = Flask(__name__)
start_scheduler()

@app.route('/')
def home():
    return 'BTC 리포트 서비스 실행 중'

@app.route(f"/{os.environ['TELEGRAM_BOT_TOKEN']}", methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if str(chat_id) != os.environ["TELEGRAM_CHAT_ID"]:
        return "unauthorized", 403

    if text.startswith("/수익"):
        send_telegram_message(f"📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요.")
        send_telegram_message(get_profit_report_text())

    elif text.startswith("/예측"):
        send_telegram_message(f"📡 예측 분석 준비 중입니다...\n잠시만 기다려 주세요.")
        send_telegram_message(get_prediction_report_text())

    elif text.startswith("/일정"):
        send_telegram_message(get_schedule_report_text())

    else:
        send_telegram_message("❓ 지원하지 않는 명령어입니다. /수익 /예측 /일정 중 선택해 주세요.")
    
    return "ok", 200

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
