import requests
import time
import hmac
import hashlib
import json
from datetime import datetime
import pytz

from modules.constants import (
    BITGET_APIKEY,
    BITGET_APISECRET,
    BITGET_PASSPHRASE,
)


def get_kst_now():
    return datetime.now(pytz.timezone("Asia/Seoul"))


def format_currency(value):
    return f"{value:,.2f}"


def fetch_coinbase_price():
    url = "https://api.coinbase.com/v2/prices/BTC-USDT/spot"
    response = requests.get(url)
    if response.status_code == 200:
        return float(response.json()['data']['amount'])
    return None


def fetch_bitget_position_data():
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    request_path = "/api/mix/v1/position/singlePosition?symbol=BTCUSDT_UMCBL&marginCoin=USDT"
    prehash_string = timestamp + method + request_path
    signature = hmac.new(BITGET_APISECRET.encode(), prehash_string.encode(), hashlib.sha256).hexdigest()

    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
    }

    url = "https://api.bitget.com" + request_path
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()['data']
        if data:
            return {
                "entryPrice": float(data['entryPrice']),
                "marketPrice": float(data['marketPrice']),
                "leverage": float(data['leverage']),
                "amount": float(data['total']),
                "unrealizedPL": float(data['unrealizedPL']),
                "margin": float(data['margin']),
            }
    return None
