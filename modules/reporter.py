from datetime import datetime
from modules.constants import *
from modules.exchange import get_position_info
from modules.analyst import (
    gpt_event_scan, gpt_technical_analysis, gpt_sentiment_analysis, gpt_12h_forecast, gpt_mental_comment
)

def format_profit(data):
    total_profit = data['unrealized_pnl'] + data['realized_pnl']
    profit_rate = (total_profit / data['margin']) * 100
    krw = data['krw_usd']
    total_profit_krw = int(total_profit * krw)
    # 멘탈 코멘트: GPT 실시간 생성
    comment = gpt_mental_comment(profit_rate, total_profit_krw)
    return f"""\
{PROFIT_HEADER}
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
- 미실현 손익: +${data['unrealized_pnl']} (약 {int(data['unrealized_pnl']*krw):,}원)
- 실현 손익: +${data['realized_pnl']} (약 {int(data['realized_pnl']*krw):,}원)
- 금일 총 수익: +${total_profit:.1f} (약 {total_profit_krw:,}원)
- 진입 자산: ${data['margin']}
- 수익률: +{profit_rate:.2f}%
━━━━━━━━━━━━━━━━━━━
🧠 멘탈 케어
{comment}
━━━━━━━━━━━━━━━━━━━
"""

def format_report():
    return f"""{REPORT_HEADER}
📅 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━
📌 시장 이벤트 및 속보
{gpt_event_scan()}
━━━━━━━━━━━━━━━━━━━
📉 기술적 분석
{gpt_technical_analysis()}
━━━━━━━━━━━━━━━━━━━
🧠 심리·구조적 분석
{gpt_sentiment_analysis()}
━━━━━━━━━━━━━━━━━━━
🔮 향후 12시간 예측
{gpt_12h_forecast()}
━━━━━━━━━━━━━━━━━━━
💰 수익 및 미실현 손익
{format_profit(get_position_info())}
"""

def format_forecast():
    return f"""{FORECAST_HEADER}
📅 작성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━
📊 분석 요약
{gpt_technical_analysis()}
━━━━━━━━━━━━━━━━━━━
🔮 12시간 매동 전망
{gpt_12h_forecast()}
━━━━━━━━━━━━━━━━━━━
💰 금일 손익
{format_profit(get_position_info())}
"""
