
from datetime import datetime
import pytz

def generate_profit_report():
    now = datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
    unrealized = 81.0
    realized = 24.3
    total = unrealized + realized
    rate = 5.26
    krw = 143000

    if rate >= 10:
        comment = f"🎉 오늘 선물로 {krw:,}원을 벌었다니, 해외여행 항공권에 가까운 수익이에요!"
    elif rate >= 5:
        comment = f"💰 오늘 수익은 약 {krw:,}원으로 편의점 알바 약 10시간치에 해당해요!"
    elif rate > 0:
        comment = f"📈 오늘도 +수익으로 마감했어요. 작지만 꾸준한 수익은 강력한 무기입니다!"
    elif rate > -5:
        comment = f"📉 약간의 손실({rate}%)은 전략적 휴식일 수 있어요."
    else:
        comment = f"🛑 오늘 손실이 컸어요. 충동매매는 반드시 피해주세요."

    return f"""💰 현재 수익 현황 요약
📅 작성 시각: {now}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보
- 종목: BTCUSDT
- 방향: 롱
- 진입가: $65,400 / 현재가: $66,210
- 레버리지: 10x
- 청산가: $60,930
━━━━━━━━━━━━━━━━━━━
💸 손익 정보
- 미실현 손익: +${unrealized} (11.0만원)
- 실현 손익: +${realized} (3.3만원)
- 금일 총 수익: +${total} (14.3만원)
- 수익률: +{rate:.2f}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
"""    
