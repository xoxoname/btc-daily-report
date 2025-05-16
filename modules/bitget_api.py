import requests
import hmac
import hashlib
import time
import os

def _make_headers(api_key, secret_key, passphrase):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + "GET" + "/api/mix/v1/account/account"  # dummy
    sign = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()

    return {
        'ACCESS-KEY': api_key,
        'ACCESS-SIGN': sign,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }

def fetch_bitget_wallet_balance():
    api_key = os.environ['BITGET_APIKEY']
    secret_key = os.environ['BITGET_APISECRET']
    passphrase = os.environ['BITGET_PASSPHRASE']

    url = "https://api.bitget.com/api/mix/v1/account/account?productType=USDT-FUTURES"
    headers = _make_headers(api_key, secret_key, passphrase)
    res = requests.get(url, headers=headers).json()
    return res

def fetch_bitget_positions():
    api_key = os.environ['BITGET_APIKEY']
    secret_key = os.environ['BITGET_APISECRET']
    passphrase = os.environ['BITGET_PASSPHRASE']

    url = "https://api.bitget.com/api/mix/v1/position/allPosition?productType=USDT-FUTURES"
    headers = _make_headers(api_key, secret_key, passphrase)
    res = requests.get(url, headers=headers).json()
    return res
