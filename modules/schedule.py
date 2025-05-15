import pytz
from datetime import datetime, timedelta

def get_upcoming_events():
    now = datetime.now(pytz.timezone("Asia/Seoul"))
    return [
        {"time": (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M"), "title": "미국 CPI 발표", "impact": "높음"},
        {"time": (now + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "title": "FOMC 의사록 공개", "impact": "중간"},
        {"time": (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), "title": "BTC 온체인 지표", "impact": "낮음"},
    ]

def format_schedule_text(events: list) -> str:
    header = "📅 *향후 1주일 일정*\n"
    if not events:
        return header + "일정이 없습니다."
    return header + "\n".join([f"- `{e['time']}`: {e['title']} (영향: {e['impact']})" for e in events])
