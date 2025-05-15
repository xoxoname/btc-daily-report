import os
import logging
from datetime import datetime
import pytz
import requests
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

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
from modules.constants import TELEGRAM_TOKEN, CHAT_ID, APP_URL
from modules.utils import send_message

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

# Flask 앱 초기화
app = Flask(__name__)

# 텔레그램 Webhook 등록 함수
def register_webhook():
    if not TELEGRAM_TOKEN or not APP_URL:
        logging.warning("Missing TELEGRAM_TOKEN or APP_URL for webhook registration.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        resp = requests.post(url, json={"url": f"{APP_URL}/bot"})
        logging.info(f"Webhook 등록 결과: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Webhook 등록 실패: {e}")

# 리포트 생성 함수
def create_full_report() -> str:
    kst = pytz.timezone("Asia/Seoul")
    now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
    header = f"📢 *GPT 매동 예측 예상*\n{now_str} 기준\n\n"

    profit = get_profit_report()
    profit_text = format_profit_report_text(profit)

    prediction = get_prediction_report()
    prediction_text = format_prediction_report_text(prediction)

    return header + profit_text + "\n\n" + prediction_text

# 리포트 전송
def handle_report(chat_id: int):
    send_message(chat_id, "🔎 자료 검색 중… 잠시만 기다려주세요.")
    try:
        report_text = create_full_report()
        send_message(chat_id, report_text)
    except Exception as e:
        logging.exception("리포트 생성 실패")
        send_message(chat_id, f"⚠️ 리포트 생성 중 오류가 발생했습니다.\n{e}")

# 일정 전송
def handle_schedule(chat_id: int):
    send_message(chat_id, "🔎 일정 정보 수집 중… 잠시만 기다려주세요.")
    try:
        events = get_upcoming_events()
        schedule_text = format_schedule_text(events)
        send_message(chat_id, schedule_text)
    except Exception as e:
        logging.exception("일정 전송 실패")
        send_message(chat_id, f"⚠️ 일정 수집 중 오류가 발생했습니다.\n{e}")

# 스케줄 설정
scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=9,  minute=0)
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=13, minute=0)
scheduler.add_job(lambda: handle_report(int(CHAT_ID)), 'cron', hour=23, minute=0)
scheduler.start()

# 기본 라우트
@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok"})

# JSON API
@app.route("/report", methods=["GET"])
def report_api():
    try:
        profit = get_profit_report()
        prediction = get_prediction_report()
        return jsonify({
            "data": {
                "price": profit.get("price", "N/A"),
                "usdt_pnl": profit.get("usdt_pnl", "N/A"),
                "krw_pnl": profit.get("krw_pnl", "N/A"),
                "summary": prediction[:200] + "..." if prediction else None
            },
            "message": "Report ready",
            "status": "ready"
        })
    except Exception as e:
        logging.exception("/report API 실패")
        return jsonify({"status": "error", "message": str(e)}), 500

# Telegram Webhook
@app.route("/bot", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    msg = update.get("message")
    if not msg:
        return "OK"
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text.startswith("/report") or "리포트" in text:
        handle_report(chat_id)
    elif text.startswith("/일정"):
        handle_schedule(chat_id)
    else:
        send_message(chat_id, "⚡️ 지원하는 명령어: /report, /일정")
    return "OK"

# 실행
if __name__ == "__main__":
    register_webhook()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
