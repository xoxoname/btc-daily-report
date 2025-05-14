from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt
import requests
import os

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")

exch = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "password": API_PASSPHRASE,
    "enableRateLimit": True,
    "options": {"defaultType": "swap"},
})

app = Flask(__name__)
latest_report = {}

def fetch_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(res.json()["data"]["amount"])
    except:
        return None

def fetch_data():
    global latest_report
    try:
        balance = exch.fetch_balance({"type": "swap"})
        equity = balance['total'].get('USDT', 0)

        positions = exch.fetch_positions()
        open_positions = [pos for pos in positions if pos['contracts'] > 0]
        total_unrealized = sum(float(pos.get('unrealizedPnl', 0)) for pos in open_positions)

        now = datetime.utcnow() + timedelta(hours=9)
        today_start = datetime(now.year, now.month, now.day)
        since = int(today_start.timestamp() * 1000)

        # 실현 PnL은 실제 체결 로그가 없을 경우 정확히 알 수 없음 → 추후 수정 가능
        realized = 0.0

        coinbase_price = fetch_coinbase_price()
        pos_info = []
        for pos in open_positions:
            market = pos['symbol']
            direction = pos['side']
            qty = pos['contracts']
            entry = pos['entryPrice']
            now_price = coinbase_price if coinbase_price else entry
            pct = ((now_price - entry) / entry) * 100 if direction == 'long' else ((entry - now_price) / entry) * 100
            pos_info.append({
                "market": market,
                "direction": direction,
                "quantity": qty,
                "entry_price": entry,
                "current_price": now_price,
                "diff_pct": round(pct, 2)
            })

        latest_report = {
            "timestamp": now.isoformat(),
            "equity": round(equity, 4),
            "realized": round(realized, 4),
            "unrealized": round(total_unrealized, 4),
            "coinbase_price": coinbase_price,
            "positions": pos_info
        }
    except Exception as e:
        latest_report = {"error": str(e)}

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(fetch_data, 'interval', minutes=5)
scheduler.start()
fetch_data()

@app.route("/report", methods=["GET"])
def report():
    return jsonify(latest_report)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
