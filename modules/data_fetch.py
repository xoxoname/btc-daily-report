# modules/data_fetch.py

import requests

def fetch_btc_price():
    url = "https://api.bitget.com/api/v2/spot/market/ticker?symbol=BTCUSDT"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            return {
                "price": float(data["data"]["close"]),
                "high_24h": float(data["data"]["high24h"]),
                "low_24h": float(data["data"]["low24h"]),
                "change_percent": float(data["data"]["changeUtc"])  # 또는 "change24hRate" 사용 가능
            }
        else:
            return {"status": "error", "message": f"API response error: {data.get('msg', 'Unknown')}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
