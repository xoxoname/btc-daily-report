import datetime
from .bitget import get_positions, get_profit_history
from .gpt import ask_gpt, get_dynamic_mental_comment

def get_krw(val_usd, usdkrw=1350):
    try:
        return int(float(val_usd) * usdkrw)
    except Exception:
        return 0

def format_profit_report():
    pos = get_positions()
    profit = get_profit_history()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usdkrw = 1350  # 환율 고정(실환율은 추후 API)
    mental = ""

    if pos:
        day_pnl = float(pos.get("unrealizedPnl", 0)) + float(profit.get("realizedPnl", 0))
        day_pnl_krw = get_krw(day_pnl, usdkrw)
        mental = get_dynamic_mental_comment(day_pnl, day_pnl_krw)
        msg = f"""💰 현재 수익 현황 요약
📅 작성 시각: {now}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보

종목: {pos['symbol']}
방향: {pos['side']}
진입가: ${pos['openPrice']:,} / 현재가: ${pos['currentPrice']:,}
레버리지: {pos['leverage']}x
청산가: ${pos['liquidationPrice']:,}
청산까지 남은 거리: 약 {round(100*(1-pos['liquidationPrice']/pos['openPrice']),1)}%

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
미실현 손익: {pos['unrealizedPnl']:+.2f} (약 {get_krw(pos['unrealizedPnl'], usdkrw):,}원)
실현 손익: {profit['realizedPnl']:+.2f} (약 {get_krw(profit['realizedPnl'], usdkrw):,}원)
금일 총 수익: {day_pnl:+.2f} (약 {day_pnl_krw:,}원)
진입 자산: ${pos['margin']:,}
수익률: {round(100*day_pnl/max(1,pos['margin']),2)}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{mental}
━━━━━━━━━━━━━━━━━━━
"""
    else:
        # 포지션 없음/손익만 보여주기
        realized = profit.get("realizedPnl", 0)
        today = profit.get("todayPnl", 0)
        msg = f"""💰 현재 수익 현황 요약
📅 작성 시각: {now}
━━━━━━━━━━━━━━━━━━━
포지션 없음(BTCUSDT). 현재 오픈된 포지션이 없습니다.

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
실현 손익: {realized:+.2f} (약 {get_krw(realized):,}원)
금일 총 수익: {today:+.2f} (약 {get_krw(today):,}원)
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{get_dynamic_mental_comment(today, get_krw(today))}
━━━━━━━━━━━━━━━━━━━
"""
    return msg
