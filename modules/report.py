from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY
from modules.utils import (
    fetch_coinbase_price,
    fetch_bitget_position_data,
    format_currency,
    send_telegram_message,
)
import openai

def build_and_send_report():
    try:
        price = fetch_coinbase_price()
        pos_data = fetch_bitget_position_data()
        usdt_pnl = pos_data.get("total_pnl", 0)
        krw_pnl = int(usdt_pnl * 1370)

        prompt = (
            f"현재 BTC 가격은 ${price}이고, 포지션 손익은 ${usdt_pnl}입니다.\n"
            "기술적 지표, 심리적 요소, 구조적 요소를 바탕으로 12시간 이내의 시장 예측 리포트를 GPT-4 수준으로 작성해줘. "
            "중대한 시장 이벤트나 급변 가능성도 포함해줘."
        )

        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response['choices'][0]['message']['content'].strip()

        message = (
            f"📊 BTC 자동 예측 리포트\n\n"
            f"{summary}\n\n"
            f"💰 실현+미실현 수익: ${usdt_pnl:.2f} ({krw_pnl:,}원)\n"
            f"🪙 현재 BTC 시세: ${price:,.2f}"
        )
        send_telegram_message(message)

    except Exception as e:
        send_telegram_message(f"[ERROR] 리포트 생성 실패: {e}")
