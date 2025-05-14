import os
import ccxt
import json
import asyncio
import requests
from flask import Flask, jsonify
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# 환경변수 설정
BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_APISECRET = os.getenv("BITGET_APISECRET")
BITGET_APIPASSWORD = os.getenv("BITGET_APIPASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # ex: '@zzzzzzzz5555'

app = Flask(__name__)
scheduler = BackgroundScheduler()
report_data = {}

def generate_report():
    global report_data
    try:
        exchange = ccxt.bitget({
            'apiKey': BITGET_APIKEY,
            'secret': BITGET_APISECRET,
            'password': BITGET_APIPASSWORD,
            'enableRateLimit': True,
        })

        btc_price = ccxt.coinbase().fetch_ticker('BTC/USDT')['last']
        balance = exchange.fetch_balance()
        equity = balance['total'].get('USDT', 0)
        positions = exchange.fetch_positions()
        position = next((p for p in positions if p['symbol'] == 'BTC/USDT:USDT'), None)

        entry_price = position['entryPrice'] if position else 0
        size = position['contracts'] if position else 0
        side = position['side'] if position else ""
        unrealized = position['unrealizedPnl'] if position else 0

        deposit = 3961.28
        pnl = equity - deposit
        profit_rate = f"{(pnl / deposit) * 100:.2f}%" if deposit > 0 else "0.00%"

        forecast = {
            "upProbability": "57%",
            "downProbability": "43%",
            "reason": "RSI 중립 / MACD 약세 / 롱포 과열 없음 → 제한적 상승 가능성"
        }

        sentiment = "Fear & Greed 45 → ⚪ 중립"
        technical = "RSI 54 / MACD 데드크로스 → ⚪ 중립"
        events = "📉 ETF / CPI 관련 뉴스 없음"

        report_data = {
            "BTC_USD_spot": btc_price,
            "bitgetAccount": {
                "equity": equity,
                "openPositions": [{
                    "entryPrice": entry_price,
                    "side": side,
                    "size": size,
                    "symbol": "BTC/USDT:USDT",
                    "unrealized": unrealized
                }],
                "error_balance": "",
            },
            "netDeposit": deposit,
            "pnl": round(pnl, 2),
            "profitRate": profit_rate,
            "unrealizedPnL": 0,
            "realizedPnL": 0,
            "forecast12h": forecast,
            "sentiment": sentiment,
            "technical": technical,
            "marketEvents": events,
            "exceptionsRealtime": [],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return report_data
    except Exception as e:
        return {"error": str(e)}

@app.route("/")
def index():
    return "BTC Daily Report Service Running"

@app.route("/report")
def report():
    return jsonify(report_data)

# 텔레그램 핸들러
async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = report_data or generate_report()
    msg = f"""📊 *실시간 수익 요약*\n
총 자산: ${report['bitgetAccount']['equity']:.2f}
수익: ${report['pnl']:.2f}
수익률: {report['profitRate']}

진입가: ${report['bitgetAccount']['openPositions'][0]['entryPrice']:.2f}
포지션: {report['bitgetAccount']['openPositions'][0]['side']}
규모: {report['bitgetAccount']['openPositions'][0]['size']}

({report['timestamp']})
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = report_data or generate_report()
    msg = f"""🔮 *BTC 12시간 예측*\n
상승 확률: {report['forecast12h']['upProbability']}
하락 확률: {report['forecast12h']['downProbability']}
이유: {report['forecast12h']['reason']}

📈 기술적 지표: {report['technical']}
🧠 심리 지표: {report['sentiment']}
📰 뉴스: {report['marketEvents']}

({report['timestamp']})
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

# 정기 리포트 전송
async def send_scheduled_report():
    try:
        report = generate_report()
        text = f"""📊 *정기 BTC 리포트 ({report['timestamp']})*\n
총 자산: ${report['bitgetAccount']['equity']:.2f}
수익: ${report['pnl']:.2f}
수익률: {report['profitRate']}

📈 *12시간 예측*
상승 확률: {report['forecast12h']['upProbability']}
하락 확률: {report['forecast12h']['downProbability']}
이유: {report['forecast12h']['reason']}

📰 주요 뉴스: {report['marketEvents']}
"""
        await app_bot.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode='Markdown')
    except Exception as e:
        print(f"[ERROR] 자동 리포트 전송 실패: {e}")

def schedule_reports():
    times = ['09:00', '13:00', '23:00']
    for t in times:
        hour, minute = map(int, t.split(':'))
        scheduler.add_job(lambda: asyncio.run(send_scheduled_report()),
                          'cron', hour=hour, minute=minute)

def run_telegram_bot():
    global app_bot
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def set_commands():
        await app_bot.bot.set_my_commands([
            BotCommand("수익", "현재 수익 요약"),
            BotCommand("예측", "BTC 12시간 예측"),
        ])
    asyncio.run(set_commands())

    app_bot.add_handler(CommandHandler("수익", handle_profit))
    app_bot.add_handler(CommandHandler("예측", handle_forecast))

    schedule_reports()
    app_bot.run_polling()

if __name__ == "__main__":
    scheduler.add_job(generate_report, 'interval', minutes=5)
    scheduler.start()
    import threading
    threading.Thread(target=run_telegram_bot).start()
    app.run(host='0.0.0.0', port=10000)
