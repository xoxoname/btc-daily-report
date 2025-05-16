import os
import requests
from modules.bitget_api import fetch_bitget_positions, fetch_bitget_wallet_balance
from modules.constants import USDT_KRW
from modules.utils import get_kst_now, get_usdt_krw_price  # 이 함수들은 이미 utils.py 안에 있으면 삭제

def send_telegram_message(chat_id: str, text: str):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage",
            json=payload
        )
        response.raise_for_status()
    except Exception as e:
        print(f"❌ 텔레그램 메시지 전송 실패: {e}")


def get_profit_report_text():
    positions = fetch_bitget_positions()
    balance = fetch_bitget_wallet_balance()
    usdt_to_krw = get_usdt_krw_price()

    if not balance:
        return "❌ Bitget 지갑 정보를 불러올 수 없습니다."

    total_equity = balance.get("totalEquity", 0)
    margin = balance.get("marginBalance", 0)
    available = balance.get("availableBalance", 0)

    result_lines = [
        "📊 실시간 수익 리포트",
        f"총 자산: ${total_equity:.2f} ({total_equity * usdt_to_krw:,.0f}원)",
        f"증거금: ${margin:.2f}",
        f"가용 잔고: ${available:.2f}",
        "",
        "📈 현재 포지션:"
    ]

    if not positions:
        result_lines.append("포지션 없음")
    else:
        for p in positions:
            symbol = p['symbol']
            size = float(p['total'])
            entry_price = float(p['entryPrice'])
            mark_price = float(p['markPrice'])
            pnl = float(p['unrealizedPnl'])
            roe = float(p['returnRate'])
            krw_pnl = pnl * usdt_to_krw

            result_lines.append(
                f"- {symbol}: {size}개 @ 진입가 ${entry_price:.2f} → 현재가 ${mark_price:.2f}\n"
                f"  미실현손익: ${pnl:.2f} ({krw_pnl:,.0f}원), 수익률: {roe:.2f}%"
            )

    result_lines.append(f"\n업데이트: {get_kst_now().strftime('%Y-%m-%d %H:%M:%S')} (KST)")
    return "\n".join(result_lines)
