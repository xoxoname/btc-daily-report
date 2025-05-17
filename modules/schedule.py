from datetime import datetime

def generate_schedule():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""🕒 기준 시각: {now}
📅 향후 7일간 주요 일정 (/schedule 명령어 예시)
━━━━━━━━━━━━━━━━━━━━
📌 5/18 (토) 21:30 — FOMC 의사록 공개 (중간)
📌 5/20 (월) 09:00 — 🇰🇷 수출입지수 발표 (낮음)
📌 5/22 (수) 03:00 — 🇺🇸 파월 의장 발언 예정 (높음)
📌 5/23 (목) 21:30 — 🇺🇸 신규 실업수당 청구건수 (중간)
━━━━━━━━━━━━━━━━━━━━
📍 GPT 분석 기준: 시장 영향도 높은 일정만 선별
"""