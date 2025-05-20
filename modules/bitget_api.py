import os
import time
import requests
import base64
import hmac

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

def robust_request(url, headers, max_retry=3):
    for attempt in range(max_retry):
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 429:
                print("Bitget API Rate Limit, Retrying...")
                time.sleep(2)
                continue
            data = resp.json()
            # Bitget 고유 에러 메시지 감지
            if "code" in data and data["code"] not in ("00000", 0):
                print(f"Bitget API 오류: {data.get('msg', data.get('code', 'Unknown error'))}")
                return {"error": data.get("msg", data.get("code", "Unknown error")), "data": None}
            return {"error": None, "data": data.get("data", None)}
        except requests.exceptions.RequestException as e:
            print(f"네트워크 에러: {e}, 재시도 {attempt+1}")
            time.sleep(2)
        except Exception as e:
            print(f"응답 파싱 에러: {e}, 재시도 {attempt+1}")
            time.sleep(1)
    # 모두 실패 시
    return {"error": "네트워크/Bitget API 응답 없음", "data": None}

def get_usdt_futures_account():
    path = "/api/v2/mix/account/accounts"
    url = f"https://api.bitget.com{path}?productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    result = robust_request(url, headers)
    if result["error"]:
        return {"error": result["error"], "data": None}
    return {"error": None, "data": result["data"]}

def get_positions(symbol="BTCUSDT"):
    path = "/api/v2/mix/position/single-position"
    url = f"https://api.bitget.com{path}?symbol={symbol}&productType=USDT-FUTURES"
    headers = get_headers("GET", path, "")
    result = robust_request(url, headers)
    if result["error"]:
        return {"error": result["error"], "data": None}
    return {"error": None, "data": result["data"]}

def get_profit_summary(symbol="BTCUSDT"):
    acc = get_usdt_futures_account()
    if acc["error"]:
        return {"error": f"계좌 조회 오류: {acc['error']}"}
    asset = 0
    if acc["data"] and isinstance(acc["data"], dict):
        asset = float(acc["data"].get("marginBalance", 0))
    pos = get_positions(symbol)
    if pos["error"]:
        return {"error": f"포지션 조회 오류: {pos['error']}"}
    pos_data = pos["data"] or {}
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
            "error": None
        }
    except Exception as e:
        return {"error": f"Bitget 데이터 파싱 오류: {e}"}
