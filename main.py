from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message, get_profit_report_text

app = Flask(__name__)
start_scheduler()

@app.route('/')
def home():
    return "✅ BTC Report System is running."

@app.route(f'/{os.environ["TELEGRAM_BOT_TOKEN"]}', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if chat_id != int(os.environ["TELEGRAM_CHAT_ID"]):
        return "Unauthorized", 403

    if text == "/수익":
        send_telegram_message("📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요.")
        report = get_profit_report_text()
        send_telegram_message(report)
    else:
        send_telegram_message("지원하지 않는 명령어입니다.")

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
