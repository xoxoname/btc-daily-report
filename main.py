import os
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import ccxt

load_dotenv()

app = Flask(__name__)

def create_exchange():
    return ccxt.bitget({
        'apiKey': os.environ['BITGET_API_KEY'],
        'secret': os.environ['BITGET_SECRET'],
        'password': os.environ['BITGET_PASSPHRASE'],
        'enableRateLimit': True,
    })

def fetch_total_net_deposit(exchange):
    base_url = 'https://api.bitget.com/api/mix/v1/account/accountBill'
    headers = {
        'ACCESS-KEY': os.environ['BITGET_API_KEY'],
        'ACCESS-SIGN': '',
        'ACCESS-TIMESTAMP': '',
        'ACCESS-PASSPHRASE': os.environ['BITGET_PASSPHRASE'],
        'Content-Type': 'application/json'
    }

    start_time = int((datetime.utcnow() - timedelta(days=730)).timestamp() * 1000)  # 2년치 최대 조회
    end_time = int(datetime.utcnow().timestamp() * 1000)
    step = 30 * 24 * 60 * 60 * 1000  # 30일 단위(ms)

    deposit_total = 0.0
    withdraw_total = 0.0

    while start_time < end_time:
        segment_end = min(start_time + step, end_time)
        params = {
            "productType": "UMCBL",
            "marginCoin": "USDT",
            "startTime": start_time,
            "endTime": segment_end,
            "pageSize": 100,
            "lastEndId": ""
        }

        response = requests.get(base_url, params=params, headers={})
        if response.status_code != 200:
            break

        data = response.json()
        if not data.get("data", []):
            break

        for entry in data["data"]:
            if entry.get("business") == "deposit":
                deposit_total += float(entry.get("amount", 0))
            elif entry.get("business") == "withdraw":
                withdraw_total += float(entry.get("amount", 0))

        start_time = segment_end
        time.sleep(0.3)

    net = deposit_total - withdraw_total
    return round(net, 4)

def fetch_data():
    exch = create_exchange()

    balance = exch.fetch_balance({'type': 'future'})
    equity = float(balance['info']['data'][0]['equity'])
    net_deposit = fetch_total_net_deposit(exch)
    pnl = equity - net_deposit
    pnl_percent = (pnl / net_deposit * 100) if net_deposit > 0 else 0

    return {
        "총 자산 (USDT)": equity,
        "순입금액 (USDT)": net_deposit,
        "총 손익 (USDT)": round(pnl, 4),
        "총 수익률 (%)": round(pnl_percent, 2)
    }

@app.route('/')
def index():
    return "BTC Daily Report API"

@app.route('/report')
def report():
    try:
        return jsonify(fetch_data())
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_data, 'interval', minutes=5)
    scheduler.start()
    app.run(host='0.0.0.0', port=10000)
