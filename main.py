import os
import ccxt
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_API_SECRET = os.getenv("BITGET_API_SECRET")
BITGET_API_PASSWORD = os.getenv("BITGET_API_PASSWORD")

app = Flask(__name__)
cached_report = {}

def fetch_report():
    global cached_report
    try:
        exchange = ccxt.bitget({
            'apiKey': BITGET_API_KEY,
            'secret': BITGET_API_SECRET,
            'password': BITGET_API_PASSWORD,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })

        balance = exchange.fetch_balance({'type': 'swap'})
        equity = balance['total'].get('USDT', 0)

        positions = exchange.fetch_positions()
        total_unrealized = 0
        position_list = []

        for pos in positions:
            if pos['contracts'] == 0:
                continue
            unrealized = pos.get('unrealizedPnl', 0)
            total_unrealized += unrealized
            position_list.append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'entryPrice': pos['entryPrice'],
                'unrealizedPnl': unrealized,
                'contracts': pos['contracts']
            })

        cached_report = {
            "equity": equity,
            "pnl_today_realized": 0,
            "pnl_today_unrealized": total_unrealized,
            "pnl_cumulative": 0,
            "positions": position_list
        }
    except Exception as e:
        cached_report = {"error": str(e)}

@app.route("/report")
def get_report():
    return jsonify(cached_report)

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_report, 'interval', minutes=5)
    scheduler.start()

    # 최초 실행 시 리포트 수집
    fetch_report()

    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
