import datetime
from modules.bitget import get_positions, get_wallet
from modules.gpt import get_gpt_comment

def format_profit_report():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pos = get_positions()
    wallet = get_wallet()
    if not pos:
        return f"수익 정보 조회 오류. Bitget API 연동 또는 인증키 확인 필요!"

    entry = pos["openPrice"]
    price = pos["currentPrice"]
    side = pos["side"]
    qty = pos["positionAmt"]
    liq = pos["liquidationPrice"]
    lev = pos["leverage"]
    unreal = pos["unrealizedPnl"]
    margin = pos["margin"]
    asset = wallet

    pnl_percent = (unreal / margin) * 100 if margin > 0 else 0
    liq_gap = ((price - liq) / price) * 100 if price > liq else ((liq - price) / price) * 100

    krw_rate = 1350  # 환율 임시 고정, 원하면 환율 API로 자동화
    krw_unreal = int(unreal * krw_rate)
    krw_margin = int(margin * krw_rate)
    krw_asset = int(asset * krw_rate)

    comment = get_gpt_comment(pnl_percent, unreal)

    return f"""
💰 현재 수익 현황 요약
📅 작성 시각: {now}
━━━━━━━━━━━━━━━━━━━
📌 포지션 정보

종목: BTCUSDT
방향: {side}
진입가: ${entry:.2f} / 현재가: ${price:.2f}
레버리지: {lev}x
청산가: ${liq}
청산까지 남은 거리: 약 {liq_gap:.2f}%

━━━━━━━━━━━━━━━━━━━
💸 손익 정보
미실현 손익: {unreal:+.2f} USDT (약 {krw_unreal:,}원)
진입 증거금: {margin:.2f} USDT (약 {krw_margin:,}원)
총 자산: {asset:.2f} USDT (약 {krw_asset:,}원)
수익률: {pnl_percent:+.2f}%

━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
━━━━━━━━━━━━━━━━━━━
""".strip()
