import os
import time
import hmac
import hashlib
import base64
import requests
import json

BASE_URL = "https://api.bitget.com"

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")


def _get_headers(method, request_path, body=""):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{request_path}{body}"
    signature = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    signature_base64 = base64.b64encode(signature).decode()

    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature_base64,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }


def get_account_assets():
    url = "/api/v2/account/assets"
    headers = _get_headers("GET", url)
    response = requests.get(BASE_URL + url, headers=headers)
    return response.json()


def get_positions(symbol="BTCUSDT_UMCBL"):
    url = f"/api/v2/mix/position/single?symbol={symbol}&marginCoin=USDT"
    headers = _get_headers("GET", url)
    response = requests.get(BASE_URL + url, headers=headers)
    return response.json()


def get_position_pnl(position):
    entry_price = float(position.get("entryPrice", 0))
    current_price = float(position.get("marketPrice", 0))
    size = float(position.get("total", 0))
    side = position.get("holdSide", "long")

    if entry_price == 0 or size == 0:
        return 0.0

    pnl = (current_price - entry_price) * size if side == "long" else (entry_price - current_price) * size
    return pnl


def get_total_profit_usdt():
    result = get_positions()
    if result.get("msg") != "success":
        return {"error": "API fetch failed."}

    position = result.get("data")
    if not position:
        return {"error": "No position data."}

    pnl = get_position_pnl(position)
    return {
        "symbol": position.get("symbol"),
        "entryPrice": float(position.get("entryPrice")),
        "marketPrice": float(position.get("marketPrice")),
        "size": float(position.get("total")),
        "side": position.get("holdSide"),
        "pnl": pnl
    }
