from datetime import datetime
import pytz
import random

# 동적 멘탈 코멘트 생성
def make_mental_comment(profit_krw, total_time=0, is_loss=False):
    hourly = 12000  # 편의점 시급 예시
    if profit_krw is None:
        return "매매는 휴식도 중요합니다. 오늘은 쉬어가요!"
    hours = round(abs(profit_krw) / hourly, 1)
    if profit_krw == 0:
        return "수익/손실이 없네요. 냉정하게 관망하는 것도 실력입니다."
    if is_loss:
        comment_list = [
            f"손실 {abs(profit_krw):,}원... 알바 {hours}시간치입니다. 급하게 복구하려다 더 잃지 말고 천천히 돌아보세요.",
            f"이번엔 {abs(profit_krw):,}원 손실이지만, 아직 기회는 많습니다. 리벤지 매매는 금물!",
            f"오늘은 손실 {abs(profit_krw):,}원. 내일 더 좋은 타이밍이 올 거예요. 괜찮아요!"
        ]
    else:
        comment_list = [
            f"{profit_krw:,}원 수익! 알바 {hours}시간. 오늘 수익으로 자신에게 작은 선물을 해보는 건 어떨까요?",
            f"오늘 수익 {profit_krw:,}원! 이런 날은 과감한 추가매수보단, 휴식하면서 내일 타이밍을 기다려요.",
            f"수익 {profit_krw:,}원, 현실 알바 {hours}시간! 수익에 집착 말고, 차분히 다음 타점까지 기다려봐요."
        ]
    return random.choice(comment_list)

def format_profit_report(position, realized_pnl=0, today_profit=0):
    seoul = pytz.timezone("Asia/Seoul")
    now = datetime.now(seoul)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    report = f"💰 현재 수익 현황 요약\n📅 작성 시각: {now_str}\n━━━━━━━━━━━━━━━━━━━\n"
    if not position:
        report += "📌 포지션 없음\n\n━━━━━━━━━━━━━━━━━━━\n💸 손익 정보\n"
        report += "미실현 손익: 0\n실현 손익: 0\n금일 총 수익: 0\n━━━━━━━━━━━━━━━━━━━\n"
        report += "🧠 멘탈 케어\n매매는 기회가 올 때만! 오늘은 여유롭게 관망하세요.\n━━━━━━━━━━━━━━━━━━━"
        return report

    entry = float(position.get("openPrice", 0))
    cur = float(position.get("marketPrice", 0))
    leverage = position.get("leverage", "N/A")
    liq = float(position.get("liqPrice", 0))
    pnl = float(position.get("unrealizedPL", 0))
    pnl_krw = int(pnl * 1350)
    realized = float(position.get("achievedPL", 0))  # Bitget에서 실현 손익
    realized_krw = int(realized * 1350)
    total_profit = pnl + realized
    total_profit_krw = int(total_profit * 1350)
    margin = float(position.get("margin", 0))
    direction = position.get("holdSide", "N/A")  # long/short

    report += "📌 포지션 정보\n\n"
    report += f"종목: {position.get('symbol', 'BTCUSDT')}\n"
    report += f"방향: {direction}\n"
    report += f"진입가: ${entry:,.2f} / 현재가: ${cur:,.2f}\n"
    report += f"레버리지: {leverage}x\n"
    report += f"청산가: ${liq:,.2f}\n"
    liq_gap = (entry - liq) if direction.lower().startswith("long") else (liq - entry)
    liq_percent = abs(liq_gap / entry) * 100 if entry else 0
    report += f"청산까지 남은 거리: 약 {liq_percent:.1f}%\n\n"
    report += "━━━━━━━━━━━━━━━━━━━\n"
    report += "💸 손익 정보\n"
    report += f"미실현 손익: {pnl:.2f} (약 {pnl_krw:,}원)\n"
    report += f"실현 손익: {realized:.2f} (약 {realized_krw:,}원)\n"
    report += f"금일 총 수익: {total_profit:.2f} (약 {total_profit_krw:,}원)\n"
    report += f"진입 자산: ${margin:,.2f}\n"
    roi = (total_profit / margin * 100) if margin else 0
    report += f"수익률: {roi:.1f}%\n"
    report += "━━━━━━━━━━━━━━━━━━━\n"
    is_loss = total_profit < 0
    report += f"🧠 멘탈 케어\n{make_mental_comment(total_profit_krw, is_loss=is_loss)}\n"
    report += "━━━━━━━━━━━━━━━━━━━"
    return report
