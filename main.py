from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message
from modules.report import handle_profit_command, handle_prediction_command, handle_report_command, handle_schedule_command

app = Flask(__name__)
start_scheduler()

@app.route("/")
def index():
    return "BTC Daily Report is running."

@app.route("/report", methods=["GET"])
def report_endpoint():
    return {
        "message": "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.",
        "status": "success"
    }

@app.route(f"/{os.environ.get('TELEGRAM_TOKEN')}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if "message" not in data:
        return "no message", 200

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if str(chat_id) != os.environ.get("TELEGRAM_CHAT_ID"):
        return "unauthorized", 403

    if text.startswith("/수익"):
        handle_profit_command()
    elif text.startswith("/예측"):
        handle_prediction_command()
    elif text.startswith("/리포트"):
        handle_report_command()
    elif text.startswith("/일정"):
        handle_schedule_command()
    else:
        send_telegram_message("❓ 지원하지 않는 명령어입니다.\n\n사용 가능 명령어: /수익 /예측 /리포트 /일정")

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
