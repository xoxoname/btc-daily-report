import os
import requests

PUBLICITY_BASE_URL = "https://api.publicity.com/v1"

def fetch_upcoming_events():
    api_key = os.getenv("PUBLICITY_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = f"{PUBLICITY_BASE_URL}/events/upcoming?importance=high&market=crypto"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        return {"error": str(e)}