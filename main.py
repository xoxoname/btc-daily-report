from dotenv import load_dotenv
import ccxt
import requests
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os

# Load env variables
load_dotenv()

app = Flask(__name__)

def create_exchange():
    return ccxt.bitget({
        'apiKey': os.environ['BITGET_API_KEY'],
        'secret': os.environ['BITGET_SECRET'],
        'password': os.environ['BITGET_PASSWORD'],
        'enableRateLimit': True,
    })

def get_coinbase_price():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-USDT/spot")
        return float(res.json()['data']['amount'])
    except:
        return None

def fetch_data():
    try:
        exch = create_exchange()
        balance = exch.fetch_balance({'type': 'swap'})
        usdt = balance['total'].get('USDT', 0)
        equity = float(usdt)

        positions = exch.fetch_positions()
        realized = sum(float(p.get('realizedPnl', 0)) for p in positions)
        unrealized = sum(float(p.get('unrealizedPnl', 0)) for p in positions)

        deposits = exch.privateMixGetV2MixAccountDepositHistory({'coin': 'USDT'})['data']['rows']
        withdrawals = exch.privateMixGetV2MixAccountWithdrawalHistory({'coin': 'USDT'})['data']['rows']

        total_in = sum(float(d['amount']) for d in deposits if d['status'] == 'success')
        total_out = sum(float(w['amount']) for w in withdrawals if w['status'] == 'success')
        net_inflow = total_in - total_out

        total_pnl = equity - net_inflow
        base = net_inflow if net_inflow > 0 else 1
        pct = (total_pnl / base) * 100

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'equity': round(equity, 2),
            'realized_pnl': round(realized, 2),
            'unrealized_pnl': round(unrealized, 2),
            'total_pnl': round(total_pnl, 2),
            'net_inflow': round(net_inflow, 2),
            'profit_pct': round(pct, 2),
            'coinbase_price': get_coinbase_price()
        }

    except Exception as e:
        return {'error': str(e)}

@app.route('/')
def index():
    return 'BTC 리포트 API 활성화 중'

@app.route('/report')
def report():
    return jsonify(fetch_data())

scheduler = BackgroundScheduler()
scheduler.add_job(func=fetch_data, trigger="interval", minutes=5)
scheduler.start()
