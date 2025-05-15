# modules/report.py

import requests
import datetime
from modules.constants import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from modules.utils import fetch_coinbase_price, fetch_bitget_position_data, format_currency

def build_and_send_report():
    try:
        # 실시간 가격
        price = fetch_coinbase_price()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 비트겟 수익 분석
        position_data = fetch_bitget_position_data()
        entry_usdt = position_data["entry_value"]
        pnl_usdt = position_data["pnl"]
        pnl_krw = pnl_usdt * 1375  # 환율 예시
        entry_krw = entry_usdt * 1375
        pnl_rate = (pnl_usdt / entry_usdt * 100) if entry_usdt else 0

        message = (
            f"📡 *BTC 정규 매매 리포트*\n\n"
            f"📅 시각: {now}\n"
            f"💰 현재 BTC 가격: ${price:,.2f}\n\n"
            f"📊 *포지션 요약*\n"
            f"• 진입 자산: {format_currency(entry_usdt)} USDT ({format_currency(entry_krw)}원)\n"
            f"• 수익: {format_currency(pnl_usdt)} USDT ({format_currency(pnl_krw)}원)\n"
            f"• 수익률: {pnl_rate:.2f}%\n"
        )

        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        )
    except Exception as e:
        print(f"[리포트 오류]: {e}")
