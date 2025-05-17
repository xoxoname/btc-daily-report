# modules/report.py
import os
from openai import OpenAI
from modules.utils import (
    get_current_timestamp,
    get_bitget_data,
    format_usd,
    format_krw,
    load_previous_prediction,
    save_prediction
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_profit_report():
    data = get_bitget_data()
    pos = data["positions"][0]

    msg = f"""📆 {get_current_timestamp()} 기준 수익 리포트

💸 [실시간 수익 리포트]

🔹 포지션: {pos['symbol']}
🔹 진입가: {format_usd(pos['entry_price'])}
🔹 현재가: {format_usd(pos['current_price'])}
🔹 미실현 손익: {format_usd(pos['pnl_usd'])} (약 {format_krw(pos['pnl_krw'])})
🔹 수익률: {data['return_rate']}%

🧾 오늘 실현 손익: {format_usd(data['realized'])} (약 {format_krw(data['realized'] * 1370)})
💼 입금 기준 자산: ${data['deposit']} → ${data['now_asset']}
📊 총 수익 : {format_usd(data['total_pnl'])} (약 {format_krw(data['total_krw'])})
"""

    if data['total_pnl'] < 0:
        msg += f"""
😥 멘탈 코멘트:
오늘은 살짝 흔들렸지만, 포커 게임에서도 한두 번 접는 건 전략입니다.
📊 지난 7일 누적 수익률은 여전히 +{data['weekly_return']}%로 수익권 유지 중이에요!
지금은 조급함보다 침착함이 자산을 지키는 열쇠입니다.
"""
    else:
        msg += """
😌 멘탈 코멘트:
오늘은 꽤 잘 버셨네요! 🍕 야식 3번은 시켜 먹을 수 있을 정도입니다.
무리하지 말고 이 흐름 유지해보세요. 장기전이니까요.
"""
    return msg


def generate_full_report():
    # 향후 실시간 분석용 기능 통합 예정
    return "📡 GPT 기반 정규 분석 리포트는 현재 생성 중입니다."


def generate_prediction():
    previous = load_previous_prediction()
    prompt = f"""
비트코인 매매 동향 예측 보고서를 다음 형식으로 작성해줘. 간결하게, 명확하게, 예시처럼 가독성 좋게 만들어줘. (이전 예측: {previous['direction']} / 실제 결과: {previous['result']}) 참고해서 피드백까지 포함시켜줘.

1. 시장 뉴스 및 이벤트 요약 (호재/악재/중립)
2. 기술적 분석 요약 (호재/악재/중립)
3. 심리 및 구조 분석 (호재/악재/중립)
4. 향후 12시간 예측 (상승/하락/횡보 확률 + 시세 구간)
5. 예외 상황 감지 (있으면 원인 포함)
6. 이전 예측 검증 결과 요약
7. 오늘 손익 및 수익률 (한화 환산 포함)
8. 위트 있고 센스 있는 멘탈 코멘트 (수익 여부 따라 다르게)

출력은 다음과 같은 Markdown 형식으로 줄 간격 포함해서 보내줘:
━━━━━━━━━━━━━━━━━━━━
제목  
내용
━━━━━━━━━━━━━━━━━━━━
이런 느낌으로 출력해.
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.choices[0].message.content
    save_prediction(result)
    return f"📡 {get_current_timestamp()} 기준 분석 결과입니다.\n\n{result}"
