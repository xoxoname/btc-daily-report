from datetime import datetime, timedelta

def get_upcoming_events():
    return [
        {"event": "🇺🇸 CPI 발표", "time": "2025-05-15 21:30"},
        {"event": "🇺🇸 FOMC 미팅", "time": "2025-05-22 03:00"},
    ]

def format_schedule_text(events: list) -> str:
    header = "🗓 *주요 일정*\n"
    body = "\n".join([f"- {e['event']}: {e['time']}" for e in events])
    return header + body
