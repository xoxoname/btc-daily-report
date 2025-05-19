from telegram.ext import Application, CommandHandler
import os
import asyncio
from modules.bitget import BitgetClient
from modules.reporter import format_profit_report

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def profit(update, context):
    try:
        positions = BitgetClient.get_positions()
        wallet = BitgetClient.get_wallet()
        msg = format_profit_report(positions, wallet)
    except Exception as e:
        msg = f"수익 정보 조회 오류: {str(e)}"
    await update.message.reply_text(msg)

app.add_handler(CommandHandler("profit", profit))

def run_telegram_bot():
    asyncio.run(app.run_polling())
