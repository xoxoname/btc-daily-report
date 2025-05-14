import os
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 텔레그램 환경변수
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# 실시간 리포트 데이터 URL
REPORT_URL = "https://btc-daily-report.onrender.com/report"

app = Flask(__name__)

def krw(value):
    return f"{int(value * 1350):,}원"

def format_profit(data):
    try:
        equity = data["bitgetAccount"]["equity"]
        pnl = data["pnl"]
        rate = data["profitRate"]
        deposit = data["netDeposit"]
        realized = data["realizedPnL"]
        unrealized = data["unrealizedPnL"]
        now = data["timestamp"]

        return (
            f"📊 *BTC 수익 요약*\n"
            f"총자산: {equity:.2f} USDT ({krw(equity)})\n"
            f"누적 입금: {deposit:.2f} USDT ({krw(deposit)})\n"
            f"총 손익: {pnl:.2f} USDT ({krw(pnl)})\n"
            f"수익률: {rate}\n"
            f"실현 손익: {realized:.2f} USDT / 미실현 손익: {unrealized:.2f} USDT\n"
            f"⏱ 업데이트: {now}"
        )
    except Exception as e:
        return f"⚠️ 수익 리포트 파싱 오류: {e}"

def format_forecast(data):
    try:
        forecast = data["forecast12h"]
        tech = data["technical"]
        senti = data["sentiment"]
        events = data["marketEvents"]
        now = data["timestamp"]

        return (
            f"📈 *BTC 매동 예측 (12H)*\n"
            f"상승 확률: {forecast['upProbability']} / 하락 확률: {forecast['downProbability']}\n"
            f"🔍 예측 사유: {forecast['reason']}\n\n"
            f"📊 기술 분석: {tech}\n"
            f"🧠 심리 지표: {senti}\n"
            f"🗞 시장 이벤트: {events}\n"
            f"⏱ 분석 시각: {now}\n\n"
            f"💡 다음 12시간 대응 전략을 참고해 주세요!"
        )
    except Exception as e:
        return f"⚠️ 예측 리포트 파싱 오류: {e}"

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get(REPORT_URL)
    data = res.json()
    msg = format_profit(data)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = requests.get(REPORT_URL)
    data = res.json()
    msg = format_forecast(data)
    await update.message.reply_text(msg, parse_mode="Markdown")

# Flask에서 / 로크 확인
@app.route("/")
def index():
    return "BTC 리포트 텔레그램 봇 작동 중입니다."

# Telegram 봇 실행
if __name__ == "__main__":
    from threading import Thread

    def run_telegram_bot():
        app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
        app_bot.add_handler(CommandHandler("수익", handle_profit))
        app_bot.add_handler(CommandHandler("예측", handle_forecast))
        app_bot.run_polling()

    Thread(target=run_telegram_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
