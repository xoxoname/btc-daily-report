import os
import time
import ccxt
import pytz
import json
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("BITGET_API_KEY")
secret = os.getenv("BITGET_API_SECRET")
password = os.getenv("BITGET_API_PASSWORD")

exch = ccxt.bitget({
    "apiKey": api_key,
    "secret": secret,
    "password": password,
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap"
    }
})

latest_report = {}

def fetch_data():
    global latest_report
    now = datetime.now(pytz.timezone("Asia/Seoul"))
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        balance = exch.fetch_balance({"type": "swap"})
        equity = balance["total"]["USDT"]
    except Exception:
        equity = None

    try:
        positions = exch.fetch_positions()
        position_details = []
        total_unrealized = 0.0
        for pos in positions:
            if pos['symbol'] == "BTC/USDT:USDT" and float(pos['contracts']) > 0:
                side = pos['side']
                entry = float(pos['entryPrice'])
                amount = float(pos['contracts'])
                mark_price = float(pos['markPrice'])
                unrealized = float(pos.get('unrealizedPnl', 0.0))
                total_unrealized += unrealized

                position_details.append(f"📊 {pos['symbol']} | {side} | 수량: {amount:.4f} | 진입가: {entry} | 미실현 PNL: {unrealized:.4f} USDT")

    except Exception:
        position_details = ["❌ 포지션 조회 실패"]
        total_unrealized = None

    try:
        since = exch.parse8601(datetime.now().strftime("%Y-%m-%dT00:00:00Z"))
        history = exch.fetch_account_trades(symbol="BTC/USDT:USDT", since=since)
        realized = sum(float(t.get('realizedPnl', 0)) for t in history if 'realizedPnl' in t)
    except Exception:
        realized = None

    latest_report = {
        "timestamp": now_str,
        "equity": equity,
        "realized_pnl": realized,
        "unrealized_pnl": total_unrealized,
        "positions": position_details
    }

def generate_report():
    fetch_data()
    print(f"[BTC 실시간 리포트] {latest_report['timestamp']}")
    print(f"💎 총 자산(Equity): {latest_report['equity']} USDT")
    print(f"📊 오늘 실현 PnL: {latest_report['realized_pnl']} USDT")
    print(f"📊 오늘 미실현 PnL: {latest_report['unrealized_pnl']} USDT")
    for p in latest_report['positions']:
        print(p)
    print("----------------------------------------")

# Flask 앱 및 웹 서비스 정의
app = Flask(__name__)

@app.route("/")
def home():
    return "BTC 리포트 서비스 실행 중"

@app.route("/report")
def report():
    fetch_data()
    return jsonify(latest_report)

# APScheduler로 자동 실행 등록
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(generate_report, "interval", minutes=5)  # 5분 간격 실행
scheduler.add_job(generate_report, "cron", hour=0, minute=30)   # KST 09:30
scheduler.add_job(generate_report, "cron", hour=4, minute=0)    # KST 13:00
scheduler.add_job(generate_report, "cron", hour=14, minute=0)   # KST 23:00
scheduler.start()

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
