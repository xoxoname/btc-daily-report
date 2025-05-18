import os
from modules.tls_adapter import session

def get_publicity_events():
    try:
        headers = {"Authorization": f"Bearer {os.getenv('PUBLICITY_API_KEY')}"}
        url = "https://api.publicity.com/v1/events/upcoming"
        r = session.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("🚨 Publicity API 오류:", e)
        return {"error": str(e)}
