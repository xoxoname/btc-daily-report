import os
import time
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import ccxt

load_dotenv()

app = Flask(__name__)
latest_report = {}

def create_exchange():
    return ccxt.bitget({
        'apiKey': os.getenv("BITGET_API_KEY"),
        'secret': os.getenv("BITGET_API_SECRET"),
        'password': os.getenv("BITGET_API_PASSWORD"),
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'},
    })

def fetch_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USDT/spot").json()
        return float(res["data"]["amount"])
    except Exception as e:
        print("Coinbase 가격 조회 실패:", e)
        return None

def fetch_data():
    exch = create_exchange()
    price = fetch_coinbase_price()
    if price is None:
        price = 0

    try:
        balance = exch.fetch_balance({'type': 'swap'})
        equity = float(balance['total'].get('USDT', 0))
    except Exception as e:
        print("잔고 조회 실패:", e)
        equity = 0

    try:
        positions = exch.fetch_positions()
    except Exception as e:
        print("포지션 조회 실패:", e)
        positions = []

    open_positions = []
    unrealized_pnl_total = 0
    realized_pnl_total = 0  # Bitget 실현 손익 API로 따로 불러와야 정확하지만 지금은 0 고정

    for pos in positions:
        if pos.get("contracts", 0) > 0:
            side = pos['side']
            entry = float(pos['entryPrice'])
            amt = float(pos['contracts'])
            unreal = float(pos.get('unrealizedPnl', 0))
            symbol = pos['symbol']
            change_pct = round(((price - entry) / entry) * 100, 2) if entry else 0

            open_positions.append({
                'symbol': symbol,
                'side': side,
                'amount': amt,
                'entry': entry,
                'change_pct': change_pct,
                'unrealized': unreal
            })

            unrealized_pnl_total += unreal

    return {
        'equity': round(equity, 4),
        'coinbase_price': round(price, 2),
        'realized_pnl': round(realized_pnl_total, 4),
        'unrealized_pnl': round(unrealized_pnl_total, 4),
        'pnl_rate': round(((realized_pnl_total + unrealized_pnl_total) / equity) * 100, 2) if equity else 0,
        'positions': open_positions,
    }

def update_report():
    global latest_report
    print("🔁 최신 리포트 갱신 중...")
    latest_report = fetch_data()

@app.route("/report")
def report():
    return jsonify(latest_report)

if __name__ == "__main__":
    update_report()

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(update_report, 'interval', minutes=5)
    scheduler.start()

    app.run(host="0.0.0.0", port=10000)
