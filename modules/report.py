from modules.bitget_api import fetch_wallet_balance, fetch_positions
from modules.utils import format_currency, convert_usd_to_krw
from datetime import datetime

def generate_profit_report():
    available, total = fetch_wallet_balance()
    positions = fetch_positions()

    report = f"📊 [정규 리포트]\n⏰ 기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += f"💰 총 자산: {format_currency(total)} USDT ({convert_usd_to_krw(total)}원)\n"
    report += f"🔓 사용 가능: {format_currency(available)} USDT ({convert_usd_to_krw(available)}원)\n\n"

    if positions:
        report += "📈 포지션:\n"
        for p in positions:
            symbol = p["symbol"]
            entry = float(p["entryPrice"])
            mark = float(p["markPrice"])
            pnl = float(p["unrealizedPL"])
            report += f"- {symbol} | 진입가: {entry} | 현재가: {mark} | PnL: {format_currency(pnl)} USDT ({convert_usd_to_krw(pnl)}원)\n"
    else:
        report += "📉 현재 보유 포지션이 없습니다."

    return report

def generate_schedule_report():
    return (
        "🗓️ 금일 보고 일정은 다음과 같습니다:\n"
        "- 오전 9시\n- 오후 1시\n- 오후 11시\n(모두 KST 기준)"
    )
