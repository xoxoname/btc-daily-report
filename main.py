import os
import json
from flask import Flask, jsonify
from report import get_profit_report, format_profit_report_text, get_prediction_report, format_prediction_report_text
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from datetime import datetime
import pytz

# 환경 변수 세팅
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TZ = pytz.timezone("Asia/Seoul")

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

# 리포트 전송 함수
def send_all_reports():
    profit = get_profit_report()
    prediction = get_prediction_report()

    profit_msg = format_profit_report_text(profit)
    prediction_msg = format_prediction_report_text(prediction)

    final_msg = "\n".join(["\ud83c\udf1f *BTC 실시간 보고서*", profit_msg, prediction_msg])
    bot.send_message(chat_id=CHAT_ID, text=final_msg, parse_mode="Markdown")

@app.route("/report")
def report():
    report = get_profit_report()
    return jsonify(report)

# 스케줄링: 매일 9:00, 13:00, 23:00 (KST 기준)
scheduler = BackgroundScheduler(timezone=TZ)
scheduler.add_job(send_all_reports, "cron", hour=9, minute=0)
scheduler.add_job(send_all_reports, "cron", hour=13, minute=0)
scheduler.add_job(send_all_reports, "cron", hour=23, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
