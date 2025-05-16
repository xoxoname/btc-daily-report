import os, time, hmac, hashlib, requests

BASE_URL = "https://api.bitget.com"

def get_auth_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path + body
    signature = hmac.new(
        os.environ["BITGET_APISECRET"].encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return {
        "ACCESS-KEY": os.environ["BITGET_APIKEY"],
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": os.environ["BITGET_PASSPHRASE"],
        "Content-Type": "application/json"
    }

def fetch_bitget_wallet_balance():
    path = "/api/mix/v1/account/accounts?productType=USDT-FUTURES"
    url = BASE_URL + path
    headers = get_auth_headers("GET", path)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]

def fetch_bitget_positions():
    path = "/api/mix/v1/position/allPosition?productType=USDT-FUTURES"
    url = BASE_URL + path
    headers = get_auth_headers("GET", path)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]
