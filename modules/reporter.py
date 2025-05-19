import pytz
from datetime import datetime
import random

def format_profit_report(position, wallet):
    now = datetime.now(pytz.timezone("Asia/Seoul"))
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    if not position:
        return f"수익 정보 조회 오류. Bitget API 연동 또는 인증키 확인 필요!\n(작성 시각: {created_at})"
    p = position[0]
    now_price = p["avgOpenPrice"] + p["upl"]  # 보수적(실제는 현재가 따로 조회 권장)
    profit_krw = int(p["upl"] * 1350)
    real_krw = int(p["realisedPnl"] * 1350)
    total_krw = int((p["upl"] + p["realisedPnl"]) * 1350)
    pnl_rate = round((p["upl"] + p["realisedPnl"]) / p["margin"] * 100, 2)
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
    if upl + realised > 0:
        msg = [
            f"수익 {total_krw:,}원! 알바 {total_krw//12000}시간치, 수익에 들뜨지 말고 오늘은 매매 대신 산책 한 번 어떠세요?",
            f"축하해요, {total_krw:,}원 수익! 하지만 수익의 연속을 위해선 오늘은 관망, 내일 타점에 집중해봐요.",
            f"{total_krw:,}원 벌었어요! 이럴 때 충동 매매가 제일 위험합니다. 수익 인증하고 바로 로그아웃!",
            f"오늘은 수익 달성! 이럴 때일수록 추가 진입은 금물, 내일은 또 내일의 기회가 옵니다.",
        ]
    else:
        msg = [
            "손실이 발생했네요. 지금 바로 진입보다, 복기와 휴식이 더 현명합니다.",
            "시장에 흔들리지 마세요. 손실도 투자자의 경험치입니다. 다음 타점만 노려봐요.",
            "충동 매매 금지! 오늘 손실은 내일 기회로 바꿔봅시다.",
            "손실났을 때일수록 매매를 줄이고, 이전 기록 복기하며 진짜 실력을 쌓아가요.",
        ]
    return random.choice(msg)
