import os
import json
import requests
from flask import Flask, jsonify
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from report import get_profit_report, format_profit_report_text, get_prediction_report, format_prediction_report_text

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TELEGRAM_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

KST = timezone(timedelta(hours=9))

def send_telegram_message(message):
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

def send_profit_report():
    try:
        profit_data = get_profit_report()
        message = format_profit_report_text(profit_data)
        send_telegram_message(message)
    except Exception as e:
        send_telegram_message(f"[오류] 수익 리포트 전송 실패: {e}")

def send_prediction_report():
    try:
        prediction_data = get_prediction_report()
        message = format_prediction_report_text(prediction_data)
        send_telegram_message(message)
    except Exception as e:
        send_telegram_message(f"[오류] 예측 리포트 전송 실패: {e}")

@app.route("/report")
def report():
    try:
        profit_data = get_profit_report()
        return jsonify(profit_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

scheduler = BackgroundScheduler(timezone=KST)
scheduler.add_job(send_profit_report, "interval", minutes=5)
scheduler.add_job(send_prediction_report, "cron", hour=9, minute=0)
scheduler.add_job(send_prediction_report, "cron", hour=13, minute=0)
scheduler.add_job(send_prediction_report, "cron", hour=23, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
