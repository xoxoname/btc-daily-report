import os
import time
import requests
import hmac
import hashlib
import base64

BASE_URL = "https://api.bitget.com"
APIKEY = os.environ.get("BITGET_APIKEY")
APISECRET = os.environ.get("BITGET_APISECRET")
PASSPHRASE = os.environ.get("BITGET_PASSPHRASE")

def _headers(method, path, query=None, body=""):
    timestamp = str(int(time.time() * 1000))
    query_str = f"?{query}" if query else ""
    pre_sign = f"{timestamp}{method}{path}{query_str}{body}"
    sign = base64.b64encode(
        hmac.new(APISECRET.encode(), pre_sign.encode(), hashlib.sha256).digest()
    ).decode()
    return {
        "ACCESS-KEY": APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json",
    }

def get_btc_position():
    method = "GET"
    path = "/api/mix/v1/position/singlePosition"
    query = "symbol=BTCUSDT_UMCBL&marginCoin=USDT"
    url = BASE_URL + path + "?" + query
    try:
        headers = _headers(method, path, query)
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return {"error": f"Bitget API 오류: {resp.status_code} - {resp.text}"}
        data = resp.json()
        if data.get("code") != "00000":
            return {"error": f"Bitget 내부 오류: {data.get('msg', 'Unknown')}"}
        pos = data.get("data", {})
        # holdVol == 0 → 포지션 없음
        if float(pos.get("holdVol", 0)) == 0:
            return {}
        return {
            "symbol": pos.get("symbol"),
            "side": pos.get("holdSide"),
            "avg_open": float(pos.get("avgOpenPrice", 0)),
            "current_price": float(pos.get("marketPrice", 0)),
            "leverage": int(pos.get("leverage", 1)),
            "liquidation": float(pos.get("liquidationPrice", 0)),
            "upl": float(pos.get("unrealizedPL", 0)),
            "realized": float(pos.get("achievedProfits", 0)),
            "margin": float(pos.get("margin", 0)),
        }
    except Exception as e:
        return {"error": f"Bitget API 연동 오류: {e}"}

def get_btc_balance():
    # 실제 잔고/총 자산 등 불러오기 (추가 필요시 여기에)
    return 2000  # 데모 값. 실제 잔고 연동 필요시 Bitget Spot API 참조

def get_today_realized_profit():
    # TODO: Bitget의 손익 기록 API를 활용해서 오늘 실현 수익을 가져오게 수정 (데모)
    return 340.0  # 데모 값. 실제로는 Bitget 트랜잭션을 일자별로 집계
