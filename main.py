import os
import time
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from ccxt import bitget
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSWORD = os.getenv("BITGET_API_PASSWORD")

exch = bitget({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': API_PASSWORD,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
    }
})

latest_report = {}

def fetch_data():
    global latest_report
    try:
        balance = exch.fetch_balance({'type': 'swap'})
        equity = balance['total'].get('USDT', 0)
        positions = exch.fetch_positions()
        unrealized = sum(p.get('unrealizedPnl', 0) for p in positions if 'unrealizedPnl' in p)
        realized = sum(p.get('realizedPnl', 0) for p in positions if 'realizedPnl' in p)

        latest_report = {
            "equity": round(equity, 4),
            "realized_pnl": round(realized, 4),
            "unrealized_pnl": round(unrealized, 4),
            "timestamp": int(time.time())
        }
    except Exception as e:
        latest_report = {"error": str(e)}

# Start scheduler for 5-minute updates
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, 'interval', minutes=5)
scheduler.start()
fetch_data()  # Run immediately on startup

# Flask web server
app = Flask(__name__)

@app.route("/")
def root():
    return "BTC Daily Report Server is running."

@app.route("/report")
def report():
    return jsonify(latest_report)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
