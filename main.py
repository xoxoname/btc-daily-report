import os
import time
import requests
import ccxt
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
latest_report = {"message": "리포트 초기화 중..."}

def create_exchange():
    api_key = os.getenv("BITGET_API_KEY")
    secret = os.getenv("BITGET_SECRET")
    password = os.getenv("BITGET_PASSPHRASE")
    if not all([api_key, secret, password]):
        return None  # 인증 누락 처리
    return ccxt.bitget({
        'apiKey': api_key,
        'secret': secret,
        'password': password,
        'enableRateLimit': True,
    })

def get_coinbase_price():
    try:
        r = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(r.json()["data"]["amount"])
    except:
        return None

def fetch_data():
    exch = create_exchange()
    if not exch:
        return {"error": "Bitget API 키 누락됨 (환경변수 확인 필요)"}

    try:
        balance = exch.fetch_balance({'type': 'swap'})
        equity = float(balance['total']['USDT'])

        positions = exch.fetch_positions()
        open_positions = []
        unrealized_total = 0.0

        for pos in positions:
            if float(pos['contracts']) > 0:
                pnl = float(pos['unrealizedPnl'])
                unrealized_total += pnl
                open_positions.append({
                    "symbol": pos['symbol'],
                    "side": pos['side'],
                    "entry": pos['entryPrice'],
                    "amount": pos['contracts'],
                    "unrealized": round(pnl, 2)
                })

        # 수익률 계산
        spot_price = get_coinbase_price()
        change_pct = None
        if 'total' in balance and 'USDT' in balance['total']:
            initial_equity = float(os.getenv("INITIAL_EQUITY", "1000"))  # 없으면 1000 가정
            change_pct = round((equity - initial_equity) / initial_equity * 100, 2)

        report = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "equity": round(equity, 2),
            "change_pct": change_pct,
            "coinbase_price": spot_price,
            "open_positions": open_positions,
            "unrealized_pnl": round(unrealized_total, 2),
        }
        return report
    except Exception as e:
        return {"error": str(e)}

def update_report():
    global latest_report
    latest_report = fetch_data()

@app.route("/")
def home():
    return "BTC Daily Report Web Service"

@app.route("/report")
def report():
    return jsonify(fetch_data())

# 백그라운드 5분마다 실행
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_report, trigger="interval", minutes=5)
scheduler.start()

# 앱 실행
if __name__ == "__main__":
    update_report()
    app.run(host='0.0.0.0', port=10000)
