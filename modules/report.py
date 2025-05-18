from modules.bitget_api import fetch_position_info
from modules.utils import get_btc_price, format_datetime
from modules.gpt import ask_gpt
from modules.publicity import get_publicity_events
import datetime

def generate_report():
    try:
        btc_price = get_btc_price()
        now = format_datetime(datetime.datetime.now())
        gpt_response = ask_gpt(f"현재 비트코인 가격은 ${btc_price}입니다. 기술적 분석, 심리 분석, 예외 감지, 예측 검증, 손익 분석 및 멘탈 코멘트를 포함한 전체 리포트를 작성해줘.")
        return f"📡 GPT 매동 예측 분석 리포트

🕘 작성 시각: {now}

📊 현재 BTC 가격: ${btc_price}

{gpt_response}"
    except Exception as e:
        return f"⚠️ GPT 분석 실패: {str(e)}"

def generate_profit():
    try:
        result = fetch_position_info()
        return result
    except Exception as e:
        return f"⚠️ Bitget 응답 오류: {str(e)}"

def generate_forecast():
    try:
        btc_price = get_btc_price()
        gpt_response = ask_gpt(f"비트코인 현재 가격은 ${btc_price}야. 다음 12시간의 매매 동향을 예측해줘. 확률과 함께.")
        now = format_datetime(datetime.datetime.now())
        return f"📈 단기 매매 동향 예측

🕘 기준 시각: {now}

📊 현재 BTC 가격: ${btc_price}

{gpt_response}"
    except Exception as e:
        return f"⚠️ GPT 예측 실패: {str(e)}"

def generate_schedule():
    try:
        events = get_publicity_events()
        now = format_datetime(datetime.datetime.now())
        return f"""📆 자동 리포트 일정 안내
📅 기준 시각: {now}
━━━━━━━━━━━━━━━━━━━
🕓 정규 리포트 발송 시간 (KST 기준)
- 오전 9시
- 오후 1시
- 오후 5시
- 오후 11시

📡 예정 주요 이벤트 (Publicity 기준)
{events if events else '- Publicity 일정 없음'}
━━━━━━━━━━━━━━━━━━━"""
    except Exception as e:
        return f"⚠️ 일정 생성 실패: {str(e)}"
