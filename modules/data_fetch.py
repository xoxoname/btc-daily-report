import time
import hmac
import hashlib
import requests
import pandas as pd
from .constants import BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE

BASE_URL = "https://api.bitget.com"

def _sign(method: str, path: str, timestamp: str, body: str = "") -> dict:
    message = timestamp + method.upper() + path + body
    signature = hmac.new(
        BITGET_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def fetch_spot_klines(symbol: str, granularity: int = 3600, limit: int = 200) -> pd.DataFrame:
    """
    symbol: e.g. "BTCUSDT"
    granularity: in seconds (60, 300, 3600, 86400)
    """
    path = f"/api/spot/v3/market/candles?symbol={symbol}&granularity={granularity}&limit={limit}"
    url = BASE_URL + path
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()  # [[timestamp, open, high, low, close, volume], ...]
    df = pd.DataFrame(data, columns=["time","open","high","low","close","volume"])
    df = df.astype({
        "time": "int64",
        "open": "float",
        "high": "float",
        "low": "float",
        "close": "float",
        "volume": "float"
    })
    df["dt"] = pd.to_datetime(df["time"], unit="s")
    return df.set_index("dt")

def fetch_ticker(symbol: str) -> dict:
    """현재가, 24h 변동 등 간단 ticker 정보"""
    path = f"/api/spot/v3/market/ticker?symbol={symbol}"
    url = BASE_URL + path
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()
