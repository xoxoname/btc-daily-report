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

def get_usdt_balance():
    endpoint = "/api/spot/v1/account/assets"
    headers = get_headers("GET", endpoint)
    response = requests.get(BASE_URL + endpoint, headers=headers)
    data = response.json()
    if data.get("code") != "00000":
        raise Exception(f"Bitget API 오류: {data.get('msg')}")
    for asset in data.get("data", []):
        if asset["coinName"] == "USDT":
            return float(asset["available"])
    return 0.0

def get_btcusdt_position():
    endpoint = "/api/mix/v1/position/singlePosition?productType=umcbl&symbol=BTCUSDT"
    headers = get_headers("GET", endpoint)
    response = requests.get(BASE_URL + endpoint, headers=headers)
    data = response.json()
    if data.get("code") != "00000":
        raise Exception(f"Bitget API 오류: {data.get('msg')}")
    return data.get("data", {})