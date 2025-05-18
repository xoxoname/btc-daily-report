from datetime import datetime
from modules.exchange import BitgetAPI
from modules.publicity import get_publicity_events

def generate_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M (KST)")
    bitget = BitgetAPI()
    try:
        acc = bitget.get_account_info()
        pos = bitget.get_position_info()
        pub = get_publicity_events()

        account_data = acc.get("data", {})
        position_data = pos.get("data", {})
        event_info = pub if isinstance(pub, dict) and "error" not in pub else {}

        return f"""📡 GPT 매동 예측 분석 리포트  
📅 기준 시각: {now}

━━━━━━━━━━━━━━━━━━━  
📌 계정 정보
- 결과: {account_data}

━━━━━━━━━━━━━━━━━━━  
📌 포지션 정보
- 결과: {position_data}

━━━━━━━━━━━━━━━━━━━  
📌 Publicity 이벤트
- 결과: {event_info}

━━━━━━━━━━━━━━━━━━━  
📌 분석 결과 요약
- 현재 시장 상황 및 포지션 기반 분석 내용 포함 예정

━━━━━━━━━━━━━━━━━━━"""
    except Exception as e:
        return f"""📡 GPT 매동 예측 분석 리포트  
📅 기준 시각: {now}
━━━━━━━━━━━━━━━━━━━
❌ 리포트 생성 실패: {str(e)}
━━━━━━━━━━━━━━━━━━━"""
