from modules.utils import get_current_timestamp

def generate_schedule():
    return f"""📆 {get_current_timestamp()} 기준 향후 주요 일정

━━━━━━━━━━━━━━━━━━━━

📅 5월 17일 (금)
- 트럼프 대통령 암호화폐 관련 연설 (22:00 KST)

📅 5월 20일 (월)
- 연준 금리 결정 발표

📅 5월 22일 (수)
- 미중 무역 협상 회담

📅 5월 25일 (토)
- 비트코인 국제 컨퍼런스

━━━━━━━━━━━━━━━━━━━━

⏱ *일정은 시장 변동성과 예측 정확도에 큰 영향을 미칠 수 있습니다.*
"""
