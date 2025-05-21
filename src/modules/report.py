from .bitget_api import get_btc_price, get_spot_balance_usdt, get_btcusdt_position
from datetime import datetime
import pytz

def generate_profit_report():
    now = datetime.now(pytz.timezone("Asia/Seoul")).strftime('%Y-%m-%d %H:%M')
    price = get_btc_price()
    usdt = get_spot_balance_usdt()
    pos = get_btcusdt_position()
    entry = float(pos.get("openPrice", 0))
    mark = float(pos.get("marketPrice", price))
    size = float(pos.get("total", 0))
    leverage = float(pos.get("leverage", 1))
    direction = pos.get("holdSide", "N/A").upper()
    pnl = float(pos.get("unrealizedPL", 0))
    liquidation = float(pos.get("liquidationPrice", 0))

    profit_pct = round((pnl / (entry * size / leverage)) * 100, 2) if entry and size else 0
    krw = round(pnl * 1350)
    comment = "오늘 수익은 편의점 알바 {}시간치입니다.".format(round(krw / 3500, 1))

    return f"""💰 현재 수익 현황 요약
📅 작성 시각: {now}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
- 종목: BTCUSDT
- 방향: {direction}
- 진입가: ${entry:,} / 현재가: ${mark:,}
- 레버리지: {leverage}x
- 청산가: ${liquidation:,}
━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: ${pnl:.2f} ({krw:,}원)
- 수익률: {profit_pct:.2f}%
- 총 자산: ${usdt:.2f}
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
━━━━━━━━━━━━━━━━━━━"""