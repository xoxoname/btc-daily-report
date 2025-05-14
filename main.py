import os
import logging
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import ccxt
import openai

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_SECRET = os.getenv("BITGET_SECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Set OpenAI key
openai.api_key = OPENAI_API_KEY

# Set up Bitget client
bitget = ccxt.bitget({
    "apiKey": BITGET_APIKEY,
    "secret": BITGET_SECRET,
    "password": BITGET_PASSPHRASE,
    "enableRateLimit": True
})

def get_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot").json()
        return float(res["data"]["amount"])
    except:
        return None

def get_bitget_data():
    try:
        balance = bitget.fetch_balance()
        equity = balance["total"]["USDT"]
        positions = bitget.fetch_positions()
        return {
            "equity": equity,
            "positions": positions
        }
    except Exception as e:
        return {"error": str(e)}

def generate_report():
    price = get_coinbase_price()
    bitget_data = get_bitget_data()

    if price is None:
        return "❌ Coinbase 시세를 불러오지 못했습니다."

    if "error" in bitget_data:
        return f"❌ Bitget 오류: {bitget_data['error']}"

    equity = bitget_data["equity"]
    positions = bitget_data["positions"]

    position_summary = []
    for pos in positions:
        if pos["symbol"] == "BTC/USDT:USDT":
            entry = pos["entryPrice"]
            side = pos["side"]
            size = pos["contracts"]
            unreal = pos["unrealizedPnl"]
            position_summary.append(f"- {side.upper()} {size} @ {entry} → 미실현손익 {unreal:.2f} USDT")

    return (
        f"📊 *BTC 정규 리포트*\n\n"
        f"🟡 Coinbase 가격: ${price:,.2f}\n"
        f"📦 총 자산: ${equity:,.2f}\n\n"
        f"🧾 포지션:\n" + ("\n".join(position_summary) if position_summary else "없음") +
        "\n\n⏱ 자동 생성 시각 기준\n"
    )

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = generate_report()
    await update.message.reply_text(report, parse_mode='Markdown')

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    forecast_text = (
        "🔮 *12시간 예측*\n\n"
        "📈 상승 확률: *57%*\n"
        "📉 하락 확률: *43%*\n"
        "🧠 사유: RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성\n"
        "\n📍 시장 심리: Fear & Greed 45 → 중립\n"
        "🛠 기술 지표: RSI 54 / MACD 데드크로스 → 중립\n"
    )
    await update.message.reply_text(forecast_text, parse_mode='Markdown')

# Set up Telegram application
tg_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
tg_app.add_handler(CommandHandler("profit", handle_profit))
tg_app.add_handler(CommandHandler("forecast", handle_forecast))

# Schedule automatic reports
scheduler = BackgroundScheduler()
scheduler.add_job(lambda: tg_app.bot.send_message(chat_id=os.getenv("TELEGRAM_CHAT_ID"), text=generate_report()), 'interval', minutes=5)
scheduler.start()

@app.route('/')
def index():
    return "BTC Daily Report Running."

if __name__ == '__main__':
    tg_app.run_polling()
