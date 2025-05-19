import os
import requests
import time
import hmac
import hashlib
import base64

BITGET_APIKEY = os.environ.get('BITGET_APIKEY')
BITGET_APISECRET = os.environ.get('BITGET_APISECRET')
BITGET_PASSPHRASE = os.environ.get('BITGET_PASSPHRASE')

BASE_URL = "https://api.bitget.com"

def _timestamp():
    return str(int(time.time() * 1000))

def _sign(message, secret):
    return base64.b64encode(
        hmac.new(secret.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256).digest()
    ).decode('utf-8')

def _headers(path, method, body=""):
    timestamp = _timestamp()
    prehash = timestamp + method + path + body
    sign = _sign(prehash, BITGET_APISECRET)
    return {
        'ACCESS-KEY': BITGET_APIKEY,
        'ACCESS-SIGN': sign,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': BITGET_PASSPHRASE,
        'Content-Type': 'application/json',
        'locale': 'en-US'
    }

def get_positions():
    # BTCUSDT 포지션만 조회 (선물)
    url = f"{BASE_URL}/api/v2/mix/position/singlePosition"
    params = {
        "symbol": "BTCUSDT",
        "marginCoin": "USDT"
    }
    path = f"/api/v2/mix/position/singlePosition?symbol=BTCUSDT&marginCoin=USDT"
    headers = _headers(path, "GET")
    r = requests.get(url, params=params, headers=headers)
    try:
        data = r.json()
        pos = data['data']
        if not pos or float(pos.get('total',0)) == 0:
            return None
        # 리턴값 표준화
        return {
            "symbol": pos['symbol'],
            "side": "롱" if pos['holdSide']=='long' else "숏",
            "openPrice": float(pos['openPrice']),
            "currentPrice": float(pos['lastPrice']),
            "leverage": int(pos['leverage']),
            "liquidationPrice": float(pos['liqPrice']),
            "unrealizedPnl": float(pos['unrealizedPL']),
            "margin": float(pos['margin'])
        }
    except Exception as e:
        print(f"Bitget API Error (positions): {e}")
        return None

def get_profit_history():
    # 금일 실현손익 등 조회 (예시: 거래내역 최근 24시간 기준)
    url = f"{BASE_URL}/api/v2/mix/order/history"
    params = {
        "symbol": "BTCUSDT",
        "marginCoin": "USDT",
        "startTime": int((time.time() - 86400) * 1000),
        "endTime": int(time.time() * 1000),
        "pageSize": 100,
        "lastEndId": ""
    }
    path = f"/api/v2/mix/order/history?symbol=BTCUSDT&marginCoin=USDT&startTime={params['startTime']}&endTime={params['endTime']}&pageSize=100&lastEndId="
    headers = _headers(path, "GET")
    r = requests.get(url, params=params, headers=headers)
    realized = 0
    try:
        data = r.json()
        if 'data' in data and 'orderList' in data['data']:
            for order in data['data']['orderList']:
                if 'realizedPL' in order:
                    realized += float(order['realizedPL'])
        return {
            "realizedPnl": realized,
            "todayPnl": realized
        }
    except Exception as e:
        print(f"Bitget API Error (profit): {e}")
        return {"realizedPnl": 0, "todayPnl": 0}
