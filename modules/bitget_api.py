import time
import requests
import hmac
import hashlib
from modules.constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

def sign_params(method, endpoint, params=''):
    timestamp = str(int(time.time() * 1000))
    pre_hash = timestamp + method + endpoint + params
    signature = hmac.new(
        BITGET_APISECRET.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).hexdigest()
    return timestamp, signature

def get_headers(method, endpoint, params=''):
    timestamp, sign = sign_params(method, endpoint, params)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_positions():
    endpoint = "/api/mix/v1/position/singlePosition?symbol=BTCUSDT&marginCoin=USDT"
    url = "https://api.bitget.com" + endpoint
    headers = get_headers("GET", endpoint)
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get('data', {})

def get_assets():
    endpoint = "/api/v2/mix/account/accounts?productType=USDT-FUTURES"
    url = "https://api.bitget.com" + endpoint
    headers = get_headers("GET", endpoint)
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    for d in r.json().get('data', []):
        if d['marginCoin'] == 'USDT':
            return d
    return {}

def get_ticker():
    url = "https://api.bitget.com/api/spot/v1/market/ticker?symbol=BTCUSDT"
    r = requests.get(url)
    r.raise_for_status()
    return float(r.json()["data"]["close"])
