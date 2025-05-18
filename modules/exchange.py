import os
import time
import hmac
import hashlib
import requests

BASE_URL = "https://api.bitget.com"

def _get_headers(api_key, api_secret, timestamp, method, path, query=""):
    to_sign = f"{timestamp}{method}{path}{query}"
    sign = hmac.new(api_secret.encode(), to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": str(timestamp),
        "ACCESS-PASSPHRASE": os.getenv("BITGET_PASSPHRASE"),
        "Content-Type": "application/json"
    }

def fetch_account_info():
    timestamp = int(time.time() * 1000)
    path = "/api/mix/v1/account/accounts?productType=USDT-FUTURES"
    url = f"{BASE_URL}{path}"
    headers = _get_headers(os.getenv("BITGET_APIKEY"), os.getenv("BITGET_APISECRET"), timestamp, "GET", "/api/mix/v1/account/accounts", "")
    response = requests.get(url, headers=headers)
    return response.json()

def fetch_position_info():
    timestamp = int(time.time() * 1000)
    symbol = "BTCUSDT_UMCBL"
    path = f"/api/mix/v1/position/singlePosition?symbol={symbol}&marginCoin=USDT"
    url = f"{BASE_URL}{path}"
    headers = _get_headers(os.getenv("BITGET_APIKEY"), os.getenv("BITGET_APISECRET"), timestamp, "GET", "/api/mix/v1/position/singlePosition", f"?symbol={symbol}&marginCoin=USDT")
    response = requests.get(url, headers=headers)
    return response.json()