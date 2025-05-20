# modules/bitget_api.py
import os
import time
import hmac
import hashlib
import base64
import requests
import json

API_KEY = os.getenv("BITGET_APIKEY")
API_SECRET = os.getenv("BITGET_APISECRET")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

def generate_signature(timestamp, method, request_path, query_string, body):
    # Bitget 신호 생성 공식
    if query_string:
        request_path += '?' + query_string
    message = f'{timestamp}{method.upper()}{request_path}{body}'
    mac = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode('utf-8')

def bitget_request(method, endpoint, params=None, data=None, max_retries=4):
    url = BASE_URL + endpoint
    for attempt in range(1, max_retries+1):
        try:
            timestamp = str(int(time.time() * 1000))
            query_string = ''
            if params:
                query_string = '&'.join([f'{key}={params[key]}' for key in sorted(params)])
            body = json.dumps(data) if data else ''
            signature = generate_signature(timestamp, method, endpoint, query_string, body)
            headers = {
                "ACCESS-KEY": API_KEY,
                "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": timestamp,
                "ACCESS-PASSPHRASE": API_PASSPHRASE,
                "Content-Type": "application/json"
            }
            req_url = url
            if method.upper() == "GET" and params:
                req_url += '?' + query_string
            if method.upper() == "GET":
                resp = requests.get(req_url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                resp = requests.post(req_url, headers=headers, data=body, timeout=10)
            else:
                raise ValueError("Unsupported HTTP method")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("code") == "00000":
                        return data
                    else:
                        print(f"[Bitget API Error] Code: {data.get('code')}, Msg: {data.get('msg')}")
                        # 권한, rate limit 등도 msg로 반환됨
                        if "frequency" in str(data.get("msg", "")).lower() or "limit" in str(data.get("msg", "")).lower():
                            time.sleep(2 ** attempt)
                            continue
                        break
                except Exception as e:
                    print(f"[Bitget API] JSON Parse Error: {e}")
                    break
            elif resp.status_code in (429, 500):
                print(f"[Bitget API] {resp.status_code} Too Many Requests/Server Error. Retrying ({attempt})...")
                time.sleep(2 ** attempt)
                continue
            elif resp.status_code == 403:
                print(f"[Bitget API] 403 Forbidden - Check API key permission or IP whitelist")
                break
            elif resp.status_code == 401:
                print(f"[Bitget API] 401 Unauthorized - Check API key, secret, passphrase")
                break
            else:
                print(f"[Bitget API] Unexpected status {resp.status_code}: {resp.text}")
                break
        except requests.exceptions.RequestException as e:
            print(f"[Bitget API] Network error: {e} (retry {attempt})")
            time.sleep(2 ** attempt)
    return None

def get_account():
    # USDT-Futures 전체 계좌 잔고
    endpoint = "/api/v2/mix/account/accounts"
    params = {"productType": "USDT-FUTURES"}
    result = bitget_request("GET", endpoint, params)
    if result and result.get("data"):
        return result["data"]
    return None

def get_position(symbol="BTCUSDT"):
    # 특정 심볼 포지션 조회
    endpoint = "/api/v2/mix/position/single-position"
    params = {"symbol": symbol, "productType": "USDT-FUTURES"}
    result = bitget_request("GET", endpoint, params)
    if result and result.get("data"):
        return result["data"]
    return None

def get_profit_summary(symbol="BTCUSDT"):
    account = get_account()
    pos = get_position(symbol)
    if not account or not pos:
        return None
    try:
        # 포지션 정보 예시 (1건만 있다고 가정)
        p = pos
        return {
            "종목": symbol,
            "방향": "Long" if float(p["holdSide"].upper() == "LONG") else "Short",
            "진입가": p.get("openAvgPrice", "-"),
            "현재가": p.get("marketPrice", "-"),
            "레버리지": p.get("leverage", "-"),
            "청산가": p.get("liquidationPrice", "-"),
            "청산까지 남은 거리": f'{float(p.get("marketPrice",0))-float(p.get("liquidationPrice",0)):.2f}',
            "미실현 손익": p.get("unrealizedPL", "-"),
            "실현 손익": p.get("realizedPL", "-"),
            "진입 자산": account.get("usdtEquity", "-"),
            "수익률": f"{float(p.get('unrealizedPL',0))/float(account.get('usdtEquity',1))*100:.2f}%"
        }
    except Exception as e:
        print(f"[Bitget API] Data parse error: {e}")
        return None
