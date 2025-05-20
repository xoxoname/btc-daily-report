import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from modules.constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from modules.report import build_report
from modules.utils import kr_now_str

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="비트코인 예측 봇에 오신 것을 환영합니다!")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    # 아래는 실제 데이터 분석/수집/요약(GPT) 파트와 연결 필요
    user_prompt = "실시간 BTC 시장 리포트 및 전략 분석을 아래 항목 순서대로 한국어로 작성: ..."
    market_data = ["ETF 승인 이슈 없음 → 호재", "FOMC 8시간 전 대기 중 → 악재 예상"]
    tech_data = ["현재가: $66,210", "RSI(4H): 61.5 (중립 강세) → 호재"]
    psych_data = ["펀딩비: +0.012% (롱 과열) → 호재", "공포탐욕지수: 71 (탐욕) → 호재"]
    forecast = ["상승 확률: 62%", "전략: 분할 매수/익절"]
    alerts = ["Whale Alert: 1,000 BTC 이체 감지 → 호재"]
    prev_check = ["5/17 23:00 횡보 예측 → 변동폭 ±0.9% → ✅ 적중"]
    pnl = {"진입 자산": "$2,000", "미실현 손익": "+$81.0 (11.0만원)", "실현 손익": "+$24.3 (3.3만원)", "금일 총 수익": "+$105.3 (14.3만원)", "수익률": "+5.26%"}
    msg = build_report(market_data, tech_data, psych_data, forecast, alerts, prev_check, pnl, user_prompt)
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 실제 포지션, 손익 수집 → 분석 후 리포트로 변환
    await handle_report(update, context)

async def handle_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_report(update, context)

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 스케줄 안내 메시지
    msg = f"📅 작성 시각: {kr_now_str()}\n📡 예정 주요 이벤트\n- 2025-05-19 21:00: FOMC 결과 발표 예정 (변동성 경고)\n- 2025-05-21 18:00: 비트코인 현물 ETF 심사 마감 예정"
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 자연어 질의도 모두 /report로 안내
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

async def send_report():
    # 정규 스케줄러에서 호출, 예시 메시지
    await handle_report(Update.de_json({"message":{"chat":{"id":TELEGRAM_CHAT_ID}}}, None), ContextTypes.DEFAULT_TYPE)

async def send_exception():
    # 예외 감지/긴급 알림 (5분마다)
    # 실제 예외 탐지 시 아래 메시지 수정
    msg = f"🚨 [BTC 예외 리포트] {kr_now_str()}\n❗ Whale Alert: 3,200 BTC 이체 감지\n📉 최근 10분 간 -2.3% 급락\n📌 GPT 판단: 공포 유입, 유동성 위축\n👉 향후 2시간 내 추가 하락 확률↑\n━━━━━━━━━━━━━━━━━━━\n※ 포지션 관리 강화, 레버리지 축소 권고"
    # Send only if critical event is detected!
    pass
