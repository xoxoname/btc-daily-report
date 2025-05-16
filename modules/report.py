import openai
import telegram
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY
from modules.utils import fetch_coinbase_price, fetch_bitget_position_data, format_currency

bot = telegram.Bot(token=TELEGRAM_TOKEN)
openai.api_key = OPENAI_API_KEY

def build_and_send_report():
    price = fetch_coinbase_price()
    bitget_data = fetch_bitget_position_data()

    if not price or not bitget_data:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ 실시간 데이터 조회에 실패했습니다.")
        return

    total_usdt = bitget_data.get("total_usdt", 0)
    total_krw = bitget_data.get("total_krw", 0)
    pnl_usdt = bitget_data.get("total_pnl", 0)
    pnl_krw = bitget_data.get("total_pnl_krw", 0)
    entry_usdt = bitget_data.get("entry_usdt", 1)
    roi = (pnl_usdt / entry_usdt) * 100 if entry_usdt else 0

    usd = format_currency(price)
    krw = format_currency(price * 1350, "KRW")

    report = (
        f"📡 *GPT 기반 비트코인 매매 분석 리포트*\n\n"
        f"📊 *현재 BTC 시세*: {usd} ({krw})\n"
        f"💼 *진입 자산*: {format_currency(entry_usdt)} ({format_currency(entry_usdt * 1350, 'KRW')})\n"
        f"📈 *총 수익*: {format_currency(pnl_usdt)} ({format_currency(pnl_krw, 'KRW')})\n"
        f"📊 *총 자산*: {format_currency(total_usdt)} ({format_currency(total_krw, 'KRW')})\n"
        f"📌 *수익률*: {roi:.2f}%\n"
        f"\n🧠 예측 보고서 및 시장 심층 분석은 GPT 처리 시스템에서 곧 도착합니다."
    )

    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=report, parse_mode="Markdown")
