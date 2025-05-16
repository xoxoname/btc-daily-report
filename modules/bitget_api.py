import requests
import time
import hmac
import hashlib
import os

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

def _get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method}{path}{body}"
    signature = hmac.new(
        API_SECRET.encode(),
        prehash.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

def fetch_wallet_balance():
    path = "/api/v2/account/accounts"
    url = BASE_URL + path
    headers = _get_headers("GET", path)
    res = requests.get(url, headers=headers).json()
    for acc in res.get("data", []):
        if acc["marginCoin"] == "USDT":
            return float(acc["available"]), float(acc["totalEquity"])
    return 0.0, 0.0

def fetch_positions():
    path = "/api/v2/position/allPosition"
    url = BASE_URL + path + "?productType=umcbl"
    headers = _get_headers("GET", path + "?productType=umcbl")
    res = requests.get(url, headers=headers).json()
    return res.get("data", [])
