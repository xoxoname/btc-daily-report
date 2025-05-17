import openai
import requests
from modules.constants import OPENAI_API_KEY

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
📡 [BTC 시장 리포트 요청]

현재 비트코인 가격은 ${usd:.2f} ≈ {krw:,.0f}원입니다.  
다음 항목을 기반으로 **실시간 시장 리포트**를 작성해주세요:

1. 📌 시장 뉴스 및 이벤트 요약 (예: CPI, ETF, 정책 발표 등)
2. 📈 기술 분석 (RSI, MACD 등 주요 지표 기반, 호재/중립/악재 구분)
3. 🧠 심리 및 구조 분석 (공포탐욕지수, 펀딩비, 롱/숏 비율 등)
4. ⏱ 향후 12시간 매매 전망 (상승/하락/횡보 확률 포함)
5. 🚨 예외 상황 요약 (있는 경우만)
6. 🔁 이전 예측 검증 및 피드백
7. 💰 오늘 수익 및 수익률 (예시 형식 사용)
8. 😌 멘탈 코멘트 (알바 비교 + 위로 문장 포함)

📌 출력은 마크다운 형식, 줄바꿈, 이모지 포함, 한글로 작성  
불필요한 설명 없이 핵심 위주로, 꼭 투자자에게 전달하는 리포트처럼 구성
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content

def generate_profit_report():
    prompt = """
📊 [비트코인 수익 리포트 작성 요청]

아래 항목을 기준으로 보고서 스타일로 작성해줘. 이모지, 줄바꿈, 마크다운 형식 사용해서 읽기 쉽게 만들고, GPT 캐시 사용 없이 실시간 데이터 기반으로 작성해.

1. 💵 *실현 손익*, *미실현 손익* (BTC + 원화 병기)
2. 📅 *오늘 수익* (BTC + 원화 병기)
3. 📈 *총 수익률* (% + 원화 총합 병기)
4. ⏱ *최근 7일 수익 유지 여부*
5. 🏪 *편의점 알바 수익과 비교* (알바 수익 vs 투자 수익)
6. 🧘‍♀️ *멘탈 안정 코멘트* (심리 방어 멘트, 격려 멘트)

📌 반드시 한국어로, 문장 길이는 적당히 요약해.  
절대로 일반적인 설명이나 과거 통계만으로 작성하지 말고, 실시간 투자자에게 전달하는 리포트처럼 써줘.
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content

def generate_prediction():
    prompt = """
📈 [비트코인 12시간 매매 동향 예측 요청]

다음 기준으로 분석 보고서 스타일로 작성해주세요:

1. 상승/하락/횡보 확률 예측
2. 기술적 분석 요약 (RSI, 이평선, 패턴 등)
3. 심리 및 구조적 분석 요약 (공포탐욕, 펀딩비, 롱숏비 등)
4. 전략 요약 (지금 진입할지, 기다릴지 등)
5. 멘탈 안정 코멘트 (불안한 투자자 위한 위로 멘트)
6. 오늘 수익/손실 반영 (긍정적/부정적 상황 모두 대응)

📌 한국어로 작성, 이모지 포함, 줄바꿈 사용, 마크다운 형식
"""
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content
