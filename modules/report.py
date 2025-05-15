# modules/report.py

import os
import openai
from datetime import datetime

# 1) API 키 설정 (환경변수 OPENAI_API_KEY)
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_prediction_report():
    """비트코인 12시간 예측 리포트 생성"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 전문 암호화폐 분석가입니다."},
            {"role": "user", "content": (
                "1. 📰 시장 요인 요약\n"
                "- 미국 CPI 발표: 전년比 2.4%, 예상치 부합 → BTC에 영향: 중립\n"
                "- 연준 발언 없음, 트럼프/바이든 이슈 無 → 중립\n"
                "- ETF/해킹 등 긴급 뉴스 없음 → 중립\n"
                "- 미국 증시 개장 전 JD.com 실적 호조 → 기술주 심리 개선 → BTC에 소폭 호재\n\n"
                "2. 📈 BTC 기술적 분석\n"
                "- RSI: 55 중립, MACD: 상향 크로스 → 단기 상승 우위\n"
                "- 이동평균(20/50/200): 20>50>200 → 상승 추세 유지\n"
                "- 볼린저밴드 상단 근접 → 과열 주의\n"
                "- 파생: 펀딩비 +0.02%, 오픈이자 증가 → 매수 압력\n"
                "- 바이낸스 유동성 맵: 69k–70k USD 구간에 물량 집결 → 지지 확인\n"
                "- 고래 온체인: 1대 대형 지갑 500 BTC 이체 → 중립\n\n"
                "3. 🧠 심리 및 구조적 요소\n"
                "- 공포·탐욕 지수: 62 탐욕 → 시장 낙관\n"
                "- BTC Dominance 45% 유지 → 분산 자금 유입 제한적\n"
                "- DXY 103.2 → 달러 강세 → BTC 하방 압박\n"
                "- GBTC 자금 유출 소폭 → 단기 약세 요인\n"
                "- 옵션 만기: 75k–80k 최대 집중 → 저항 구간\n\n"
                "4. 📌 12시간 예측 및 전략\n"
                "- 상승 확률 62% / 하락 확률 38%\n"
                "- 근거: MACD 크로스 + 20/50 MA 정배열 vs DXY 강세\n"
                "- 전략: 단기적으로 상승 우위, 그러나 70k 저항 주의 → 부분 이익 실현 권장\n\n"
                "5. ⚠️ 예외 상황 실시간 감지\n"
                "- 규제·해킹·ETF 승인 등 특이 뉴스 즉시 알림 발송\n\n"
                "6. 🧾 이전 예측 검증 및 피드백\n"
                "- 12시간 전 예측(상승 58%) vs 실제 +3.5% 상승 → 예측 정확\n"
                "- 오차 원인: 고래 매도 일부 반영 미흡\n"
                "- 보완점: 대형 온체인 이체 모듈 강화\n"
            )}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

def format_profit_report_text():
    """실현/미실현 손익 리포트 생성"""
    # 실제 연동 전 예시 데이터
    realized_pnl = 31.4    # 실현 손익 (USD)
    unrealized_pnl = -5.2  # 미실현 손익 (USD)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"🧾 실현 손익: ${realized_pnl:.2f}\n"
        f"📉 미실현 손익: ${unrealized_pnl:.2f}\n"
        f"🕒 기준 시각: {now}"
    )
