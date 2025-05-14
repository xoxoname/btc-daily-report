import os
import time
from datetime import datetime, timezone
from threading import Lock

from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import ccxt

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
PASSWORD = os.getenv("BITGET_API_PASSPHRASE")

# 전역 변수에 최신 리포트 저장
report = {
    "equity": None,
    "today_return_pct": None,
    "realized_pnl": None,
    "unrealized_pnl": None,
    "cumulative_pnl": 0.0,
    "timestamp": None
}
lock = Lock()

def fetch_data():
    global report
    exch = ccxt.bitget({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "password": PASSWORD,
        "enableRateLimit": True,
    })
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp() * 1000

    # 1) 총 자산(equity) 조회
    bal = exch.fetch_balance({"type": "future"})
    # bitget 반환 구조에 따라 조정
    total = sum(float(x['equity']) for x in bal['info'] if 'equity' in x)

    # 2) 오늘 실현 PnL 조회
    try:
        bills = exch.publicGetMixAccountAccountBill({
            "productType": "umcbl",
            "marginCoin": "USDT",
            "startTime": int(start_of_day),
            "endTime": int(now.timestamp() * 1000),
            "pageSize": 100
        })['data']
        realized = sum(float(x['realProfit']) for x in bills)
    except Exception:
        realized = None

    # 3) 실시간 포지션 미실현 PnL
    try:
        pos = exch.publicGetMixPositionOpenPositions({
            "productType": "umcbl",
            "marginCoin": "USDT"
        })['data']
        unrealized = sum(float(p['unrealisedPnl']) for p in pos)
    except Exception:
        unrealized = None

    # 4) 당일 수익률
    if report["equity"] not in (None, 0):
        today_return = (total - report["equity"]) / report["equity"] * 100
    else:
        today_return = 0.0

    with lock:
        report.update({
            "equity": round(total, 4),
            "today_return_pct": round(today_return, 2),
            "realized_pnl": round(realized, 4) if realized is not None else None,
            "unrealized_pnl": round(unrealized, 4) if unrealized is not None else None,
            "cumulative_pnl": round((report["cumulative_pnl"] or 0) + (realized or 0), 4),
            "timestamp": now.astimezone().isoformat()
        })

# 백그라운드에서 5분마다 갱신
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, 'interval', minutes=5)
scheduler.start()
# 첫 호출
fetch_data()

# Flask 앱
app = Flask(__name__)

@app.route('/report', methods=['GET'])
def get_report():
    with lock:
        return jsonify(report)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
