from modules.utils import send_telegram_message, format_currency, get_kst_now
from modules.bitget_api import fetch_bitget_wallet_balance, fetch_bitget_positions

def build_and_send_report():
    balance = fetch_bitget_wallet_balance()
    positions = fetch_bitget_positions()

    msg = "📊 [정규 리포트]\n"
    msg += f"⏰ 기준 시각: {get_kst_now()}\n\n"
    msg += f"💰 총 자산: {format_currency(balance['totalEquity'])} USDT\n"
    msg += f"🔓 사용 가능: {format_currency(balance['available'])} USDT\n\n"
    if positions:
        msg += "📈 포지션:\n"
        for p in positions:
            msg += f"- {p['symbol']} | 진입가: {p['entryPrice']} | 현재가: {p['markPrice']} | PnL: {p['unrealizedPnl']} USDT\n"
    else:
        msg += "현재 보유 중인 포지션이 없습니다.\n"

    send_telegram_message(msg)

def handle_command(command):
    if command.startswith("/수익"):
        send_telegram_message("📊 수익 분석 준비 중입니다...\n잠시만 기다려 주세요.")
        build_and_send_report()
    elif command.startswith("/일정"):
        send_telegram_message("🗓️ 금일 보고 일정은 다음과 같습니다:\n- 오전 9시\n- 오후 1시\n- 오후 11시\n(모두 KST 기준)")
    elif command.startswith("/리포트"):
        send_telegram_message("📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")
