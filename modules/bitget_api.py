import os
import time
import requests
import base64
import hmac
import json

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

def bitget_signature(timestamp, method, path, body):
    prehash = f"{timestamp}{method}{path}{body}"
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), digestmod='sha256').digest()
    return base64.b64encode(sign).decode()

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = bitget_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_profit_summary(symbol="BTCUSDT"):
    # 1. 계좌 정보
    account_path = "/api/v2/mix/account/accounts"
    account_url = f"https://api.bitget.com{account_path}?productType=USDT-FUTURES"
    account_headers = get_headers("GET", account_path, "")
    acc_resp = requests.get(account_url, headers=account_headers)
    acc_json = acc_resp.json()
    asset = 0
    if "data" in acc_json and isinstance(acc_json["data"], dict):
        asset = float(acc_json["data"].get("marginBalance", 0))

    # 2. 포지션 정보
    pos_path = "/api/v2/mix/position/single-position"
    pos_url = f"https://api.bitget.com{pos_path}?symbol={symbol}&productType=USDT-FUTURES"
    pos_headers = get_headers("GET", pos_path, "")
    pos_resp = requests.get(pos_url, headers=pos_headers)
    pos_json = pos_resp.json()
    pos_data = pos_json.get("data", {})
    try:
        return {
            "종목": symbol,
            "방향": pos_data.get("holdSide", "-"),
            "진입가": pos_data.get("openAvgPrice", "-"),
            "현재가": pos_data.get("last", "-"),
            "레버리지": pos_data.get("leverage", "-"),
            "청산가": pos_data.get("liquidationPrice", "-"),
            "청산까지 남은 거리": f"{float(pos_data.get('liquidationPrice', 0)) - float(pos_data.get('last', 0)):.2f}" if pos_data.get('liquidationPrice') and pos_data.get('last') else "-",
            "미실현 손익": pos_data.get("unrealizedPL", "-"),
            "실현 손익": pos_data.get("realizedPL", "-"),
            "진입 자산": asset,
            "수익률": f"{(float(pos_data.get('unrealizedPL', 0)) / asset * 100):.2f}%" if asset else "-",
        }
    except Exception:
        return None
