import requests
import time
import hmac
import hashlib
import json
from modules.constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

def get_bitget_headers(method, path, query=''):
    timestamp = str(int(time.time() * 1000))
    pre_hash = timestamp + method + path + query
    sign = hmac.new(BITGET_APISECRET.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()
    return {
        'ACCESS-KEY': BITGET_APIKEY,
        'ACCESS-SIGN': sign,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': BITGET_PASSPHRASE,
        'Content-Type': 'application/json'
    }

def get_positions(symbol='BTCUSDT'):
    method = 'GET'
    path = '/api/mix/v1/position/singlePosition'
    query = f'?symbol={symbol}&marginCoin=USDT'
    url = 'https://api.bitget.com' + path + query
    headers = get_bitget_headers(method, path, query)
    res = requests.get(url, headers=headers)
    data = res.json()
    if data.get("code") != "00000":
        return None
    return data["data"]

def get_account():
    method = 'GET'
    path = '/api/mix/v1/account/account'
    query = '?symbol=BTCUSDT&marginCoin=USDT'
    url = 'https://api.bitget.com' + path + query
    headers = get_bitget_headers(method, path, query)
    res = requests.get(url, headers=headers)
    data = res.json()
    if data.get("code") != "00000":
        return None
    return data["data"]

def get_profit_summary():
    pos = get_positions()
    acc = get_account()
    if not pos or not acc:
        return None

    entry_price = float(pos['openPrice'])
    mark_price = float(pos['marketPrice'])
    size = float(pos['holdVol'])
    direction = pos['holdSide']
    leverage = float(pos['leverage'])
    liq_price = float(pos['liquidationPrice'])
    pnl = float(pos['unrealizedPL'])
    realized = float(acc.get('realizedPL', 0))
    margin = float(pos['margin'])
    margin_coin = 'USDT'

    pnl_ratio = (pnl + realized) / margin * 100 if margin else 0

    return {
        "종목": pos['symbol'],
        "방향": direction,
        "진입가": f"${entry_price:,.2f}",
        "현재가": f"${mark_price:,.2f}",
        "레버리지": f"{leverage}x",
        "청산가": f"${liq_price:,.2f}",
        "미실현 손익": f"{pnl:,.2f} {margin_coin}",
        "실현 손익": f"{realized:,.2f} {margin_coin}",
        "진입 자산": f"{margin:,.2f} {margin_coin}",
        "수익률": f"{pnl_ratio:.2f}%",
        "청산까지 남은 거리": f"{((mark_price-liq_price)/mark_price*100):.2f}%"
    }
