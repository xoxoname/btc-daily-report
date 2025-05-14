import os
import time
import ccxt
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
latest_report = {}

exchange = ccxt.bitget({
    'apiKey': os.getenv("BITGET_API_KEY"),
    'secret': os.getenv("BITGET_API_SECRET"),
    'password': os.getenv("BITGET_API_PASSWORD"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
    }
})

def get_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USDT/spot").json()
        return float(res["data"]["amount"])
    except:
        return None

def fetch_equity():
    try:
        balance = exchange.fetch_balance(params={"type": "swap"})
        usdt = balance['total'].get("USDT", 0)
        return round(usdt, 4)
    except Exception as e:
        print("❌ Equity fetch error:", e)
        return 0

def fetch_positions():
    try:
        positions = exchange.fetch_positions()
        open_positions = []
        for pos in positions:
            if float(pos.get("contracts", 0)) > 0:
                open_positions.append(pos)
        return open_positions
    except Exception as e:
        print("❌ Position fetch error:", e)
        return []

def generate_report():
    global latest_report
    equity = fetch_equity()
    price = get_coinbase_price()
    positions = fetch_positions()

    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    report_lines = [f"[BTC 실시간 리포트] {now}", "----------------------------------------"]
    report_lines.append(f"💎 총 자산(Equity): {equity:.4f} USDT")

    total_unrealized = 0
    for pos in positions:
        side = pos["side"]
        symbol = pos["symbol"]
        entry = float(pos["entryPrice"])
        amount = float(pos["contracts"])
        mark_price = price
        unreal = (mark_price - entry) * amount * (1 if side == "long" else -1)
        total_unrealized += unreal
        diff_pct = (mark_price - entry) / entry * 100
        report_lines.append(
            f"📊 {symbol} | {side} | 수량: {amount} | 진입가: {entry} | 현재가: {mark_price:.2f} | 수익률: {diff_pct:+.2f}%"
        )

    report_lines.append(f"🧮 총 미실현 PNL: {total_unrealized:+.4f} USDT")
    report_lines.append("----------------------------------------")

    latest_report = {
        "timestamp": now,
        "equity": equity,
        "coinbase_price": price,
        "unrealized_pnl": round(total_unrealized, 4),
        "positions": positions,
        "report_text": "\n".join(report_lines)
    }

    print(latest_report["report_text"])

@app.route("/report", methods=["GET"])
def get_report():
    return jsonify(latest_report)

if __name__ == "__main__":
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(generate_report, 'interval', minutes=5)
    scheduler.start()
    generate_report()
    app.run(host="0.0.0.0", port=10000)

