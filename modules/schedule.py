import datetime
from pytz import timezone

def generate_schedule_report():
    now = datetime.datetime.now(timezone("Asia/Seoul"))
    formatted_time = now.strftime("⏱️ 수집 시각: %Y년 %m월 %d일 %p %I:%M (KST)").replace("AM", "오전").replace("PM", "오후")

    schedule_table = """📅 향후 7일간 주요 일정 (/일정 명령어 예시)

날짜 (KST)       이벤트                         예상 영향
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5월 17일       트럼프 대통령 연설               📈 긍정적 신호 가능성
5월 20일       연준 금리 결정 발표              📉 변동성 증가 예상
5월 22일       미국-중국 무역 협상 회담         📉 시장 불확실성 확대
5월 25일       비트코인 관련 국제 컨퍼런스       📈 관심도 상승 가능성
5월 26일       SEC 비트코인 ETF 심사 데드라인   📈 주요 모멘텀 예상
5월 28일       주요 기술기업 실적 발표           📉 나스닥 변동성 → BTC 영향 가능
5월 30일       FOMC 의사록 공개                 📊 중립

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
※ 이벤트는 실시간 뉴스에 따라 조정될 수 있습니다."""

    return f"{formatted_time}\n\n{schedule_table}"
