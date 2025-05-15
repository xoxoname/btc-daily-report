import os
import logging
from datetime import datetime
import pytz
import requests
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Import modules
from modules.report import (
    get_profit_report,
    format_profit_report_text,
    get_prediction_report,
    format_prediction_report_text,
)
from modules.schedule import (
    get_upcoming_events,
    format_schedule_text,
)

# 환경 변수
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID        = os.getenv("CHAT_ID")
APP_URL        = os.getenv("APP_URL")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# Telegram 메시지 전송 함수
def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })
    if resp.status_code != 200:
        logging.error(f"메시지 전송 실패: {resp.status_code}, {resp.text}")

# 리포트 생성
def create_full_report() -> str:
    now = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    header = f"📢 *GPT 매동 예측 예상*\n{now} 기준\n\n"
    profit_text = format_profit_report_text(get_profit_report())
    prediction_text = format_prediction_report_text(get_prediction_report())
    return header + profit_text + "\n\n" + prediction_text

# 핸들러
def handle_report(chat_id: int):
    send_message(chat_id, "🔎 자료 검색 중… 잠시만 기다려주세요.")
    send_message(chat_id, create_full_report())

def handle_schedule(chat_id: int):
    send_message(chat_id, "🔎 일정 정보 수집 중… 잠시만 기다려주세요.")
    text = format_schedule_text(get_upcoming_events())
    send_message(chat_id, text)

# Webhook 등록
def register_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        resp = requests.post(url, json={"url": f"{APP_URL}/bot"})
        logging.info(f"Webhook 등록 결과: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Webhook 등록 실패: {e}")

# 주기적 리포트 전송 스케줄링
scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=9, minute=0)
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=13, minute=0)
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=23, minute=0)
scheduler.start()

# Webhook 라우팅
@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok"})

@app.route("/bot", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    message = update.get("message")
    if not message:
        return "OK"
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text.startswith("/report") or "리포트" in text:
        handle_report(chat_id)
    elif text.startswith("/일정"):
        handle_schedule(chat_id)
    else:
        send_message(chat_id, "⚡️ 지원하는 명령어: /report, /일정")
    return "OK"

if __name__ == "__main__":
    register_webhook()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
