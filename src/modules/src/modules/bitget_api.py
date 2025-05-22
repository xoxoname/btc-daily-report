
import requests
import os
import time
import hashlib
import hmac
import base64

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def _get_headers(method, request_path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = timestamp + method + request_path + body
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    sign_b64 = base64.b64encode(sign).decode()

    return {
        'ACCESS-KEY': API_KEY,
        'ACCESS-SIGN': sign_b64,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json'
    }

def get_positions():
    path = "/api/mix/v1/position/singlePosition?symbol=BTCUSDT&marginCoin=USDT"
    url = "https://api.bitget.com" + path
    headers = _get_headers("GET", path)
    response = requests.get(url, headers=headers)
    return response.json()
