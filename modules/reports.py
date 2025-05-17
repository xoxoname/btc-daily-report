# modules/report.py
from modules.utils import fetch_realtime_data, krw, get_now_kst

async def generate_report():
    data = await fetch_realtime_data()
    now = get_now_kst()
    return f"""
📍 [BTC 매매 동향 예측 분석]  
발행 시각: {now} (KST 기준)  
분석 기준 시세: ${data['price']:,.2f} 
━━━━━━━━━━━━━━━━━━━━
📌 1. 시장 이벤트 및 뉴스 요약 ({data['news_grade']})
{data['news_summary']}
━━━━━━━━━━━━━━━━━━━━
📈 2. 기술적 분석 ({data['tech_grade']})
{data['tech_summary']}
━━━━━━━━━━━━━━━━━━━━
🧠 3. 심리·구조 분석 ({data['sentiment_grade']})
{data['sentiment_summary']}
━━━━━━━━━━━━━━━━━━━━
⏱ 4. 향후 12시간 매매 전망
- 🔼 상승 확률: {data['forecast_up']}%
- ➖ 횡보 확률: {data['forecast_side']}%
- 🔽 하락 확률: {data['forecast_down']}%
- 📍 예상 변동 구간: **${data['range_low']:,} ~ ${data['range_high']:,}**
━━━━━━━━━━━━━━━━━━━━
🚨 5. 예외 상황 감지
{data['exception_summary']}
━━━━━━━━━━━━━━━━━━━━
🔁 6. 이전 예측 검증
{data['backtest_result']}
━━━━━━━━━━━━━━━━━━━━
💰 수익 정보 요약
- 금일 실현 손익: **${data['realized']:.2f}** (약 {krw(data['realized'])})
- 미실현 손익: **${data['unrealized']:.2f}** (약 {krw(data['unrealized'])})
- 총 수익: **${data['total_profit']:.2f}** (약 {krw(data['total_profit'])})
━━━━━━━━━━━━━━━━━━━━
😌 오늘의 멘탈 코멘트
{data['comment']}
━━━━━━━━━━━━━━━━━━━━
"""

async def generate_profit():
    data = await fetch_realtime_data()
    return f"""
💸 [실시간 수익 리포트]

🔹 포지션: BTCUSDT
🔹 진입가: ${data['entry_price']}
🔹 현재가: ${data['price']}
🔹 미실현 손익: {data['unrealized']} ({krw(data['unrealized'])})
🔹 수익률: {data['pnl_percent']}%

🧾 오늘 실현 손익: {data['realized']} ({krw(data['realized'])})
💼 입금 기준 자산: ${data['initial']} → ${data['current']}
📊 총 수익 : {data['total_profit']} ({krw(data['total_profit'])})

{data['comment']}
"""

async def generate_forecast():
    data = await fetch_realtime_data()
    return f"""
🔮 [BTC 12시간 예측 리포트]

🗞️ 시장 이벤트 요약
{data['news_summary']}
📈 기술적 분석
{data['tech_summary']}
🧠 심리/구조적 분석
{data['sentiment_summary']}

📡 12시간 내 예상 흐름
- 하락 가능성: {data['forecast_down']}%
- 횡보 가능성: {data['forecast_side']}%
- 상승 가능성: {data['forecast_up']}%
➡️ 예측 시세 범위: ${data['range_low']} ~ ${data['range_high']}

💡 GPT 보조 지표: {data['gpt_signal']}

🧾 오늘 손익
- 금일 실현 손익: {data['realized']}
- 현재 미실현 손익: {data['unrealized']}
- 📉 금일 총 손익: {data['total_profit']}

😌 멘탈 코멘트
{data['comment']}
"""

async def generate_schedule():
    data = await fetch_realtime_data()
    return f"""
📅 향후 7일간 주요 일정
날짜 (KST)	이벤트	예상 영향
{data['schedule']}
"""
