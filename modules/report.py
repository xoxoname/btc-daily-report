import openai
import requests
from modules.constants import OPENAI_API_KEY
from modules.utils import get_bitget_data

openai.api_key = OPENAI_API_KEY

def get_btc_price():
    try:
        r = requests.get("https://btc-daily-report.onrender.com/report")
        data = r.json()
        return float(data["btc_price_usd"]), float(data["btc_price_krw"])
    except:
        return 0.0, 0.0

def generate_full_report():
    usd, krw = get_btc_price()
    prompt = f"""
📡 [비트코인 정규 리포트 요청]

현재 비트코인 가격은 ${usd:.2f} ≈ {krw:,.0f}원입니다.

아래 기준에 따라 전체 시장 리포트를 실시간 기준으로 작성해줘. 각 항목마다 [호재/중립/악재] 중 하나로 분류하고, 핵심 요점만 이모지와 함께 작성해.

1. 📌 시장 뉴스 및 이벤트 요약
2. 📈 기술 분석 (RSI, MACD, 이평선 등)
3. 🧠 심리 및 구조 분석 (펀딩비, 롱숏비, 공포탐욕지수 등)
4. ⏱ 12시간 매매 동향 전망 (상승/하락/횡보 확률 포함)
5. 🚨 예외 상황 감지 (있을 경우만)
6. 🔁 이전 예측 적중 여부 검증 및 피드백
7. 💰 수익 요약 (실현/미실현 손익, 오늘 수익, 총 수익률) → *BTC 단위 없이*, $USD 및 원화로만
8. 😌 멘탈 안정 코멘트 (위로 멘트 + 현실 비교, 예: 알바 대비 수익 등)

📌 보고서는 마크다운 형식으로, 이모지 포함, 줄바꿈 및 강조를 사용하여 시각적으로 읽기 좋게 작성해줘.
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content

def generate_profit_report():
    usdkrw = get_btc_price()[1]
    bitget = get_bitget_data()
    realized = bitget["realized"]
    unrealized = bitget["unrealized"]
    total = realized + unrealized
    krw_realized = realized * usdkrw
    krw_unrealized = unrealized * usdkrw
    krw_total = total * usdkrw

    prompt = f"""
📊 [비트코인 수익 리포트 요청]

현재 실현 손익은 ${realized:.2f} ≈ {krw_realized:,.0f}원,  
미실현 손익은 ${unrealized:.2f} ≈ {krw_unrealized:,.0f}원,  
총 수익은 ${total:.2f} ≈ {krw_total:,.0f}원입니다.

이 데이터를 반영하여 아래 항목을 보고서 형식으로 작성해줘:

1. 💵 실현 손익 / 미실현 손익 → *BTC 없이*, $USD 및 원화만
2. 📅 오늘 수익 → $USD 및 원화만
3. 📈 총 수익률 (%) 및 수익 총액 ($ + KRW)
4. ⏱ 최근 7일 수익 유지 여부 (예/아니오 + 간단 요약)
5. 🏪 알바 수익과 비교 (주 20시간 기준 월 150만원과 비교)
6. 😌 멘탈 안정 코멘트 (현재 상황에 맞는 위로 멘트)

📌 이모지와 마크다운 형식 사용, 불필요한 설명 없이 핵심만 요약해줘.
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content

def generate_prediction():
    prompt = """
📈 [비트코인 향후 12시간 매매 전망 요청]

실시간 데이터 기준으로 아래 항목 작성:

1. 상승/하락/횡보 확률 (%) 제공
2. 📊 기술적 분석 요약 (RSI, MACD 등)
3. 🧠 심리적 분석 요약 (공포탐욕, 펀딩비 등)
4. 구조적 분석 요약 (롱/숏 비율, 유동성, 옵션 등)
5. 🧭 전략 요약 (대기/진입/청산 판단 등)
6. 😌 위로 코멘트 (심리 안정 멘트)
7. 오늘 수익 상태 반영 문장

📌 줄바꿈, 이모지, 마크다운 구조 사용. 요약은 [긍정/중립/주의] 등으로 표시.
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content
