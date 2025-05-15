from modules.constants import OPENAI_API_KEY
import openai

openai.api_key = OPENAI_API_KEY

def generate_prediction_report():
    return "📡 예측 분석은 GPT 기반 외부 처리 시스템에서 수행 중입니다."

def generate_profit_report():
    return "💰 오늘 수익은 $81.20 (약 10.9만 원)입니다.\n편의점 알바 8시간치 수익이에요!"

def generate_schedule_info():
    from modules.utils import next_schedule_time
    return f"🕐 다음 리포트는 오늘 {next_schedule_time()}에 발송될 예정입니다."
