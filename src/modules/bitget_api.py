import os
import time
import hmac
import hashlib
import base64
import requests

BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_APISECRET = os.getenv("BITGET_APISECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

def _timestamp():
    return str(int(time.time() * 1000))

def _signature(timestamp, method, path, body, secret):
    message = f"{timestamp}{method.upper()}{path}{body}"
    return base64.b64encode(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()).decode()

def _headers(method, path, body=""):
    timestamp = _timestamp()
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": _signature(timestamp, method, path, body, BITGET_APISECRET),
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_btc_price():
    url = BASE_URL + "/api/spot/v1/market/ticker?symbol=BTCUSDT"
    r = requests.get(url)
    res = r.json()
    if res.get("code") != "00000":
        return None
    return float(res["data"]["close"])

def get_spot_balance_usdt():
    endpoint = "/api/spot/v1/account/assets"
    r = requests.get(BASE_URL + endpoint, headers=_headers("GET", endpoint))
    data = r.json()
    if data.get("code") != "00000":
        return None
    for asset in data.get("data", []):
        if asset["coinName"] == "USDT":
            return float(asset["available"])
    return 0.0

def get_btcusdt_position():
    endpoint = "/api/mix/v1/position/singlePosition?symbol=BTCUSDT&productType=umcbl"
    r = requests.get(BASE_URL + endpoint, headers=_headers("GET", endpoint))
    data = r.json()
    if data.get("code") != "00000":
        return {}
    return data.get("data", {})