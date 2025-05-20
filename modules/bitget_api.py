import os
import time
import requests
import base64
import hmac
import json
from modules.constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

def bitget_signature(timestamp, method, path, body):
    prehash = f"{timestamp}{method}{path}{body}"
    sign = hmac.new(BITGET_APISECRET.encode(), prehash.encode(), digestmod='sha256').digest()
    return base64.b64encode(sign).decode()

def get_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    sign = bitget_signature(timestamp, method, path, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_usdt_futures_account():
    path = "/api/v2/mix/account/accounts"
    url = f"https://api.bitget.com{path}?productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        # Error Handling
        if "code" in data and str(data["code"]) != "00000":
            return {"error": data.get("msg", "Bitget API 오류"), "code": data["code"]}
        if "data" in data and isinstance(data["data"], dict):
            return data["data"]
        else:
            return {"error": "계좌 정보 없음"}
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 오류: {e}"}
    except Exception as e:
        return {"error": f"기타 오류: {e}"}

def get_positions(symbol="BTCUSDT"):
    path = "/api/v2/mix/position/single-position"
    url = f"https://api.bitget.com{path}?symbol={symbol}&productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        # Error Handling
        if "code" in data and str(data["code"]) != "00000":
            return {"error": data.get("msg", "Bitget API 오류"), "code": data["code"]}
        if "data" in data and data["data"]:
            return data["data"]
        else:
            return {"error": "포지션 정보 없음"}
    except requests.exceptions.RequestException as e:
        return {"error": f"네트워크 오류: {e}"}
    except Exception as e:
        return {"error": f"기타 오류: {e}"}

def get_profit_summary():
    # 예시: 포지션 하나만 표기
    position = get_positions()
    if "error" in position:
        return {"error": position["error"]}
    try:
        p = position if isinstance(position, dict) else position[0]
        # 아래는 반드시 실제 API 리턴값에 맞게 매핑 필요 (샘플)
        return {
            "종목": p.get("symbol", "BTCUSDT"),
            "방향": "Long" if p.get("holdSide") == "long" else "Short",
            "진입가": p.get("openPrice"),
            "현재가": p.get("marketPrice"),
            "레버리지": p.get("leverage"),
            "청산가": p.get("liquidationPrice"),
            "청산까지 남은 거리": p.get("margin"),
            "미실현 손익": p.get("unrealizedPL"),
            "실현 손익": p.get("realizedPL"),
            "진입 자산": p.get("margin"),
            "수익률": p.get("achievedProfits"),
        }
    except Exception as e:
        return {"error": f"포지션 데이터 파싱 오류: {e}"}
