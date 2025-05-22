
from datetime import datetime
import pytz
from modules.bitget_api import get_positions

def generate_profit_report():
    now = datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
    try:
        data = get_positions()
        pos = data['data']

        entry_price = float(pos['openPrice'])
        mark_price = float(pos['markPrice'])
        leverage = int(pos['leverage'])
        pnl = float(pos['unrealizedPL'])
        margin = float(pos['margin'])

        rate = (pnl / margin) * 100 if margin != 0 else 0
        krw_total = pnl * 1350
        direction = "롱" if pos['holdSide'] == 'long' else '숏'

        if rate >= 10:
            comment = f"🎉 오늘 선물로 {krw_total:,.0f}원을 벌었다니, 해외여행 항공권에 가까운 수익이에요!"
        elif rate >= 5:
            comment = f"💰 오늘 수익은 약 {krw_total:,.0f}원으로 편의점 알바 약 10시간치에 해당해요!"
        elif rate > 0:
            comment = f"📈 오늘도 +수익으로 마감했어요. 작지만 꾸준한 수익은 강력한 무기입니다!"
        elif rate > -5:
            comment = f"📉 약간의 손실({rate:.2f}%)은 전략적 휴식일 수 있어요."
        else:
            comment = f"🛑 오늘 손실이 컸어요. 충동매매는 반드시 피해주세요."

        return f"""💰 현재 수익 현황 요약
📅 작성 시각: {now}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
- 종목: BTCUSDT
- 방향: {direction}
- 진입가: ${entry_price} / 현재가: ${mark_price}
- 레버리지: {leverage}x
━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: ${pnl:.2f} (약 {krw_total:,.0f}원)
- 진입 자산: ${margin}
- 수익률: {rate:.2f}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
"""    
    except Exception as e:
        return f"❗ Bitget API 오류 발생: {str(e)}"
