from flask import Flask, request
from modules.schedule import start_scheduler
from modules.utils import send_telegram_message
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

app = Flask(__name__)
start_scheduler()

@app.route("/")
def index():
    return "✅ BTC 리포트 서버 실행 중"

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "no content"

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "").strip()

    if str(chat_id) != TELEGRAM_CHAT_ID:
        return "unauthorized"

    if text == "/리포트":
        send_telegram_message("📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")
    elif text == "/수익":
        send_telegram_message("🔍 수익 분석 준비 중입니다.")
    elif text == "/예측":
        send_telegram_message("🔮 예측 분석 처리 중입니다.")
    elif text == "/일정":
        send_telegram_message("📅 주요 경제 일정 분석 준비 중입니다.")
    else:
        send_telegram_message("❓ 지원하지 않는 명령어입니다.")

    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
