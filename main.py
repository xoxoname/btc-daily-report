import os
import ccxt
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Load API keys
load_dotenv()
api_key = os.getenv("BITGET_API_KEY")
secret = os.getenv("BITGET_API_SECRET")
password = os.getenv("BITGET_API_PASSPHRASE")

# Configure timezone
KST = pytz.timezone("Asia/Seoul")

# Coinbase 가격 가져오기
def get_btc_price():
    try:
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        return float(response.json()["data"]["amount"])
    except:
        return None

# Bitget 거래소 연결
def connect_bitget():
    return ccxt.bitget({
        'apiKey': api_key,
        'secret': secret,
        'password': password,
        'options': {
            'defaultType': 'swap',
        }
    })

# 자산 정보 조회
def fetch_equity(exchange):
    try:
        balance = exchange.fetch_balance({"type": "swap"})
        total_equity = float(balance["total"]["USDT"])
        return total_equity
    except Exception as e:
        return {"error": str(e)}

# 포지션 정보 조회
def fetch_positions(exchange):
    try:
        markets = exchange.load_markets()
        btc_market = [s for s in markets if "BTC/USDT" in s]
        result = []
        total_unrealized = 0.0
        for symbol in btc_market:
            pos = exchange.fetch_positions([symbol])
            for p in pos:
                upnl = float(p["unrealizedPnl"])
                result.append({
                    "symbol": symbol,
                    "size": p["contracts"],
                    "entry": p["entryPrice"],
                    "upnl": upnl
                })
                total_unrealized += upnl
        return result, total_unrealized
    except Exception as e:
        return {"error": str(e)}, 0.0

# 수익률 계산
def calculate_daily_pnl(starting_equity, current_equity):
    try:
        pnl = current_equity - starting_equity
        rate = (pnl / starting_equity) * 100
        return round(pnl, 4), round(rate, 2)
    except:
        return 0.0, 0.0

# 리포트 생성
def generate_report():
    try:
        exch = connect_bitget()
        equity = fetch_equity(exch)
        if isinstance(equity, dict): return equity

        positions, upnl = fetch_positions(exch)
        if isinstance(positions, dict): return positions

        price = get_btc_price()
        realized_pnl, pnl_rate = calculate_daily_pnl(starting_equity=equity + upnl, current_equity=equity)

        return {
            "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
            "btc_price_usd": price,
            "total_equity_usdt": round(equity, 4),
            "realized_pnl": round(realized_pnl, 4),
            "unrealized_pnl": round(upnl, 4),
            "pnl_rate_percent": f"{pnl_rate}%",
            "positions": positions
        }
    except Exception as e:
        return {"error": str(e)}

# Flask 앱 구성
app = Flask(__name__)
latest_report = {}

@app.route("/report")
def get_report():
    return jsonify(latest_report)

# 자동 갱신 스케줄러
def update_report():
    global latest_report
    latest_report = generate_report()

scheduler = BackgroundScheduler(timezone=KST)
scheduler.add_job(update_report, "interval", minutes=5)
scheduler.start()
update_report()

# 시작
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

