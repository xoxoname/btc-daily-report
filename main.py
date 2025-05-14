# main.py

import os
import requests
import json
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REPORT_URL = "https://btc-daily-report.onrender.com/report"

openai_client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_report():
    try:
        res = requests.get(REPORT_URL)
        return res.json()
    except:
        return None

def convert_usd_to_krw(usd):
    try:
        krw_rate = 1340  # 환율 고정 또는 API 연동 가능
        return round(float(usd) * krw_rate)
    except:
        return 0

def format_krw(usd):
    krw = convert_usd_to_krw(usd)
    return f"{krw:,}원"

def build_forecast_prompt(report):
    btc_price = report.get("btc", 0)
    net_income = report.get("realized", 0)
    total_income = report.get("total", 0)
    position_count = report.get("positions", 0)
    rsi = report.get("rsi", 0)
    macd = report.get("macd", "")

    return f"""
다음 조건에 맞는 BTC 12시간 매매 예측 리포트를 작성해줘:
- BTC 가격: {btc_price}$
- RSI: {rsi}, MACD: {macd}
- 총 수익: {total_income}$ ({format_krw(total_income)})
- 실현 수익: {net_income}$ ({format_krw(net_income)})
- 포지션 수: {position_count}

조건:
1. 시장 이벤트 요약 및 분석
2. 기술적 분석 (RSI, MACD, MA, 볼린저밴드 등)
3. 심리 및 구조 지표
4. 12시간 예측 (상승/하락 확률, 전략 요약)
5. 예외 탐지 및 예측 검증
6. 모든 달러 금액은 한화 병기
7. 마지막엔 위로/멘탈 관리용 문장 추가. 수익 기준으로 편의점 알바 비교도 넣어줘
8. 한국어로 간결하고 구조적으로 써줘
"""

def build_profit_message(report):
    btc_price = report.get("btc", 0)
    realized = report.get("realized", 0)
    total = report.get("total", 0)
    balance = report.get("balance", 0)
    deposit = report.get("deposit", 0)
    positions = report.get("positions", 0)
    rsi = report.get("rsi", 0)
    macd = report.get("macd", "")

    return f"""
📊 BTC 리포트 - 현재 시각 기준
• BTC: ${btc_price}
• 순입금: {deposit} USDT ({format_krw(deposit)})
• 자산: {balance} USDT ({format_krw(balance)})
• 총 수익: {total} USDT ({format_krw(total)})
• 실현 수익: {realized} USDT ({format_krw(realized)})
• 포지션 수: {positions}
📈 분석: RSI {rsi} / MACD {macd}
"""

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = fetch_report()
    if not report:
        await update.message.reply_text("❌ 데이터를 불러오지 못했습니다.")
        return
    msg = build_profit_message(report)
    await update.message.reply_text(msg)

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = fetch_report()
    if not report:
        await update.message.reply_text("❌ 데이터를 불러오지 못했습니다.")
        return
    prompt = build_forecast_prompt(report)
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 정확하고 체계적인 크립토 매매 분석가입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    forecast = response.choices[0].message.content
    await update.message.reply_text(forecast)

def schedule_push():
    report = fetch_report()
    if not report:
        return
    prompt = build_forecast_prompt(report)
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 정확하고 체계적인 크립토 매매 분석가입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    forecast = response.choices[0].message.content
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"📌 GPT 매동 예측 예상\n\n{forecast}"
        }
    )

scheduler = BackgroundScheduler()
scheduler.add_job(schedule_push, 'cron', hour='0,4,14', minute='30')  # 한국 기준 9:30, 13:00, 23:00
scheduler.start()

if __name__ == '__main__':
    tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    tg_app.add_handler(CommandHandler("profit", handle_profit))
    tg_app.add_handler(CommandHandler("forecast", handle_forecast))
    tg_app.run_polling()

    app.run(host='0.0.0.0', port=10000)
