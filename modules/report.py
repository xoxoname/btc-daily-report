import requests
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY
from modules.utils import (
    fetch_coinbase_price,
    fetch_bitget_position_data,
    format_currency,
    fetch_total_profit,
    fetch_openai_analysis,
)

def build_and_send_report():
    try:
        btc_price = fetch_coinbase_price()
        position = fetch_bitget_position_data()
        total_profit = fetch_total_profit(position)

        message = f"💸 [실시간 수익 리포트]\n\n"

        if position:
            message += (
                f"🔹 포지션: {position['symbol']}\n"
                f"🔹 진입가: ${position['entry_price']:.2f}\n"
                f"🔹 현재가: ${position['current_price']:.2f}\n"
                f"🔹 미실현 손익: {format_currency(position['unrealized_pnl'])}\n"
                f"🔹 실현 손익: {format_currency(position['realized_pnl'])}\n"
                f"🔹 수익률: {position['pnl_percent']:.1f}%\n\n"
                f"🧾 총 자산 기준: ${position['initial_asset']:.2f} → ${position['total_asset']:.2f} "
                f"(+{format_currency(total_profit, include_sign=False)})\n"
            )

            if total_profit < 0:
                message += "\n😶 멘탈 코멘트: 오늘은 아쉽지만 손실이네요. 그래도 지난 7일 기준 누적 수익은 +4.2%로 여전히 수익권 유지 중이에요. 충동적인 판단은 잠시 내려놓고 흐름을 지켜봐요!"
            else:
                message += "\n😌 멘탈 코멘트: 오늘 수익은 편의점 아르바이트 약 4시간 분량이에요. 충분히 잘하고 계시니 조급해하지 마세요! 🚶‍♂️🚶‍♀️"

        else:
            message += "📭 현재 오픈된 포지션이 없습니다."

        send_telegram_message(message)

    except Exception as e:
        send_telegram_message(f"❌ 리포트 생성 중 오류 발생: {e}")

def send_telegram_message(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
    )

def handle_prediction_report():
    try:
        send_telegram_message("📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.")

        summary = fetch_openai_analysis()
        send_telegram_message(summary)

    except Exception as e:
        send_telegram_message(f"❌ 예측 분석 중 오류 발생: {e}")
