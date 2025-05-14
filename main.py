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

def get_net_deposit(exch):
    try:
        since = exch.parse8601("2022-01-01T00:00:00Z")  # 충분히 과거부터 조회
        deposits = 0
        withdrawals = 0
        page = 1
        while True:
            result = exch.privateMixGetAccountAccountBill({
                'productType': 'UMCBL',
                'marginCoin': 'USDT',
                'startTime': since,
                'endTime': int(time.time() * 1000),
                'pageSize': 100,
                'pageNo': page,
            })
            records = result['data']
            if not records:
                break
            for r in records:
                if r['businessType'] == 'deposit':
                    deposits += float(r['amount'])
                elif r['businessType'] == 'withdraw':
                    withdrawals += float(r['amount'])
            if len(records) < 100:
                break
            page += 1
        return round(deposits - withdrawals, 2)
    except Exception as e:
        return None

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

    net_deposit = get_net_deposit(exch)
    return_rate = None
    if net_deposit and net_deposit > 0:
        return_rate = round((equity - net_deposit) / net_deposit * 100, 2)

    return {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "equity": equity,
        "netDeposit": net_deposit,
        "returnRate": return_rate,
        "totalUnrealizedPnl": sum(p["unrealizedPnl"] for p in filtered_positions),
        "positions": filtered_positions,
    }

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
