import requests
import os

def fetch_position():
    url = "https://api.bitget.com/api/mix/v1/position/singlePosition"
    params = {
        "symbol": "BTCUSDT",
        "marginCoin": "USDT",
        "productType": "umcbl"
    }
    headers = {
        "ACCESS-KEY": os.getenv("BITGET_APIKEY"),
        "ACCESS-SIGN": "debug-signature",
        "ACCESS-TIMESTAMP": "debug-time",
        "ACCESS-PASSPHRASE": os.getenv("BITGET_PASSPHRASE"),
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers, params=params)
    return response.text
