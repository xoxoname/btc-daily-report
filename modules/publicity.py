import os
import requests

def get_publicity_events():
    api_key = os.getenv("PUBLICITY_API_KEY")
    try:
        response = requests.get(
            "https://api.publicity.ai/v1/calendar/upcoming",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        data = response.json()
        events = [f"- {e['title']} ({e['date']})" for e in data.get("events", [])]
        return "\n".join(events)
    except Exception:
        return "- Publicity 일정 불러오기 실패"
