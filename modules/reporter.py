from datetime import datetime
from modules.exchange import get_position_info
from modules.constants import *

def generate_profit_report():
    data = get_position_info()
    total_profit = data['unrealized_pnl'] + data['realized_pnl']
    profit_rate = (total_profit / data['margin']) * 100
    if profit_rate > 10:
        comment = MENTAL_COMMENTS["high_profit"]
    elif profit_rate > 1:
        comment = MENTAL_COMMENTS["mid_profit"]
    elif profit_rate > -1:
        comment = MENTAL_COMMENTS["neutral"]
    elif profit_rate > -5:
        comment = MENTAL_COMMENTS["small_loss"]
    else:
        comment = MENTAL_COMMENTS["big_loss"]

    return f"""{PROFIT_HEADER}
📅 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
- 종목: {data['symbol']}
- 방향: {data['side']}
- 진입가: ${data['entry_price']} / 현재가: ${data['current_price']}
- 레버리지: {data['leverage']}x
- 청산가: ${data['liq_price']}
- 청산까지 남은 거리: 약 {-((data['current_price'] - data['liq_price']) / data['entry_price']) * 100:.1f}%

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: +${data['unrealized_pnl']} (약 11.0만원)
- 실현 손익: +${data['realized_pnl']} (약 3.3만원)
- 금일 총 수익: +${total_profit:.1f} (약 14.3만원)
- 진입 자산: ${data['margin']}
- 수익률: +{profit_rate:.2f}%

━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
━━━━━━━━━━━━━━━━━━━
"""
