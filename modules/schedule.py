from datetime import datetime, timedelta

def get_upcoming_events():
    now = datetime.now()
    return [
        {"event": "FOMC 회의", "time": (now + timedelta(hours=6)).strftime("%H:%M")},
        {"event": "미국 CPI 발표", "time": (now + timedelta(hours=10)).strftime("%H:%M")},
    ]

def format_schedule_text(events: list) -> str:
    if not events:
        return "📅 예정된 주요 일정이 없습니다."
    result = "📅 *예정된 주요 일정*\n"
    for event in events:
        result += f"- {event['event']}: {event['time']}\n"
    return result
