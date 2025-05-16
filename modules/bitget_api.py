import os
import requests

BASE_URL = "https://api.bitget.com"
HEADERS = {
    "ACCESS-KEY": os.getenv("BITGET_APIKEY"),
    "ACCESS-SIGN": "",
    "ACCESS-TIMESTAMP": "",
    "ACCESS-PASSPHRASE": os.getenv("BITGET_PASSPHRASE"),
    "Content-Type": "application/json"
}

def fetch_bitget_positions():
    # 실제 요청 구현 필요
    return [
        {"symbol": "BTCUSDT", "entryPrice": "10000", "markPrice": "10200", "unrealizedPnl": "200"}
    ]

def fetch_bitget_wallet_balance():
    return {
        "totalEquity": 10500,
        "available": 3000
    }
