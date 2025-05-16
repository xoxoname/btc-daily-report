import requests
import time
import hmac
import hashlib
import json
from modules.constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE, OPENAI_API_KEY

def fetch_coinbase_price():
    url = "https://api.coinbase.com/v2/prices/spot?currency=USD"
    response = requests.get(url)
    return float(response.json()["data"]["amount"])

def fetch_bitget_position_data():
    url = "/api/mix/v1/position/singlePosition"
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    query = "symbol=BTCUSDT_UMCBL&marginCoin=USDT"
    body = ""

    sign = make_signature(timestamp, method, url + "?" + query, body)

    headers = {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

    full_url = f"https://api.bitget.com{url}?{query}"
    res = requests.get(full_url, headers=headers)
    data = res.json()

    if "data" not in data or data["data"] is None:
        return None

    pos = data["data"]
    entry_price = float(pos["openPrice"])
    current_price = fetch_coinbase_price()
    size = float(pos["total"])
    leverage = float(pos["leverage"])
    margin = float(pos["margin"])

    pnl = (current_price - entry_price) * size
    pnl_percent = (pnl / margin) * 100 if margin != 0 else 0

    realized_pnl = float(pos.get("realizedProfit", 0.0))

    return {
        "symbol": pos["symbol"],
        "entry_price": entry_price,
        "current_price": current_price,
        "unrealized_pnl": pnl,
        "realized_pnl": realized_pnl,
        "pnl_percent": pnl_percent,
        "initial_asset": 2100.00,  # 사용자가 직접 입력한 실입금 자산
        "total_asset": 2100.00 + pnl + realized_pnl
    }

def make_signature(timestamp, method, request_path, body):
    prehash_string = f"{timestamp}{method.upper()}{request_path}{body}"
    return hmac.new(
        BITGET_APISECRET.encode("utf-8"),
        prehash_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

def fetch_total_profit(position):
    return position["total_asset"] - position["initial_asset"]

def format_currency(amount, include_sign=True):
    sign = "+" if amount >= 0 else "-"
    formatted = f"${abs(amount):,.2f}"
    return f"{sign}{formatted}" if include_sign else formatted

def fetch_openai_analysis():
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a crypto trading analyst."},
            {"role": "user", "content": "비트코인 향후 12시간 예측, 호재/악재 분류, 골든 크로스, 온체인 지표 포함해서 전체 분석해줘. 초보자도 이해 가능하게, 확률 포함"}
        ]
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
    return response.json()["choices"][0]["message"]["content"]
