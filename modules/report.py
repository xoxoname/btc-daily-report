import openai
import requests
import datetime
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
    📌 [BTC 시장 리포트 요청]
    현재 비트코인 가격은 ${usd:.2f} ≈ {krw:,.0f}원입니다.
    - 기술적 지표 분석
    - 시장 구조 및 심리 분석
    - 향후 12시간 매매 동향 전망 (확률 포함)
    - 예외 상황 여부
    - 이전 예측 적중 여부
    - 오늘 수익 및 수익률
    - 멘탈 코멘트 포함

    위 기준으로 가장 정밀한 분석을 한국어로 작성해줘. GPT 캐시 없이 최신 정보 기준으로.
    """
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return res.choices[0].message.content

def generate_profit_report():
    prompt = """
    📊 비트코인 수익 리포트 요청:
    - 실현 손익 / 미실현 손익 / 오늘 수익 / 총 수익률 계산
    - 각 수치 옆에 한화 환산
    - 최근 7일 수익 유지 여부
    - 편의점 알바 수익 비교
    - 불안 심리 완화 멘트 작성
    한국어로 전체 보고서 형식으로 작성해줘.
    """
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return res.choices[0].message.content

def generate_prediction():
    prompt = """
    🧠 비트코인 향후 12시간 매매 예측 요청:
    - 상승/하락/횡보 확률
    - 구조적 요인 요약
    - 기술적/심리적 분석 포함
    - 전략 요약 및 위로 멘트 포함
    - 오늘 수익 상태 반영

    위 내용을 실시간 데이터 기준으로 작성해줘. 자연어 한국어 형식으로.
    """
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.45,
    )
    return res.choices[0].message.content
