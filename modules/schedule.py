import datetime
from pytz import timezone

def generate_schedule_report():
    today = datetime.datetime.now(timezone("Asia/Seoul"))
    formatted_time = today.strftime("⏱️ 수집 시각: %Y년 %m월 %d일 %p %I:%M (KST)").replace("AM", "오전").replace("PM", "오후")

    body = f"""
{formatted_time}

📅 향후 7일간 주요 일정 (/일정 명령어 예시)

━━━━━━━━━━━━━━━━━━━━

| 날짜 (KST) | 이벤트 | 예상 영향 |
|------------|--------|------------|
| 5월 17일 | 트럼프 대통령의 암호화폐 관련 연설 | 시장에 긍정적 신호 제공 가능성 |
| 5월 20일 | 연준의 금리 결정 발표 | 시장 변동성 증가 예상 |
| 5월 22일 | 미국-중국 무역 협상 회담 | 시장 안정성에 영향 가능성 |
| 5월 25일 | 비트코인 관련 국제 컨퍼런스 | 시장 관심도 증가 예상 |
| 5월 26일 | 한국은행 기준금리 발표 | 원화 약세 → BTC/USDT 유입 가능성 |
| 5월 28일 | 미국 4월 개인소비지출(PCE) 발표 | 인플레이션 압력 확인 지표 |
| 5월 30일 | SEC 위원장 암호화폐 청문회 예정 | 규제 방향성 불확실성 증가 |

━━━━━━━━━━━━━━━━━━━━

📌 일정은 시장에 따라 변경될 수 있으며, 주요 이벤트 직후에는 별도 긴급 리포트로 안내됩니다.
"""
    return body.strip()
