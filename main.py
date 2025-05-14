import os
import requests
import time
import hmac
import hashlib
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")  # 필요 없다면 비워도 무방

BASE_URL = "https://api.bitget.com"

def get_timestamp():
    return str(int(time.time() * 1000))

def sign(params: str, secret_key: str):
    return hmac.new(secret_key.encode(), params.encode(), hashlib.sha256).hexdigest()

def fetch_pnl():
    now = datetime.now(timezone("Asia/Seoul"))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now

    start_ts = int(start.timestamp() * 1000)
    end_ts = int(end.timestamp() * 1000)

    timestamp = get_timestamp()
    path = "/api/mix/v1/account/accountBill"
    query = f"productType=USDT-FUTURES&startTime={start_ts}&endTime={end_ts}&pageSize=50"

    message = timestamp + "GET" + path + "?" + query
    signature = sign(message, SECRET_KEY)

    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(f"{BASE_URL}{path}?{query}", headers=headers)
        data = response.json()

        total_pnl = 0.0
        for
