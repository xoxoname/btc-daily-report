import os
from telegram.ext import Application, CommandHandler
import logging

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def start(update, context):
    await update.message.reply_text("✅ 봇이 정상적으로 실행되었습니다! /profit 명령어를 입력해 테스트해보세요.")

async def profit(update, context):
    await update.message.reply_text("💰 수익 리포트 샘플\n- (여기에 비트겟 연동 결과가 표시됩니다.)")

def run_telegram_bot():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profit", profit))
    app.run_polling()
