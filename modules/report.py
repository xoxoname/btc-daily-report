from modules.utils import fetch_btc_price, fetch_bitget_data
from modules.constants import CHAT_ID, TELEGRAM_BOT_TOKEN
import requests

def format_profit_report_text():
    usd, krw = fetch_btc_price()
    if not usd or not krw:
        return "❌ 비트코인 실시간 가격 조회에 실패했습니다."

    data = fetch_bitget_data()
    realized = data["realized_pnl"]
    unrealized = data["unrealized_pnl"]
    entry = data["entry_balance"]
    total = realized + unrealized
    roi = round((total / entry) * 100, 2)

    report = f"""
📊 현재 BTC 가격: ${usd:,.2f} ({int(krw):,}원 KRW 기준)
💰 실현 손익: ${realized:.2f}
📈 미실현 손익: ${unrealized:.2f}
🔁 총 수익률: {roi}%
"""
    return report.strip()

def build_and_send_report():
    profit_report = format_profit_report_text()
    message = f"📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.\n\n{profit_report}"
    send_telegram_message(CHAT_ID, message)
    return {"status": "success", "prediction_report": "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다.", "profit_report": profit_report}

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)
