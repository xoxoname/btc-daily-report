from datetime import datetime
from modules.exchange import fetch_account_info, fetch_position_info
from modules.publicity import fetch_publicity_events
from modules.openai_bot import generate_forecast

def generate_report(command="/report"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pub = fetch_publicity_events()
    acc = fetch_account_info()
    pos = fetch_position_info()

    prompt = f"시각: {now}\nPublicity 이벤트: {pub}\n계정 정보: {acc}\n포지션 정보: {pos}\n명령어: {command}\n위 정보를 바탕으로 {command} 리포트를 출력 형식에 맞게 작성해줘."

    forecast = generate_forecast(prompt)

    title_map = {
        "/report": "📡 GPT 매동 예측 분석 리포트",
        "/forecast": "📈 오늘의 단기 매동 예측",
        "/profit": "💰 현재 수익 현황 요약",
        "/schedule": "📆 자동 리포트 일정 안내",
    }

    title = title_map.get(command, "📡 GPT 리포트")
    message = f"""{title}  
📅 기준 시각: {now} (KST)
━━━━━━━━━━━━━━━━━━━
{forecast}
━━━━━━━━━━━━━━━━━━━
"""
    return message