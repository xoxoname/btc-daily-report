import requests
import time
import hmac
import hashlib
import base64
import json
import os

def bitget_signature(api_secret, params, timestamp, method, request_path):
    if params:
        param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    else:
        param_str = ''
    prehash = f"{timestamp}{method.upper()}{request_path}{param_str}"
    return base64.b64encode(hmac.new(api_secret.encode('utf-8'), prehash.encode('utf-8'), digestmod=hashlib.sha256).digest()).decode()

def get_position(api_key, api_secret, passphrase, symbol="BTCUSDT_UMCBL", marginCoin="USDT"):
    path = "/api/mix/v1/position/singlePosition"
    url = "https://api.bitget.com" + path
    timestamp = str(int(time.time() * 1000))
    params = {
        "symbol": symbol,
        "marginCoin": marginCoin
    }
    sign = bitget_signature(api_secret, params, timestamp, "GET", path)
    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json"
    }
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    pos_data = data.get("data", [])
    # 데이터 형태 보정
    if isinstance(pos_data, dict):
        pos_data = [pos_data]
    elif not isinstance(pos_data, list):
        pos_data = []
    if not pos_data:
        return None
    return pos_data[0]
