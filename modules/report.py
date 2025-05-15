import os
import openai
from datetime import datetime

# 레거시 0.28.0 방식: 환경변수에서 API 키를 직접 읽어 세팅
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_prediction_report():
    prompt = (
        "1. 📰 시장 요인 요약\n"
        "- CPI 발표: 연간 2.6%, 예상치 초과 → BTC에 영향: 긍정적\n"
        "- 연준 발언 없음, 바이든/트럼프 이슈 없음 → 중립\n"
        "- ETF/해킹 등 긴급 뉴스 없음 → 중립\n"
        "- 유럽 증시 개장 전 Amazon 실적 호조 → 기술주 심리 개선 → BTC에 소폭 호재\n\n"
        "2. 📈 BTC 기술적 분석\n"
        "- RSI, MACD, 이동평균(20/50/200), 볼린저밴드, 피보나치, Ichimoku 등 주요 지표\n"
        "- 파생: 펀딩비, 오픈이자, 롱·숏 비율 등\n"
        "- 온체인: 고래 이체, 유동성 맵\n\n"
        "3. 🧠 심리 및 구조적 요소\n"
        "- 공포·탐욕 지수, 커뮤니티 정서, DXY, BTC Dominance 등\n"
        "- ETF 자금 유입/유출, 옵션 만기 집중 구간\n\n"
        "4. 📌 12시간 예측 및 전략\n"
        "- 상승 확률 XX% / 하락 확률 YY%\n"
        "- 근거 요약 및 전략 제언\n\n"
        "5. ⚠️ 예외 상황 실시간 감지\n"
        "- 규제·해킹·ETF 승인 등 특이 뉴스 즉시 알림\n\n"
        "6. 🧾 이전 예측 검증 및 피드백\n"
        "- 전 예측 vs 실제 움직임 비교, 보완점 제시\n\n"
        "위 6개 항목을 종합해 12시간 BTC 예측 리포트를 상세히 작성해주세요."
    )

    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 분석가입니다."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content

def format_profit_report_text():
    # Bitget 연동 전 임시 데이터
    realized_pnl   = 31.4
    unrealized_pnl = -5.2
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"🧾 실현 손익: ${realized_pnl:.2f}\n"
        f"📉 미실현 손익: ${unrealized_pnl:.2f}\n"
        f"🕒 기준 시각: {now}"
    )
