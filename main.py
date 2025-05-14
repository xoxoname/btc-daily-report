import os
import threading
import time
from flask import Flask, jsonify
import requests
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = Flask(__name__)

# 환경변수
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
REPORT_URL = os.environ.get("REPORT_URL", "https://btc-daily-report.onrender.com/report")

# 텔레그램 핸들러
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(REPORT_URL)
        data = response.json()

        equity = data["bitgetAccount"]["equity"]
        pnl = data["pnl"]
        rate = data["profitRate"]
        krw_pnl = round(pnl * 1370)
        krw_equity = round(equity * 1370)

        await update.message.reply_text(
            f"📈 *실시간 수익 요약*\n"
            f"총 자산: ${equity:.2f} ({krw_equity:,}원)\n"
            f"수익: ${pnl:.2f} ({krw_pnl:,}원)\n"
            f"수익률: {rate}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❗️수익 정보를 불러오는 중 오류 발생: {e}")

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(REPORT_URL)
        data = response.json()

        forecast = data["forecast12h"]
        technical = data["technical"]
        sentiment = data["sentiment"]
        events = data["marketEvents"]
        up = forecast["upProbability"]
        down = forecast["downProbability"]
        reason = forecast["reason"]

        await update.message.reply_text(
            f"🧠 *BTC 12시간 예측 리포트*\n\n"
            f"예상 상승 확률: {up}\n"
            f"예상 하락 확률: {down}\n"
            f"📌 근거: {reason}\n\n"
            f"📊 기술적 지표: {technical}\n"
            f"🧭 심리 지표: {sentiment}\n"
            f"🗞️ 시장 뉴스: {events}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❗️예측 정보를 불러오는 중 오류 발생: {e}")

# 텔레그램 봇 실행 (별도 스레드)
def run_telegram_bot():
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 슬래시 명령어 등록 (한글 그대로 사용 가능하게)
    app_bot.bot.set_my_commands([
        BotCommand("수익", "현재 실시간 수익 요약을 확인합니다."),
        BotCommand("예측", "BTC 12시간 예측 리포트를 받아봅니다."),
    ])

    app_bot.add_handler(CommandHandler("수익", handle_profit))
    app_bot.add_handler(CommandHandler("예측", handle_forecast))

    app_bot.run_polling()

threading.Thread(target=run_telegram_bot, daemon=True).start()

# /report API - 테스트용 리포트 응답
@app.route("/report")
def report():
    return jsonify({
        "BTC_USD_spot": 104176.06,
        "bitgetAccount": {
            "equity": 4452.10,
            "openPositions": [
                {
                    "entryPrice": 103372.69,
                    "side": "long",
                    "size": 0.145,
                    "symbol": "BTC/USDT:USDT",
                    "unrealized": 107.55
                }
            ],
            "unrealized": 107.55,
            "error_balance": None
        },
        "forecast12h": {
            "downProbability": "43%",
            "upProbability": "57%",
            "reason": "RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성"
        },
        "technical": "RSI 54 / MACD 데드크로스 → 중립",
        "sentiment": "Fear & Greed 45 → ⚪️ 중립",
        "marketEvents": "📉 ETF / CPI 관련 뉴스 없음",
        "netDeposit": 3961.28,
        "pnl": 490.83,
        "profitRate": "12.39%",
        "realizedPnL": 0,
        "unrealizedPnL": 0,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# 기본 페이지
@app.route("/")
def home():
    return "BTC Daily Report Server is Running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
