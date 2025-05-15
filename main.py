# main.py

import os
import logging
from datetime import datetime
import pytz
import requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# 리포트 모듈
from modules.report import (
    get_profit_report,
    format_profit_report_text,
    get_prediction_report,
    format_prediction_report_text,
)
# 일정 모듈
from modules.schedule import (
    get_upcoming_events,
    format_schedule_text,
)

# ── 환경변수 로드 ───────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")       # 봇 토큰
DEFAULT_CHAT_ID = os.getenv("CHAT_ID")            # 스케줄용 Chat ID
APP_URL        = os.getenv("APP_URL")             # ex) https://btc-daily-report.onrender.com
# ───────────────────────────────────────────────────────

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

# Flask 앱 초기화
app = Flask(__name__)

# ── 자동으로 Telegram Webhook 등록 ─────────────────────
def register_webhook():
    if not TELEGRAM_TOKEN or not APP_URL:
        logging.warning("WEBHOOK 등록에 필요한 TELEGRAM_TOKEN 또는 APP_URL 이 없습니다.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        resp = requests.post(url, json={"url": f"{APP_URL}/bot"})
        logging.info(f"Webhook 등록 결과: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Webhook 등록 실패: {e}")

# 배포 시 worker 가 로드될 때 한 번만 실행
register_webhook()
# ───────────────────────────────────────────────────────

def send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    })
    if resp.status_code != 200:
        logging.error(f"텔레그램 전송 실패 ({resp.status_code}): {resp.text}")
    else:
        logging.info(f"텔레그램 전송 성공: chat_id={chat_id}")

def create_full_report() -> str:
    kst = pytz.timezone("Asia/Seoul")
    now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M")
    # 1) 수익/포지션
    profit_data = get_profit_report()
    profit_section = format_profit_report_text(profit_data)
    # 2) 예측
    pred_data = get_prediction_report()
    pred_section = format_prediction_report_text(pred_data)
    header = f"📢 *GPT 매동 예측 예상*\n{now_str} 기준\n\n"
    return header + profit_section + "\n\n" + pred_section

def handle_report(chat_id: int):
    send_message(chat_id, "🔎 자료 검색 중… 잠시만 기다려주세요.")
    text = create_full_report()
    send_message(chat_id, text)

def handle_schedule(chat_id: int):
    send_message(chat_id, "🔎 일정 정보 수집 중… 잠시만 기다려주세요.")
    events = get_upcoming_events()
    text = format_schedule_text(events)
    send_message(chat_id, text)

# ── 스케줄러: 매일 09:00, 13:00, 23:00 (KST) 자동 리포트 ─────────
scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(lambda: handle_report(int(DEFAULT_CHAT_ID)), "cron", hour=9,  minute=0)
scheduler.add_job(lambda: handle_report(int(DEFAULT_CHAT_ID)), "cron", hour=13, minute=0)
scheduler.add_job(lambda: handle_report(int(DEFAULT_CHAT_ID)), "cron", hour=23, minute=0)
scheduler.start()
# ───────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return "OK"

@app.route("/bot", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    if not update or "message" not in update:
        return "OK"
    msg     = update["message"]
    chat_id = msg["chat"]["id"]
    text    = msg.get("text", "").strip()

    if text.startswith("/report") or "리포트" in text:
        handle_report(chat_id)
    elif text.startswith("/일정"):
        handle_schedule(chat_id)
    else:
        send_message(chat_id, "⚡️ 지원하는 명령어: /report, /일정")
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
