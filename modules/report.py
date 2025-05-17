from modules.utils import get_total_profit_usdt
from datetime import datetime

def format_krw(usd):
    return f"(약 {round(usd * 1370 / 10000, 1)}만원)"

def generate_profit_report():
    data = get_total_profit_usdt()
    if "error" in data:
        return f"❌ 수익 정보 조회 실패: {data['error']}"

    symbol = data["symbol"]
    entry = data["entryPrice"]
    market = data["marketPrice"]
    size = data["size"]
    side = data["side"]
    pnl = data["pnl"]
    pnl_rate = (pnl / (entry * size)) * 100 if entry and size else 0

    # 예시 실현 손익 (실제 구현 시 get_account_assets 또는 별도 API 필요)
    realized_pnl = 55.40  # 임시 고정값
    total_today = realized_pnl + pnl
    total_accum = 133.90  # 예시: 누적 수익 (DB 연동 필요 시 분리)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    comment = "😌 오늘도 침착하게 유지 중입니다." if pnl >= 0 else "😥 오늘은 흔들렸지만 포커에서도 한 판 쉬는 건 전략입니다."

    return f"""💸 [실시간 수익 리포트]

🔹 포지션: {symbol}
🔹 진입가: ${entry:,.2f}
🔹 현재가: ${market:,.2f}
🔹 미실현 손익: ${pnl:,.2f} {format_krw(pnl)}
🔹 수익률: {pnl_rate:.1f}%

🧾 금일 실현 손익: ${realized_pnl:,.2f} {format_krw(realized_pnl)}
📊 금일 총 수익: ${total_today:,.2f} {format_krw(total_today)}
💼 총 누적 수익: ${total_accum:,.2f} {format_krw(total_accum)}

🕒 기준 시각: {now}
{comment}"""
