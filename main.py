import os
import ccxt
import time
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

cached_report = {}

def create_exchange():
    try:
        return ccxt.bitget({
            'apiKey': os.environ['BITGET_API_KEY'],
            'secret': os.environ['BITGET_SECRET'],
            'password': os.environ['BITGET_PASSPHRASE'],
            'enableRateLimit': True,
        })
    except KeyError as e:
        return {"error": f"환경변수 누락: {e}"}

def fetch_data():
    exch = create_exchange()
    if isinstance(exch, dict) and "error" in exch:
        return exch

    try:
        balance = exch.fetch_balance({'type': 'swap'})
        equity = float(balance['total'].get('USDT', 0))
    except Exception as e:
        return {"error": f"잔고 조회 실패: {str(e)}"}

    try:
        positions = exch.fetch_positions()
        filtered_positions = [
            {
                "symbol": p["symbol"],
                "side": p["side"],
                "entryPrice": float(p["entryPrice"]),
                "contracts": float(p["contracts"]),
                "unrealizedPnl": float(p["unrealizedPnl"]),
            }
            for p in positions if float(p["contracts"]) > 0
        ]
    except Exception as e:
        return {"error": f"포지션 조회 실패: {str(e)}"}

    total_unrealized = sum([p["unrealizedPnl"] for p in filtered_positions])

    result = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "equity": equity,
        "totalUnrealizedPnl": total_unrealized,
        "positions": filtered_positions,
    }

    try:
        total_investment = float(os.getenv('BASE_CAPITAL', '1000'))
        if total_investment > 0:
            result["returnRate"] = round((equity - total_investment) / total_investment * 100, 2)
        else:
            result["returnRate"] = None
    except:
        result["returnRate"] = None

    return result

@app.route("/report")
def report():
    global cached_report
    return jsonify(cached_report or fetch_data())

def update_report():
    global cached_report
    cached_report = fetch_data()
    print("🔁 최신 리포트 갱신 중...")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_report, 'interval', minutes=5)
    scheduler.start()
    update_report()
    app.run(host='0.0.0.0', port=10000)
