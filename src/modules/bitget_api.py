import time
import hmac
import hashlib
import base64
import os
import requests

BITGET_APIKEY = os.getenv("BITGET_APIKEY")
BITGET_APISECRET = os.getenv("BITGET_APISECRET")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def get_signature(timestamp, method, request_path, body, secret):
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    return base64.b64encode(hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()

def get_headers(method, endpoint, body=""):
    timestamp = get_timestamp()
    signature = get_signature(timestamp, method, endpoint, body, BITGET_APISECRET)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_btcusdt_position_info():
    endpoint = "/api/mix/v1/position/singlePosition?symbol=BTCUSDT&productType=umcbl"
    headers = get_headers("GET", endpoint)
    url = BASE_URL + endpoint
    res = requests.get(url, headers=headers)
    data = res.json()
    if data["code"] != "00000":
        raise Exception(f"Bitget API 오류: {data['msg']}")
    return data["data"]

def get_spot_balance_usdt():
    endpoint = "/api/spot/v1/account/assets"
    headers = get_headers("GET", endpoint)
    url = BASE_URL + endpoint
    res = requests.get(url, headers=headers)
    data = res.json()
    if data["code"] != "00000":
        raise Exception(f"Bitget API 오류: {data['msg']}")
    for asset in data["data"]:
        if asset["coinName"] == "USDT":
            return float(asset["available"])
    return 0.0

def get_btc_price():
    url = "https://api.bitget.com/api/spot/v1/market/ticker?symbol=BTCUSDT"
    res = requests.get(url)
    data = res.json()
    if data["code"] != "00000":
        raise Exception(f"Bitget 가격 API 오류: {data['msg']}")
    return float(data["data"]["close"])