import requests
import time
import hmac
import hashlib
from modules.constants import BITGET_APIKEY, BITGET_APISECRET, BITGET_PASSPHRASE

BASE_URL = "https://api.bitget.com"

def _get_timestamp():
    return str(int(time.time() * 1000))

def _sign(method, path, timestamp, query_string="", body=""):
    pre_hash = f"{timestamp}{method}{path}{query_string}{body}"
    return hmac.new(BITGET_APISECRET.encode(), pre_hash.encode(), hashlib.sha256).hexdigest()

def _headers(method, path, query_string="", body=""):
    timestamp = _get_timestamp()
    signature = _sign(method, path, timestamp, query_string, body)
    return {
        "ACCESS-KEY": BITGET_APIKEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_bitget_positions():
    path = "/api/mix/v1/position/allPosition?productType=umcbl"
    url = BASE_URL + path
    headers = _headers("GET", path)
    res = requests.get(url, headers=headers)
    return res.json()

def get_bitget_account():
    path = "/api/mix/v1/account/account?productType=umcbl"
    url = BASE_URL + path
    headers = _headers("GET", path)
    res = requests.get(url, headers=headers)
    return res.json()

def get_bitget_data():
    pos_data = get_bitget_positions()
    acc_data = get_bitget_account()

    total_realized = 0
    total_unrealized = 0
    margin = 0
    assets = []

    if pos_data.get("code") == "00000":
        for p in pos_data["data"]:
            if p["marginMode"] == "crossed" and p["margin"] != "0":
                upnl = float(p["unrealizedPL"])
                rpnl = float(p["realizedPL"])
                total_unrealized += upnl
                total_realized += rpnl
                margin += float(p["margin"])

    if acc_data.get("code") == "00000":
        assets = acc_data["data"]

    return {
        "realized": total_realized,
        "unrealized": total_unrealized,
        "margin": margin,
        "assets": assets
    }
