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
        events = [f"- {e['time']} {e['title']}" for e in data.get("events", []) if "BTC" in e.get("title", "") or e.get("importance") == "high"]
        return "\n".join(events) if events else "- Publicity 고변동 이벤트 없음"
    except:
        return "- Publicity 이벤트 로딩 실패"

def generate_report():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M (KST)")
    price = get_coinbase_price()
    events = get_publicity_events()
    prompt = f"""
당신은 비트코인 시장 전문가입니다. 다음 정보를 바탕으로 고정 포맷의 분석 리포트를 생성하세요:

- 현재 시각: {now}
- 현재 BTC 가격: ${price}
- 예정된 이벤트:
{events}

[출력 포맷]
📡 GPT 매동 예측 분석 리포트
📅 기준 시각: {now}
(이후 형식은 당신이 작성하며 고정 포맷과 실제 자료 기반 분석을 반드시 포함하세요.)
"""
    try:
        res = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "형식을 고정하고 실제 시장 자료로 분석하는 비트코인 리포트 생성기입니다."},
                      {"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ GPT 응답 실패: {str(e)}"
