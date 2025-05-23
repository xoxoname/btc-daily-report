import requests
import time
import os

def get_timestamp():
    return str(int(time.time() * 1000))

async def fetch_profit_report():
    try:
        timestamp = get_timestamp()
        headers = {
            "ACCESS-KEY": os.getenv("BITGET_APIKEY"),
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-SIGN": "dummy_signature",
        }
        res = requests.get("https://api.bitget.com/api/mix/v1/account/accounts?productType=USDT-FUTURES", headers=headers)
        return f"📡 Bitget API 응답 원문: {res.text}"
    except Exception as e:
        return f"❗ Bitget API 호출 중 오류 발생: {e}"
