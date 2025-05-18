import os
import requests

def fetch_publicity_events():
    api_key = os.getenv("PUBLICITY_API_KEY")
    url = "https://api.publicity.com/v1/events/upcoming?importance=high&market=crypto"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        res = requests.get(url, headers=headers)
        return res.json()
    except Exception as e:
        return {"error": str(e)}