import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount("https://", TLSAdapter())

def fetch_publicity_events():
    try:
        key = os.getenv("PUBLICITY_API_KEY")
        url = "https://api.publicity.com/v1/events/upcoming"
        headers = {"Authorization": f"Bearer {key}"}
        response = session.get(url, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print(f"🚨 Publicity API 오류: {e}")
        return {"error": str(e)}