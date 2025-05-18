from datetime import datetime
from modules.exchange import fetch_account_info, fetch_position_info
from modules.publicity import fetch_publicity_events
from modules.openai_bot import generate_forecast

def generate_full_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pub = fetch_publicity_events()
    acc = fetch_account_info()
    pos = fetch_position_info()

    prompt = f"시각: {now}\nPublicity 이벤트: {pub}\n계정 정보: {acc}\n포지션 정보: {pos}\n위 데이터를 기반으로 GPT 리포트를 완전한 형식으로 작성해주세요."
    forecast = generate_forecast(prompt)

    message = f"""📡 GPT 매동 예측 분석 리포트  
📅 기준 시각: {now} (KST)
━━━━━━━━━━━━━━━━━━━
{forecast}
━━━━━━━━━━━━━━━━━━━
"""
    return message