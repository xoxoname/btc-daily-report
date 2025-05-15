import requests
import openai
from modules.constants import REPORT_URL, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY

def build_and_send_report():
    try:
        response = requests.get(REPORT_URL)
        data = response.json()

        btc_price = data['btc_price']
        krw_price = data['btc_price_krw']
        pnl = data['realized_pnl']
        unrealized = data['unrealized_pnl']
        pnl_rate = data['pnl_rate']

        content = (
            f"📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.\n\n"
            f"📊 현재 BTC 가격: ${btc_price} ({krw_price:,}원)\n"
            f"💸 실현 손익: ${pnl} / 미실현: ${unrealized}\n"
            f"📈 수익률: {pnl_rate}%"
        )

        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": content}
        )
    except Exception as e:
        print(f"[리포트 오류]: {e}")
