import os
import httpx

client = httpx.Client(verify=False, timeout=10)

def fetch_publicity_events():
    try:
        key = os.getenv("PUBLICITY_API_KEY")
        url = "https://api.publicity.com/v1/events/upcoming"
        headers = {"Authorization": f"Bearer {key}"}
        response = client.get(url, headers=headers)
        return response.json()
    except Exception as e:
        print(f"🚨 Publicity API 오류: {e}")
        return {"error": str(e)}