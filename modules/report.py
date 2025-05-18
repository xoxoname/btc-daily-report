import openai
import requests
import datetime
from modules.constants import OPENAI_API_KEY, PUBLICITY_API_KEY

openai.api_key = OPENAI_API_KEY

def get_coinbase_price():
    try:
        resp = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(resp.json()["data"]["amount"])
    except:
        return None

def get_publicity_events():
    try:
        headers = {"Authorization": f"Bearer {PUBLICITY_API_KEY}"}
        res = requests.get("https://api.publicity.com/v1/events/upcoming", headers=headers)
        data = res.json()
        events = [f"- {e['time']} {e['title']}" for e in data.get("events", []) if e.get("importance") == "high"]
        return "\n".join(events) if events else "- 고변동 이벤트 없음"
    except:
        return "- Publicity 일정 불러오기 실패"

def generate_report():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M (KST)")
    price = get_coinbase_price()
    events = get_publicity_events()
    prompt = f"""
[GPT 역할]
당신은 비트코인 시장 예측 시스템입니다. 다음 실시간 데이터를 기반으로 /report 형식에 맞춰 리포트를 생성하세요.

[실시간 입력 데이터]
- 현재 시각: {now}
- 현재 BTC 가격: ${price}
- 예정된 고변동 이벤트:
{events}

[출력 형식 요구사항]
- 제목: 📡 GPT 매동 예측 분석 리포트
- 포함 항목: 시장 이벤트, 기술적 분석, 심리 구조 분석, 향후 12시간 예측, 예외 감지, 예측 검증, 손익 정보, 멘탈 코멘트
- 줄바꿈, 이모지, 강조, 고정 제목, 한화 환산 예시 등은 이전 리포트와 동일하게 구성
- 오직 실제 수집된 정보만 해석할 것. 매번 다른 결과여야 함
"""
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "너는 비트코인 실시간 리포트 분석기다. 사용자가 제공한 정보로 매번 다른 정밀 분석을 수행하라."},
                      {"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ GPT 응답 실패: {str(e)}"

def generate_forecast():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M (KST)")
    price = get_coinbase_price()
    prompt = f"""
[GPT 역할]
당신은 비트코인 단기 예측 시스템입니다. 현재 가격과 추세 기반으로 향후 12시간 내 가격 흐름을 예측하세요.

- 현재 시각: {now}
- 현재 BTC 가격: ${price}

[형식 요구]
- 📈 오늘의 단기 매동 예측
- 기술/심리/구조 분석 요약 + 12시간 예측 확률
- 멘탈 코멘트 포함
"""
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "단기 시장 방향성을 고정 형식으로 예측하는 시스템"},
                      {"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Forecast 생성 실패: {str(e)}"

def generate_schedule():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M (KST)")
    events = get_publicity_events()
    return f"""
📆 자동 리포트 일정 안내
📅 기준 시각: {now}
━━━━━━━━━━━━━━━━━━━
🕓 정규 리포트 발송 시간 (KST 기준)
- 오전 9시
- 오후 1시
- 오후 5시
- 오후 11시

📡 예정 주요 이벤트 (Publicity 기준)
{events}
━━━━━━━━━━━━━━━━━━━
📌 명령어 요약
- /report: GPT 분석 리포트
- /forecast: 단기 매동 예측
- /profit: 현재 포지션 및 수익
- /schedule: 발송 시간 및 주요 일정
"""
