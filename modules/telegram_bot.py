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
    msg = f"📡 GPT 매동 예측 분석 리포트\n📅 작성 시각: 실시간\n━━━━━━━━━━━━━━━━━━━\n(이하 생략)"
    await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

async def handle_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != TELEGRAM_CHAT_ID:
        return
    profit = get_profit_summary()

    # 오류/None 반환 및 모든 오류 처리
    if not profit or "error" in profit and profit["error"]:
        err_msg = profit["error"] if profit and profit.get("error") else "비트겟 API 응답이 없습니다."
        msg = (
            f"❗️비트겟 API 오류: 실시간 자산/포지션을 가져올 수 없습니다.\n\n"
            f"원인: {err_msg}\n"
            f"1) API키/시크릿/패스프레이즈 확인\n"
            f"2) 키 권한 및 요청제한, 네트워크, IP락, 서버 오류, 유지보수, 구조 변경, 파라미터 입력오류 등 포함\n"
            f"3) 문제가 지속되면 Bitget 공식 사이트에서 키 상태/권한/쿼터/접속 제한/실행 서버 위치 등을 직접 점검"
        )
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        return

    required_keys = [
        '종목', '방향', '진입가', '현재가', '레버리지', '청산가',
        '청산까지 남은 거리', '미실현 손익', '실현 손익', '진입 자산', '수익률'
    ]
    if not all(k in profit for k in required_keys):
        msg = "❗️Bitget API 데이터 구조 변경 또는 키값 누락 발생! 리포트 형식 재확인 필요."
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
