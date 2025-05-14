import os
import time
import ccxt
import pytz
from datetime import datetime, timedelta
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
tz = pytz.timezone('Asia/Seoul')

# API 키 설정
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSWORD = os.getenv("BITGET_API_PASSWORD")

exch = ccxt.bitget({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "password": API_PASSWORD,
    "enableRateLimit": True,
    "options": {
        "defaultType": "swap",
        "adjustForTimeDifference": True,
    }
})

# 데이터 저장용
latest_report = {}

def fetch_data():
    global latest_report
    try:
        now = datetime.now(tz)
        since = datetime(now.year, now.month, now.day, tzinfo=tz)
        since_ts = int(since.timestamp() * 1000)
        now_ts = int(now.timestamp() * 1000)

        # 잔고 조회
        equity = exch.fetch_balance({"type": "swap"})["total"].get("USDT", 0.0)

        # 포지션 조회
        positions = exch.fetch_positions()
        open_positions = [p for p in positions if float(p["contracts"]) > 0]

        total_unrealized_pnl = 0.0
        position_summary = []

        for pos in open_positions:
            symbol = pos["symbol"]
            side = "long" if pos["side"] == "long" else "short"
            amount = float(pos["contracts"])
            entry_price = float(pos["entryPrice"])
            current_price = float(pos["last"])

            # 비트코인 가격 기준 Coinbase로 교체
            coinbase = ccxt.coinbase()
            btc_price = coinbase.fetch_ticker("BTC/USDT")["last"]

            unrealized_pnl = (btc_price - entry_price) * amount if side == "long" else (entry_price - btc_price) * amount
            total_unrealized_pnl += unrealized_pnl

            position_summary.append({
                "symbol": symbol,
                "side": side,
                "amount": round(amount, 4),
                "entry_price": round(entry_price, 2),
                "current_price": round(btc_price, 2),
                "unrealized_pnl": round(unrealized_pnl, 4)
            })

        # 수익 내역 조회 (실현)
        trades = exch.fetch_my_trades(symbol="BTC/USDT", since=since_ts)
        realized_pnl = sum([float(t.get("info", {}).get("profit", 0)) for t in trades])

        # 수익률
        equity_change = equity  # 단순 비교 기준
        initial_equity = equity - realized_pnl - total_unrealized_pnl
        percent_change = ((equity - initial_equity) / initial_equity) * 100 if initial_equity else 0.0

        latest_report = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "equity": round(equity, 4),
            "percent_change": round(percent_change, 2),
            "realized_pnl": round(realized_pnl, 4),
            "unrealized_pnl": round(total_unrealized_pnl, 4),
            "positions": position_summary
        }

    except Exception as e:
        latest_report = {"error": str(e)}

@app.route("/report", methods=["GET"])
def report():
    return jsonify(latest_report)

# 스케줄러 등록
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, "interval", minutes=5)
scheduler.start()

# 최초 1회 실행
fetch_data()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
