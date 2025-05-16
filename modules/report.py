import openai
from modules.utils import fetch_coinbase_price, format_currency, send_telegram_message
from modules.constants import ANALYSIS_LOADING_MESSAGE

def build_and_send_report():
    send_telegram_message(ANALYSIS_LOADING_MESSAGE)
    
    # 예시 분석 (실제 Bitget API 연동 등은 추후 적용)
    current_price = fetch_coinbase_price() or 0
    analysis = (
        f"📈 *BTC 예측 리포트*\n"
        f"현재가: ${current_price:,.2f}\n\n"
        "🧠 GPT 분석 중...\n\n"
        "_잠시 후 예측 결과가 업데이트됩니다._"
    )
    send_telegram_message(analysis)
