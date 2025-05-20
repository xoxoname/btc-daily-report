from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import build_report
from modules.utils import kr_now_str
from modules.bitget_api import get_profit_summary

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="비트코인 예측 봇에 오신 것을 환영합니다!")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    # 예측 리포트 텍스트(예시)
    msg = f"📡 GPT 매동 예측 분석 리포트\n📅 작성 시각: 실시간\n━━━━━━━━━━━━━━━━━━━\n(이하 생략)"
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    profit = get_profit_summary()
    if not profit:
        msg = "❗️비트겟 API 오류: 실시간 자산/포지션을 가져올 수 없습니다."
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return
    msg = f"""💰 현재 수익 현황 요약
📅 작성 시각: {kr_now_str()}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
- 종목: {profit['종목']}
- 방향: {profit['방향']}
- 진입가: {profit['진입가']} / 현재가: {profit['현재가']}
- 레버리지: {profit['레버리지']}
- 청산가: {profit['청산가']}
- 청산까지 남은 거리: {profit['청산까지 남은 거리']}
━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: {profit['미실현 손익']}
- 실현 손익: {profit['실현 손익']}
- 진입 자산: {profit['진입 자산']}
- 수익률: {profit['수익률']}
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
오늘 수익이 적다고 아쉬워 마세요. 한 번의 승리가 내일의 기회를 만듭니다! 😊
━━━━━━━━━━━━━━━━━━━"""
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_report(update, context)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"📅 작성 시각: {kr_now_str()}\n📡 예정 주요 이벤트\n- 2025-05-19 21:00: FOMC 결과 발표 예정 (변동성 경고)\n- 2025-05-21 18:00: 비트코인 현물 ETF 심사 마감 예정"
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_report(update, context)

def run_telegram_bot():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", handle_report))
    application.add_handler(CommandHandler("profit", handle_profit))
    application.add_handler(CommandHandler("forecast", handle_forecast))
    application.add_handler(CommandHandler("schedule", handle_schedule))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.run_polling()

# 스케줄러에서 호출할 수 있게 별도 함수로 제공!
def send_report():
    # 직접 텔레그램 전송(비동기 루프에서 실행 필요)
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(handle_report(
        Update.de_json({"message":{"chat":{"id":TELEGRAM_CHAT_ID}}}, None),
        None  # 실제 context 생성/전달 필요. 여기선 생략
    ))

def send_exception():
    # 예외 알림 전송
    pass  # 필요 시 구현
