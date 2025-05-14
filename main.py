import os
import time
import ccxt
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

def create_exchange():
    return ccxt.bitget({
        'apiKey': os.environ['BITGET_API_KEY'],
        'secret': os.environ['BITGET_SECRET'],
        'password': os.environ['BITGET_PASSWORD'],
        'enableRateLimit': True,
    })

def fetch_data():
    exch = create_exchange()
    try:
        positions = exch.fetch_positions()
        balance = exch.fetch_balance({'type': 'future'})
        equity = float(balance['total']['USDT'])

        open_positions = []
        total_unrealized = 0

        for pos in positions:
            if pos['contracts'] > 0:
                unrealized = float(pos.get('unrealizedPnl', 0))
                total_unrealized += unrealized
                open_positions.append({
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'contracts': pos['contracts'],
                    'entryPrice': pos['entryPrice'],
                    'unrealizedPnl': unrealized,
                })

        realized_pnl = 0  # Bitget API는 별도 처리 필요. 지금은 0으로 둠.
        percent_change = 0  # 당일 대비 수익률 계산하려면 어제 equity 저장 필요

        return {
            'equity': equity,
            'percent_change': percent_change,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': total_unrealized,
            'positions': open_positions,
        }

    except Exception as e:
        return {'error': str(e)}

@app.route("/")
def home():
    return "BTC Real-Time Profit Service is Live."

@app.route("/report")
def report():
    return jsonify(fetch_data())

# 백그라운드 스케줄러로 5분마다 데이터 갱신 (Render 무료 플랜 대응)
def schedule_job():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_data, 'interval', minutes=5)
    scheduler.start()

if __name__ == "__main__":
    schedule_job()
    app.run(host="0.0.0.0", port=10000)
