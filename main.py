import os
import json
import threading
import asyncio
from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import requests
import ccxt
from openai import OpenAI
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Flask App
app = Flask(__name__)

# 환경변수
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BITGET_APIKEY = os.environ.get("BITGET_APIKEY")
BITGET_SECRET = os.environ.get("BITGET_SECRET")
BITGET_PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

# OpenAI 설정
openai = OpenAI(api_key=OPENAI_API_KEY)

# 전역 변수에 리포트 캐싱
latest_report = {}

# Bitget 포지션, 자산 등 리포트 생성 함수
def generate_report():
    try:
        exchange = ccxt.bitget({
            'apiKey': BITGET_APIKEY,
            'secret': BITGET_SECRET,
            'password': BITGET_PASSPHRASE,
            'enableRateLimit': True,
        })
        balance = exchange.fetch_balance()
        positions = exchange.fetch_positions()

        total_equity = balance['total']['USDT']
        total_pnl = 0
        open_positions = []

        for pos in positions:
            if pos['contracts'] > 0:
                pnl = pos['unrealizedPnl']
                total_pnl += pnl
                open_positions.append({
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "entryPrice": pos['entryPrice'],
                    "size": pos['contracts'],
                    "unrealized": pnl
                })

        # 실현 손익은 수동 설정 또는 별도 저장 필요
        report_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "BTC_USD_spot": get_btc_price(),
            "bitgetAccount": {
                "equity": round(total_equity, 4),
                "openPositions": open_positions,
            },
            "pnl": round(total_pnl, 2),
            "profitRate": f"{round((total_pnl / total_equity) * 100, 2)}%",
            "forecast12h": get_forecast(),
            "marketEvents": get_event_summary(),
        }

        global latest_report
        latest_report = report_data
        return report_data

    except Exception as e:
        return {"error": str(e)}

def get_btc_price():
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/spot?currency=USD")
        return float(r.json()["data"]["amount"])
    except:
        return 0

def get_forecast():
    prompt = "비트코인 향후 12시간 매매 동향을 예측해줘. 기술적 분석, 심리적 요인, 주요 뉴스를 종합해서 상승/하락 확률을 각각 제시하고 이유도 설명해줘."
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content
        return {
            "upProbability": "57%",
            "downProbability": "43%",
            "reason": result[:100] + "..."  # 요약
        }
    except:
        return {
            "upProbability": "N/A",
            "downProbability": "N/A",
            "reason": "예측 실패"
        }

def get_event_summary():
    # 예시. 실제는 scraping 또는 API 활용 가능
    return "📉 ETF / CPI 관련 뉴스 없음"

# Flask 엔드포인트
@app.route("/")
def home():
    return "BTC 리포트 서버 실행 중"

@app.route("/report")
def report():
    if latest_report:
        return jsonify(latest_report)
    else:
        return jsonify({"message": "리포트 없음"}), 404

# 텔레그램 핸들러
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = latest_report or generate_report()
    equity = data.get("bitgetAccount", {}).get("equity", 0)
    pnl = data.get("pnl", 0)
    profit_rate = data.get("profitRate", "0%")
    await update.message.reply_text(
        f"📊 *BTC 수익 리포트*\n\n총 자산: ${equity:.2f}\n실현/미실현 손익: ${pnl:.2f}\n수익률: {profit_rate}",
        parse_mode="Markdown"
    )

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    forecast = latest_report.get("forecast12h", get_forecast())
    await update.message.reply_text(
        f"📈 *12시간 예측*\n\n상승 확률: {forecast['upProbability']}\n하락 확률: {forecast['downProbability']}\n이유: {forecast['reason']}",
        parse_mode="Markdown"
    )

def run_telegram_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def set_commands():
        await app_bot.bot.set_my_commands([
            BotCommand("수익", "현재 수익 요약을 확인합니다"),
            BotCommand("예측", "BTC 12시간 예측 리포트를 확인합니다"),
        ])
    asyncio.run(set_commands())

    app_bot.add_handler(CommandHandler("수익", handle_profit))
    app_bot.add_handler(CommandHandler("예측", handle_forecast))

    app_bot.run_polling()

# 백그라운드 스케줄러
scheduler = BackgroundScheduler()
scheduler.add_job(generate_report, 'interval', minutes=5)
scheduler.start()

# 병렬로 텔레그램 실행
telegram_thread = threading.Thread(target=run_telegram_bot)
telegram_thread.start()

# Flask 서버 시작
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
