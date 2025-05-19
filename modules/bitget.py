import os
import time
import requests
import hmac
import hashlib
import base64

BASE_URL = "https://api.bitget.com/api/v2/mix"

API_KEY = os.environ.get("BITGET_APIKEY")
API_SECRET = os.environ.get("BITGET_APISECRET")
PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

def _headers(method, path):
    timestamp = str(int(time.time() * 1000))
    prehash = f"{timestamp}{method.upper()}{path}"
    sign = hmac.new(API_SECRET.encode(), prehash.encode(), hashlib.sha256).digest()
    sign_b64 = base64.b64encode(sign).decode()
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign_b64,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_positions():
    # BTCUSDT 포지션 조회
    path = "/position/singlePosition"
    url = f"{BASE_URL}{path}?symbol=BTCUSDT&marginCoin=USDT"
    try:
        r = requests.get(url, headers=_headers("GET", path))
        data = r.json()
        if data.get("code") == "00000" and data.get("data"):
            pos = data["data"]
            return {
                "symbol": pos.get("symbol", "BTCUSDT"),
                "side": pos.get("holdSide", "-").capitalize(),
                "openPrice": float(pos.get("openPrice", 0)),
                "currentPrice": float(pos.get("latestPrice", 0)),
                "leverage": float(pos.get("leverage", 0)),
                "liquidationPrice": float(pos.get("liquidationPrice", 0)),
                "positionAmt": float(pos.get("total", 0)),
                "unrealizedPnl": float(pos.get("unrealizedPL", 0)),
                "margin": float(pos.get("margin", 0)),
            }
        return None
    except Exception as e:
        return None

def get_profit_history():
    # 실현 손익은 예시! 실제로는 비트겟 Closed PnL API 필요
    # 없으면 임시로 0 출력
    return {
        "realizedPnl": 0.0,
        "todayPnl": 0.0,  # 금일 총 수익
        "entryValue": 0.0,  # 진입 자산
    }
