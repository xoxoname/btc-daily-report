import pytz
from datetime import datetime
from modules.bitget import get_btc_position, get_btc_balance, get_today_realized_profit
import random

def now_kst():
    return datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")

def get_mental_comment(profit_krw, profit_pct):
    # 예시: 현실 알바 비교, 충동 억제, 상황별 동적 멘트
    hourly_wage = 12000  # 현실 알바 시급(편의점 등)
    hours = round(profit_krw / hourly_wage, 1) if profit_krw else 0
    if profit_krw > 0:
        choices = [
            f"수익 {profit_krw:,.0f}원, 현실 알바 {hours}시간! 오늘의 성과로 충분합니다. 무리한 추가 매매는 피하고, 내일을 준비하세요.",
            f"오늘 선물로 {profit_krw:,.0f}원을 벌었어요! 이 수익이면 알바 {hours}시간 분량입니다. 차분히 다음 기회를 기다려봅시다.",
            f"수익률 {profit_pct:.2f}%. 수익을 지키는 것도 실력! 오늘은 여기까지, 휴식도 투자입니다.",
        ]
    elif profit_krw < 0:
        choices = [
            f"손실 {profit_krw:,.0f}원 발생. 무리한 만회보다, 원인 분석 후 내일을 준비해요.",
            f"손실 {profit_krw:,.0f}원, 알바 {hours}시간과 비슷. 감정 매매는 위험, 충분히 쉬어주세요.",
            f"수익률 {profit_pct:.2f}%. 손실을 빠르게 인정하고, 포지션 청산 후 휴식! 오늘의 경험이 내일을 만듭니다.",
        ]
    else:
        choices = [
            "포지션 없음! 기다림도 전략입니다. 시장의 기회를 찬찬히 관찰하세요.",
            "수익도 손실도 없던 하루, 꾸준한 관찰이 내일의 승리로 연결됩니다.",
        ]
    return random.choice(choices)

def format_profit_report():
    pos = get_btc_position()
    if "error" in pos:
        return f"수익 정보 조회 오류: {pos['error']}"

    balance = get_btc_balance()
    realized = get_today_realized_profit()
    profit_usdt = pos.get("upl", 0) + realized
    profit_krw = round(profit_usdt * 1350)
    profit_pct = round(profit_usdt / balance * 100, 2) if balance else 0

    lines = []
    lines.append("💰 현재 수익 현황 요약")
    lines.append(f"📅 작성 시각: {now_kst()}")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    if pos:
        lines.append("📌 포지션 정보\n")
        lines.append(f"종목: {pos.get('symbol', '-')}")
        lines.append(f"방향: {pos.get('side', '-')}")
        lines.append(f"진입가: ${pos.get('avg_open', 0):,.2f} / 현재가: ${pos.get('current_price', 0):,.2f}")
        lines.append(f"레버리지: {pos.get('leverage', '-') }x")
        lines.append(f"청산가: ${pos.get('liquidation', 0):,.2f}")
        distance = (pos.get('current_price', 0) - pos.get('liquidation', 0)) / pos.get('current_price', 1) * 100
        lines.append(f"청산까지 남은 거리: 약 {distance:.2f}%")
        lines.append("━━━━━━━━━━━━━━━━━━━")
    else:
        lines.append("현재 보유 포지션이 없습니다.\n━━━━━━━━━━━━━━━━━━━")

    lines.append("💸 손익 정보")
    lines.append(f"미실현 손익: {pos.get('upl', 0):+.2f} (약 {round(pos.get('upl', 0) * 1350):,}원)")
    lines.append(f"실현 손익: {realized:+.2f} (약 {round(realized * 1350):,}원)")
    lines.append(f"금일 총 수익: {profit_usdt:+.2f} (약 {profit_krw:,}원)")
    lines.append(f"진입 자산: ${balance:,.0f}")
    lines.append(f"수익률: {profit_pct:.2f}%")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 멘탈 케어")
    lines.append(get_mental_comment(profit_krw, profit_pct))
    lines.append("━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
