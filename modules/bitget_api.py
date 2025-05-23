
import requests
import time
import hmac
import hashlib
import base64
import json
import os

def get_positions():
    api_key = os.getenv("BITGET_APIKEY")
    secret_key = os.getenv("BITGET_APISECRET")
    passphrase = os.getenv("BITGET_PASSPHRASE")
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    request_path = "/api/mix/v1/position/singlePosition?productType=umcbl&symbol=BTCUSDT"
    url = "https://api.bitget.com" + request_path

    message = timestamp + method + request_path
    signature = base64.b64encode(
        hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    ).decode()

    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)
    return response.json()
