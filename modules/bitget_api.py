import requests
import os
import hmac
import hashlib
import time
import base64

API_URL = "https://api.bitget.com"

def _headers(api_key, api_secret, passphrase, method, path, body=''):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path + body
    sign = base64.b64encode(hmac.new(api_secret.encode(), message.encode(), hashlib.sha256).digest()).decode()
    return {
        'ACCESS-KEY': api_key,
        'ACCESS-SIGN': sign,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json'
    }

def fetch_wallet_balance():
    path = '/api/v2/account/assets'
    headers = _headers(
        os.getenv("BITGET_APIKEY"),
        os.getenv("BITGET_APISECRET"),
        os.getenv("BITGET_PASSPHRASE"),
        'GET', path
    )
    response = requests.get(API_URL + path, headers=headers).json()
    for item in response['data']:
        if item['coin'] == 'USDT':
            return float(item['available']), float(item['equity'])
    return 0.0, 0.0

def fetch_position():
    path = '/api/v2/position/futures/USDT'
    headers = _headers(
        os.getenv("BITGET_APIKEY"),
        os.getenv("BITGET_APISECRET"),
        os.getenv("BITGET_PASSPHRASE"),
        'GET', path
    )
    response = requests.get(API_URL + path, headers=headers).json()
    positions = []
    for p in response['data']:
        if float(p['total']) != 0:
            positions.append({
                'symbol': p['symbol'],
                'entry_price': float(p['entryPrice']),
                'market_price': float(p['markPrice']),
                'pnl': float(p['unrealizedPL'])
            })
    return positions
