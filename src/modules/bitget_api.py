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

def get_account_info():
    endpoint = "/api/mix/v1/account/account?productType=umcbl"
    headers = get_headers("GET", endpoint)
    response = requests.get(BASE_URL + endpoint, headers=headers)
    return response.json()