import os
import requests
import hmac
import hashlib
import time

def _get_headers(api_key, api_secret, method, path, params=""):
    timestamp = str(int(time.time() * 1000))
    pre_hash = timestamp + method + path + params
    sign = hmac.new(api_secret.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": os.getenv("BITGET_PASSPHRASE"),
        "Content-Type": "application/json"
    }

def fetch_bitget_account_info():
    api_key = os.getenv("BITGET_APIKEY")
    api_secret = os.getenv("BITGET_APISECRET")
    path = "/api/mix/v1/account/accounts?productType=USDT-FUTURES"
    url = "https://api.bitget.com" + path
    headers = _get_headers(api_key, api_secret, "GET", path)
    res = requests.get(url, headers=headers)
    return res.json()

def fetch_bitget_positions():
    api_key = os.getenv("BITGET_APIKEY")
    api_secret = os.getenv("BITGET_APISECRET")
    symbol = "BTCUSDT_UMCBL"
    path = f"/api/mix/v1/position/singlePosition?symbol={symbol}&marginCoin=USDT"
    url = "https://api.bitget.com" + path
    headers = _get_headers(api_key, api_secret, "GET", path)
    res = requests.get(url, headers=headers)
    return res.json()