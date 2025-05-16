from flask import Flask, request
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.schedule import start_scheduler
from modules.emergency import start_emergency_monitor
from modules.report import build_and_send_report
import telegram

bot = telegram.Bot(token=TELEGRAM_TOKEN)

app = Flask(__name__)

@app.route("/")
def index():
    return "BTC Daily Report Bot is running."

@app.route("/수익", methods=["GET", "POST"])
def handle_profit():
    build_and_send_report()
    return "Profit report sent."

@app.route("/예측", methods=["GET", "POST"])
def handle_prediction():
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")
    return "Prediction response sent."

@app.route("/리포트", methods=["GET", "POST"])
def handle_report():
    build_and_send_report()
    return "Full report sent."

@app.route("/일정", methods=["GET", "POST"])
def handle_schedule():
    message = (
        "📅 정규 리포트 전송 시간\n"
        "- 오전 9:30 (KST, UTC+9)\n"
        "- 오후 1:00 (KST, UTC+9)\n"
        "- 오후 11:00 (KST, UTC+9)"
    )
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    return "Schedule sent."

if __name__ == "__main__":
    start_scheduler()
    start_emergency_monitor()
    app.run(host="0.0.0.0", port=10000)
