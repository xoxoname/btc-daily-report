import pytz
from datetime import datetime

def format_profit_report(position, wallet):
    now = datetime.now(pytz.timezone("Asia/Seoul"))
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    # 실제 포지션 연동 시 포지션 0일 때 처리 포함
    if not position:
        return f"수익 정보 조회 오류. Bitget API 연동 또는 인증키 확인 필요!\n(작성 시각: {created_at})"
    p = position[0]
    now_price = p["avgOpenPrice"] + p["upl"]  # 예시
    profit_krw = int(p["upl"] * 1350)
    real_krw = int(p["realisedPnl"] * 1350)
    total_krw = int((p["upl"] + p["realisedPnl"]) * 1350)
    pnl_rate = round((p["upl"] + p["realisedPnl"]) / p["margin"] * 100, 2)
    # 멘탈 코멘트
    comment = get_mental_comment(p["upl"], p["realisedPnl"], p["margin"], total_krw)
    return f"""💰 현재 수익 현황 요약
📅 작성 시각: {created_at}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보

종목: BTCUSDT
방향: {p['holdSide'].capitalize()}
진입가: ${p['avgOpenPrice']:,} / 현재가: ${now_price:,.0f}
레버리지: {p['leverage']}x
청산가: ${p['liquidationPrice']:,}
청산까지 남은 거리: 약 {round(abs(p['avgOpenPrice'] - p['liquidationPrice'])/p['avgOpenPrice']*100, 2)}%

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
미실현 손익: {p['upl']:+.2f} (약 {profit_krw:,}원)
실현 손익: {p['realisedPnl']:+.2f} (약 {real_krw:,}원)
금일 총 수익: {p['upl'] + p['realisedPnl']:+.2f} (약 {total_krw:,}원)
진입 자산: ${p['margin']:,}
수익률: {pnl_rate}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
━━━━━━━━━━━━━━━━━━━
"""

def get_mental_comment(upl, realised, margin, total_krw):
    # 실제 상황별 맞춤형 자동 멘트
    import random
    if upl + realised > 0:
        msg = [
            f"수익 {total_krw:,}원, 현실 알바 {total_krw//12000}시간! 이럴 때일수록 휴식도 전략입니다. 내일을 위한 에너지도 챙기세요.",
            f"오늘 선물로 {total_krw:,}원! 편의점 알바 {total_krw//12000}시간분 수익, 이럴 때는 충동 매매를 잠시 멈추고 다음 기회를 기다려 보세요.",
            f"{total_krw:,}원 벌었어요! 꾸준한 승리는 조급하지 않은 하루에서 시작합니다. 내일 매매는 쉬어도 괜찮아요."
        ]
    else:
        msg = [
            "손실이 발생했습니다. 조급함은 금물! 한 번의 손실이 길게 보면 좋은 배움이 될 수 있습니다.",
            "손실 구간입니다. 진입 이유를 복기해보며 매매를 잠시 쉬어보는 것도 좋은 선택입니다.",
            "시장에는 늘 기회가 옵니다. 오늘 손실은 내일을 위한 연습일 뿐! 충동 매매만 피하세요."
        ]
    return random.choice(msg)
